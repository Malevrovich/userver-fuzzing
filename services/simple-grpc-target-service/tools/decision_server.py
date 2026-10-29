"""Tiny external dependency using the same generated protobuf contract as testsuite."""

import argparse
import asyncio

import grpc
import fuzzing.targets_pb2 as api
import fuzzing.targets_pb2_grpc as services


class Decision(services.DecisionServiceServicer):
    def __init__(self, decision):
        self.decision = decision

    async def Decide(self, request, context):
        if (
            not request.HasField("mode")
            or not request.HasField("value")
            or request.mode not in (api.MODE_SAFE, api.MODE_FAST)
            or not 0 <= request.value <= 100
        ):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid mode/value")
        return api.Decision(decision=self.decision)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", choices=["accept", "retry"], default="accept")
    parser.add_argument("--endpoint", default="localhost:8084")
    args = parser.parse_args()
    server = grpc.aio.server()
    decision = api.DECISION_ACCEPT if args.decision == "accept" else api.DECISION_RETRY
    services.add_DecisionServiceServicer_to_server(Decision(decision), server)
    if not server.add_insecure_port(args.endpoint):
        raise RuntimeError(f"Cannot listen on {args.endpoint}")
    await server.start()
    print(f"DecisionService listening on {args.endpoint}: {args.decision}", flush=True)
    try:
        await server.wait_for_termination()
    finally:
        await server.stop(grace=0)


if __name__ == "__main__":
    asyncio.run(main())
