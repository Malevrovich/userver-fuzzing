Open `services/simple-grpc-target-service` in VS Code and choose **Dev Containers: Reopen in Container**.

The official userver v3.2 image supplies the build dependencies. The entire repository
is mounted at `/workspaces/userver-fuzzing`, preserving `../../third_party/userver`.
Initialize the submodule on the host with `git submodule update --init --recursive`.

Inside the container, from the service directory:

```sh
make build-debug
make test-debug
make start-debug
```

Ports: 8083 for application gRPC, 8082 for HTTP health/tests-control.
The external gRPC decision dependency defaults to `localhost:8084` and must be
reachable from inside the container. Testsuite replaces it with `grpc_mockserver`.
