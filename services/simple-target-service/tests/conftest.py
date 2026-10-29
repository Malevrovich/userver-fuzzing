import pytest


pytest_plugins = [
    "pytest_userver.plugins.core",
]

USERVER_CONFIG_HOOKS = ["userver_config_dependency"]


@pytest.fixture(scope="session")
def userver_config_http_client(userver_config_http_client):
    def patch_config(config_yaml, config_vars):
        userver_config_http_client(config_yaml, config_vars)
        # Keep the target's real timeout instead of testsuite's default 10 seconds.
        config_yaml["components_manager"]["components"]["http-client-core"][
            "testsuite-timeout"
        ] = "500ms"

    return patch_config


@pytest.fixture(scope="session")
def userver_config_dependency(mockserver_info):
    def patch_config(config_yaml, config_vars):
        config_yaml["components_manager"]["components"]["handler-dependency-crash"][
            "dependency-url"
        ] = mockserver_info.url("/decision")

    return patch_config
