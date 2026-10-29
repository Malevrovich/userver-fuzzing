Open `services/simple-target-service` in VS Code and run **Dev Containers: Reopen in Container**.

The container mounts the entire repository at `/workspaces/userver-fuzzing` and opens
`services/simple-target-service` as the workspace. This preserves the relative path
`../../third_party/userver` used by CMake, so builds use the local userver submodule.
Initialize it on the host with `git submodule update --init --recursive` if needed.

After changing the mount, run **Dev Containers: Rebuild Container**. Existing CMake
build directories contain absolute paths from the previous mount. Configure into a
new directory, for example:

```sh
cmake --preset debug -B build-devcontainer-debug
cmake --build build-devcontainer-debug
```

Configuration should print `Using userver from /workspaces/userver-fuzzing/third_party/userver`.
