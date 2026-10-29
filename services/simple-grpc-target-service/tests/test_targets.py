import asyncio
import signal
import sys

import grpc
import pytest
import yaml

import fuzzing.targets_pb2 as api
import fuzzing.targets_pb2_grpc as services


@pytest.mark.parametrize("x,y", [(0, 0), (100, 100), (20, 22), (21, 20)])
async def test_sum(target, x, y):
    response = await target.StatelessCrash(api.Numbers(x=x, y=y))
    assert response.sum == x + y


@pytest.mark.parametrize(
    "mode,value",
    [
        (api.MODE_SAFE, 13),
        (api.MODE_FAST, 12),
        (api.MODE_FAST, 0),
        (api.MODE_SAFE, 100),
    ],
)
async def test_value(target, mode, value):
    assert (
        await target.StatelessError(api.ModeValue(mode=mode, value=value))
    ).value == value


async def test_internal_keeps_process_alive(target):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.StatelessError(api.ModeValue(mode=api.MODE_FAST, value=13))
    assert error.value.code() == grpc.StatusCode.INTERNAL
    assert (
        await target.StatelessError(api.ModeValue(mode=api.MODE_SAFE, value=13))
    ).value == 13


@pytest.mark.parametrize(
    "method,payload",
    [
        ("StatelessCrash", api.Numbers()),
        ("StatelessCrash", api.Numbers(x=21)),
        ("StatelessCrash", api.Numbers(x=-1, y=21)),
        ("StatelessCrash", api.Numbers(x=101, y=21)),
        ("StatelessError", api.ModeValue(value=13)),
        ("StatelessError", api.ModeValue(mode=api.MODE_FAST)),
        ("StatelessError", api.ModeValue(mode=99, value=13)),
        ("StatelessError", api.ModeValue(mode=api.MODE_FAST, value=-1)),
        ("Sequence", api.Command()),
        ("Sequence", api.Command(action=99)),
        ("Prepare", api.Value()),
        ("Prepare", api.Value(value=101)),
        ("Commit", api.Ticket()),
        ("Commit", api.Ticket(ticket="abc")),
        ("Commit", api.Ticket(ticket="1" * 21)),
        ("DependencyCrash", api.ModeValue()),
    ],
)
async def test_invalid(target, method, payload):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await getattr(target, method)(payload)
    assert error.value.code() == grpc.StatusCode.INVALID_ARGUMENT


@pytest.mark.uservice_oneshot
async def test_sequence_reset(target):
    for action, stage in [
        (api.ACTION_FINISH, api.Stage.IDLE),
        (api.ACTION_ADVANCE, api.Stage.IDLE),
        (api.ACTION_BEGIN, api.Stage.BEGUN),
        (api.ACTION_ADVANCE, api.Stage.ADVANCED),
        (api.ACTION_RESET, api.Stage.IDLE),
        (api.ACTION_FINISH, api.Stage.IDLE),
    ]:
        assert (await target.Sequence(api.Command(action=action))).stage == stage


@pytest.mark.uservice_oneshot
async def test_shared_state(target):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.Commit(api.Ticket(ticket="1"))
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    ticket = await target.Prepare(api.Value(value=41))
    for _ in range(2):
        assert (await target.Commit(ticket)).value == 41
    current = await target.Prepare(api.Value(value=42))
    assert current.ticket != ticket.ticket
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.Commit(ticket)
    assert error.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    await target.Sequence(api.Command(action=api.ACTION_RESET))
    assert (await target.Commit(current)).value == 42


@pytest.fixture
def decision_dependency(grpc_mockserver):
    state = {"decision": api.DECISION_ACCEPT, "status": None, "delay": 0, "calls": []}

    @grpc_mockserver(services.DecisionServiceServicer.Decide)
    async def decide(request, context):
        state["calls"].append(request)
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        if state["status"]:
            await context.abort(state["status"], "Injected dependency error")
        return (
            api.Decision()
            if state["decision"] is None
            else api.Decision(decision=state["decision"])
        )

    return state


@pytest.mark.parametrize(
    "mode,value,decision",
    [
        (api.MODE_FAST, 13, api.DECISION_ACCEPT),
        (api.MODE_SAFE, 13, api.DECISION_RETRY),
        (api.MODE_FAST, 12, api.DECISION_RETRY),
    ],
)
async def test_dependency_success(target, decision_dependency, mode, value, decision):
    decision_dependency["decision"] = decision
    request = api.ModeValue(mode=mode, value=value)
    response = await target.DependencyCrash(request)
    assert response.value == value and response.decision == decision
    assert decision_dependency["calls"] == [request]


@pytest.mark.parametrize("decision", [None, api.DECISION_UNSPECIFIED, 99])
async def test_invalid_dependency_reply(target, decision_dependency, decision):
    decision_dependency["decision"] = decision
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.DependencyCrash(api.ModeValue(mode=api.MODE_FAST, value=13))
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE


async def test_dependency_error(target, decision_dependency):
    decision_dependency["status"] = grpc.StatusCode.UNAVAILABLE
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.DependencyCrash(api.ModeValue(mode=api.MODE_FAST, value=13))
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    assert len(decision_dependency["calls"]) == 1


async def test_dependency_timeout(target, decision_dependency):
    decision_dependency.update(decision=api.DECISION_RETRY, delay=0.8)
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await target.DependencyCrash(api.ModeValue(mode=api.MODE_FAST, value=13))
    assert error.value.code() == grpc.StatusCode.DEADLINE_EXCEEDED
    assert len(decision_dependency["calls"]) == 1


@pytest.fixture
async def isolated_target(
    service_binary,
    service_source_dir,
    tmp_path,
    choose_free_port,
    grpc_mockserver_endpoint,
):
    config = yaml.safe_load(
        (service_source_dir / "configs/config_vars.yaml").read_text()
    )
    config.update(
        {
            "server-port": choose_free_port(),
            "grpc-server-port": choose_free_port(),
            "decision-endpoint": grpc_mockserver_endpoint,
            "logger-level": "critical",
        }
    )
    vars_path = tmp_path / "vars.yaml"
    vars_path.write_text(yaml.safe_dump(config))
    launcher = "import os, resource, sys; resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.execv(sys.argv[1], sys.argv[1:])"
    log_path = tmp_path / "target.log"
    with log_path.open("wb") as log:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            launcher,
            str(service_binary),
            "--config",
            str(service_source_dir / "configs/static_config.yaml"),
            "--config_vars",
            str(vars_path),
            stdout=log,
            stderr=log,
        )
        try:
            async with grpc.aio.insecure_channel(
                f"localhost:{config['grpc-server-port']}"
            ) as channel:
                try:
                    await asyncio.wait_for(channel.channel_ready(), timeout=10)
                except asyncio.TimeoutError:
                    pytest.fail(log_path.read_text())
                yield process, services.TargetServiceStub(channel)
        finally:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


async def expect_abort(process, call):
    with pytest.raises(grpc.aio.AioRpcError) as error:
        await call
    assert error.value.code() == grpc.StatusCode.UNAVAILABLE
    assert await asyncio.wait_for(process.wait(), timeout=5) == -signal.SIGABRT


async def test_stateless_abort(isolated_target):
    process, target = isolated_target
    assert (await target.StatelessCrash(api.Numbers(x=20, y=22), timeout=3)).sum == 42
    await expect_abort(
        process, target.StatelessCrash(api.Numbers(x=21, y=21), timeout=3)
    )


async def test_sequence_abort(isolated_target):
    process, target = isolated_target
    for action in [api.ACTION_BEGIN, api.ACTION_ADVANCE]:
        await target.Sequence(api.Command(action=action), timeout=3)
    await expect_abort(
        process, target.Sequence(api.Command(action=api.ACTION_FINISH), timeout=3)
    )


async def test_shared_abort(isolated_target):
    process, target = isolated_target
    ticket = await target.Prepare(api.Value(value=42), timeout=3)
    assert (await target.Commit(ticket, timeout=3)).value == 42
    await expect_abort(process, target.Commit(ticket, timeout=3))


async def test_dependency_abort(isolated_target, decision_dependency):
    process, target = isolated_target
    request = api.ModeValue(mode=api.MODE_FAST, value=13)
    assert (
        await target.DependencyCrash(request, timeout=3)
    ).decision == api.DECISION_ACCEPT
    decision_dependency["decision"] = api.DECISION_RETRY
    assert (
        await target.DependencyCrash(
            api.ModeValue(mode=api.MODE_SAFE, value=13), timeout=3
        )
    ).decision == api.DECISION_RETRY
    await expect_abort(process, target.DependencyCrash(request, timeout=3))
