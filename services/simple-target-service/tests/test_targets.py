import asyncio
import signal
import sys

import aiohttp
from jsonschema import Draft4Validator
from openapi_spec_validator import validate
import pytest
import yaml


@pytest.fixture(scope="session")
def api_spec(service_source_dir):
    return yaml.safe_load((service_source_dir / "openapi.yaml").read_text())


@pytest.fixture(scope="session")
def dependency_api_spec(service_source_dir):
    return yaml.safe_load((service_source_dir / "dependency-openapi.yaml").read_text())


def check_schema(api_spec, schema, value):
    Draft4Validator({"components": api_spec["components"], **schema}).validate(value)


def check_response(api_spec, path, response):
    responses = api_spec["paths"][path]["post"]["responses"]
    assert str(response.status) in responses
    schema = responses[str(response.status)]
    if "$ref" in schema:
        schema = api_spec["components"]["responses"][schema["$ref"].split("/")[-1]]
    check_schema(
        api_spec, schema["content"]["application/json"]["schema"], response.json()
    )


def test_openapi(api_spec):
    validate(api_spec)


def test_dependency_openapi(dependency_api_spec):
    validate(dependency_api_spec)


def test_forwarded_request_contract_matches_dependency(api_spec, dependency_api_spec):
    for name in ("ModeValue", "SmallNumber"):
        assert (
            api_spec["components"]["schemas"][name]
            == dependency_api_spec["components"]["schemas"][name]
        )


@pytest.mark.parametrize(
    "path,body,expected",
    [
        ("/stateless/crash", {"x": 0, "y": 0}, {"sum": 0}),
        ("/stateless/crash", {"x": 100, "y": 100}, {"sum": 200}),
        ("/stateless/crash", {"x": 20, "y": 22}, {"sum": 42}),
        ("/stateless/crash", {"x": 21, "y": 20}, {"sum": 41}),
        ("/stateless/error", {"mode": "safe", "value": 13}, {"value": 13}),
        ("/stateless/error", {"mode": "fast", "value": 12}, {"value": 12}),
        ("/stateless/error", {"mode": "fast", "value": 0}, {"value": 0}),
        ("/stateless/error", {"mode": "safe", "value": 100}, {"value": 100}),
    ],
)
async def test_stateless_success(service_client, api_spec, path, body, expected):
    response = await service_client.post(path, json=body)
    assert response.status == 200
    assert response.json() == expected
    check_response(api_spec, path, response)


async def test_intentional_500_does_not_kill_service(service_client, api_spec):
    body = {"mode": "fast", "value": 13}
    check_schema(api_spec, {"$ref": "#/components/schemas/ModeValue"}, body)
    response = await service_client.post("/stateless/error", json=body)
    assert response.status == 500
    assert "500" not in api_spec["paths"]["/stateless/error"]["post"]["responses"]
    response = await service_client.post(
        "/stateless/error", json={"mode": "safe", "value": 13}
    )
    assert response.status == 200
    assert response.json() == {"value": 13}


@pytest.mark.parametrize(
    "path,body",
    [
        ("/stateless/crash", {}),
        ("/stateless/crash", {"x": -1, "y": 21}),
        ("/stateless/crash", {"x": 101, "y": 21}),
        ("/stateless/crash", {"x": 21.5, "y": 21}),
        ("/stateless/crash", {"x": True, "y": 21}),
        ("/stateless/crash", {"x": 2**64, "y": 21}),
        ("/stateless/crash", {"x": 21, "y": 21, "extra": 0}),
        ("/stateless/error", {"mode": "other", "value": 13}),
        ("/stateless/error", {"mode": "fast", "value": "13"}),
        ("/stateful/sequence", {"action": "other"}),
        ("/stateful/sequence", {"action": None}),
        ("/shared/prepare", {"value": -1}),
        ("/shared/commit", {"ticket": ""}),
        ("/shared/commit", {"ticket": "1" * 21}),
        ("/shared/commit", {"ticket": "abc"}),
        ("/shared/commit", {"ticket": 1}),
        ("/shared/commit", []),
        ("/shared/commit", None),
    ],
)
async def test_invalid_request(service_client, api_spec, path, body):
    response = await service_client.post(path, json=body)
    assert response.status == 400
    check_response(api_spec, path, response)


async def test_invalid_json(service_client):
    response = await service_client.post(
        "/stateless/crash", data="{", headers={"Content-Type": "application/json"}
    )
    assert response.status == 400


@pytest.mark.uservice_oneshot
async def test_sequence_reset_and_invalid_input(service_client, api_spec):
    path = "/stateful/sequence"
    for action, expected in [
        ("finish", "idle"),
        ("advance", "idle"),
        ("begin", "begun"),
        ("begin", "begun"),
        ("advance", "advanced"),
        ("reset", "idle"),
        ("finish", "idle"),
        ("begin", "begun"),
    ]:
        response = await service_client.post(path, json={"action": action})
        assert response.status == 200
        assert response.json() == {"stage": expected}
        check_response(api_spec, path, response)
    response = await service_client.post(path, json={"action": "reset", "extra": True})
    assert response.status == 400
    response = await service_client.post(path, json={"action": "advance"})
    assert response.json() == {"stage": "advanced"}
    await service_client.post(path, json={"action": "reset"})


@pytest.mark.uservice_oneshot
async def test_shared_tickets_and_independent_state(service_client, api_spec):
    path = "/shared/commit"
    response = await service_client.post(path, json={"ticket": "1"})
    assert response.status == 409
    check_response(api_spec, path, response)

    prepared = await service_client.post("/shared/prepare", json={"value": 41})
    check_response(api_spec, "/shared/prepare", prepared)
    ticket = prepared.json()["ticket"]
    for _ in range(2):
        response = await service_client.post(path, json={"ticket": ticket})
        assert response.status == 200
        assert response.json() == {"ticket": ticket, "value": 41}
        check_response(api_spec, path, response)

    prepared = await service_client.post("/shared/prepare", json={"value": 42})
    current = prepared.json()["ticket"]
    assert current != ticket
    # Invalid requests must not replace the prepared value or consume a commit.
    response = await service_client.post("/shared/prepare", json={"value": 101})
    assert response.status == 400
    response = await service_client.post(path, json={"ticket": ticket})
    assert response.status == 409
    await service_client.post("/stateful/sequence", json={"action": "reset"})
    response = await service_client.post(path, json={"ticket": current})
    assert response.status == 200
    assert response.json() == {"ticket": current, "value": 42}
    # A fresh prepare also clears the committed flag, even for the same value.
    prepared = await service_client.post("/shared/prepare", json={"value": 42})
    response = await service_client.post(
        path, json={"ticket": prepared.json()["ticket"]}
    )
    assert response.status == 200


@pytest.fixture
async def isolated_target(
    service_binary,
    service_source_dir,
    tmp_path,
    choose_free_port,
    api_spec,
    mockserver_info,
):
    """Expected process deaths run separately from the testsuite-managed daemon."""
    port = choose_free_port()
    config_vars = yaml.safe_load(
        (service_source_dir / "configs/config_vars.yaml").read_text()
    )
    config_vars["server-port"] = port
    config_vars["logger-level"] = "critical"
    config_vars["worker-threads"] = 2
    config_vars["dependency-url"] = mockserver_info.url("/decision")
    vars_path = tmp_path / "vars.yaml"
    vars_path.write_text(yaml.safe_dump(config_vars))
    log_path = tmp_path / "service.log"
    # Disable core dumps in this child only: SIGABRT is the expected test result.
    launcher = (
        "import os, resource, sys; "
        "resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); "
        "os.execv(sys.argv[1], sys.argv[1:])"
    )
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
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=2)
            ) as client:
                url = f"http://127.0.0.1:{port}"
                deadline = asyncio.get_running_loop().time() + 10
                while True:
                    assert process.returncode is None, log_path.read_text()
                    try:
                        async with client.get(url + "/ping") as response:
                            if response.status == 200:
                                break
                    except aiohttp.ClientError:
                        pass
                    assert asyncio.get_running_loop().time() < deadline, (
                        log_path.read_text()
                    )
                    await asyncio.sleep(0.05)

                async def post(path, body):
                    schema = api_spec["paths"][path]["post"]["requestBody"]["content"][
                        "application/json"
                    ]["schema"]
                    check_schema(api_spec, schema, body)
                    async with client.post(url + path, json=body) as response:
                        assert response.status == 200
                        return await response.json()

                yield process, post
        finally:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


async def assert_abort(process, post, path, body):
    with pytest.raises(aiohttp.ClientError):
        await post(path, body)
    assert await asyncio.wait_for(process.wait(), timeout=5) == -signal.SIGABRT


async def test_stateless_abort(isolated_target):
    process, post = isolated_target
    assert await post("/stateless/crash", {"x": 20, "y": 22}) == {"sum": 42}
    assert await post("/stateless/crash", {"x": 21, "y": 20}) == {"sum": 41}
    await assert_abort(process, post, "/stateless/crash", {"x": 21, "y": 21})


async def test_sequence_abort(isolated_target):
    process, post = isolated_target
    for action, stage in [("begin", "begun"), ("finish", "idle"), ("advance", "idle")]:
        assert await post("/stateful/sequence", {"action": action}) == {"stage": stage}
    assert await post("/stateful/sequence", {"action": "begin"}) == {"stage": "begun"}
    assert await post("/stateful/sequence", {"action": "advance"}) == {
        "stage": "advanced"
    }
    await assert_abort(process, post, "/stateful/sequence", {"action": "finish"})


async def test_shared_abort(isolated_target):
    process, post = isolated_target
    ticket = await post("/shared/prepare", {"value": 41})
    for _ in range(2):
        assert await post("/shared/commit", ticket) == {**ticket, "value": 41}
    ticket = await post("/shared/prepare", {"value": 42})
    assert await post("/shared/commit", ticket) == {**ticket, "value": 42}
    await assert_abort(process, post, "/shared/commit", ticket)


@pytest.fixture
def decision_dependency(mockserver, dependency_api_spec):
    state = {
        "status": 200,
        "body": {"decision": "accept"},
        "raw": None,
        "delay": 0,
        "requests": [],
    }

    @mockserver.aiohttp_handler("/decision")
    async def decision(request):
        body = await request.json()
        schema = dependency_api_spec["paths"]["/decision"]["post"]["requestBody"][
            "content"
        ]["application/json"]["schema"]
        check_schema(dependency_api_spec, schema, body)
        state["requests"].append(
            {
                "method": request.method,
                "body": body,
                "content_type": request.content_type,
            }
        )
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        if state["raw"] is not None:
            return mockserver.make_response(
                status=state["status"], response=state["raw"]
            )
        return mockserver.make_response(status=state["status"], json=state["body"])

    return state


@pytest.mark.parametrize("decision", ["accept", "retry"])
async def test_decision_dependency_contract(
    mockserver, decision_dependency, dependency_api_spec, decision
):
    decision_dependency["body"] = {"decision": decision}
    async with aiohttp.ClientSession() as client:
        async with client.post(
            mockserver.url("/decision"), json={"mode": "safe", "value": 10}
        ) as response:
            assert response.status == 200
            assert response.content_type == "application/json"
            body = await response.json()
    schema = dependency_api_spec["paths"]["/decision"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    check_schema(dependency_api_spec, schema, body)
    assert body == {"decision": decision}


@pytest.mark.parametrize(
    "body,decision",
    [
        ({"mode": "fast", "value": 13}, "accept"),
        ({"mode": "safe", "value": 13}, "retry"),
        ({"mode": "fast", "value": 12}, "retry"),
        ({"mode": "safe", "value": 100}, "accept"),
    ],
)
async def test_dependency_success(
    service_client, api_spec, decision_dependency, body, decision
):
    decision_dependency["body"] = {"decision": decision}
    response = await service_client.post("/dependency/crash", json=body)
    assert response.status == 200
    assert response.json() == {"value": body["value"], "decision": decision}
    check_response(api_spec, "/dependency/crash", response)
    assert decision_dependency["requests"] == [
        {"method": "POST", "body": body, "content_type": "application/json"}
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"mode": "other", "value": 13},
        {"mode": "fast", "value": -1},
        {"mode": "fast", "value": 101},
        {"mode": "fast", "value": True},
        {"mode": "fast", "value": "13"},
        {"mode": "fast", "value": 13, "extra": 0},
    ],
)
async def test_dependency_rejects_input_before_http_call(
    service_client, api_spec, decision_dependency, body
):
    response = await service_client.post("/dependency/crash", json=body)
    assert response.status == 400
    check_response(api_spec, "/dependency/crash", response)
    assert decision_dependency["requests"] == []


@pytest.mark.parametrize(
    "status,body,raw",
    [
        (503, {"decision": "retry"}, None),
        (301, {"decision": "retry"}, None),
        (204, None, None),
        (200, None, "not json"),
        (200, {}, None),
        (200, {"decision": True}, None),
        (200, {"decision": "unknown"}, None),
        (200, {"decision": "retry", "extra": 0}, None),
    ],
)
async def test_dependency_bad_reply_is_502(
    service_client, api_spec, decision_dependency, status, body, raw
):
    decision_dependency.update(status=status, body=body, raw=raw)
    response = await service_client.post(
        "/dependency/crash", json={"mode": "fast", "value": 13}
    )
    assert response.status == 502
    check_response(api_spec, "/dependency/crash", response)
    assert len(decision_dependency["requests"]) == 1
    assert (await service_client.get("/ping")).status == 200


async def test_dependency_timeout_is_502(service_client, api_spec, decision_dependency):
    decision_dependency.update(body={"decision": "retry"}, delay=0.8)
    response = await service_client.post(
        "/dependency/crash", json={"mode": "fast", "value": 13}
    )
    assert response.status == 502
    check_response(api_spec, "/dependency/crash", response)
    assert len(decision_dependency["requests"]) == 1
    assert (await service_client.get("/ping")).status == 200


async def test_dependency_abort_needs_request_and_reply(
    isolated_target, decision_dependency
):
    process, post = isolated_target
    body = {"mode": "fast", "value": 13}
    assert await post("/dependency/crash", body) == {"value": 13, "decision": "accept"}
    decision_dependency["body"] = {"decision": "retry"}
    assert await post("/dependency/crash", {"mode": "safe", "value": 13}) == {
        "value": 13,
        "decision": "retry",
    }
    assert await post("/dependency/crash", {"mode": "fast", "value": 12}) == {
        "value": 12,
        "decision": "retry",
    }
    await assert_abort(process, post, "/dependency/crash", body)
    assert len(decision_dependency["requests"]) == 4
    assert decision_dependency["requests"][-1]["body"] == body
