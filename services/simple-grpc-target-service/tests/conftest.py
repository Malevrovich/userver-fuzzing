import pytest

import handlers.hello_pb2_grpc as hello_services
import fuzzing.targets_pb2_grpc as targets_services

pytest_plugins = ["pytest_userver.plugins.core", "pytest_userver.plugins.grpc"]

USERVER_CONFIG_HOOKS = ["userver_config_decision"]


@pytest.fixture(scope="session")
def userver_config_decision(grpc_mockserver_endpoint):
    def patch_config(config_yaml, config_vars):
        config_vars["decision-endpoint"] = grpc_mockserver_endpoint

    return patch_config


@pytest.fixture
def grpc_service(grpc_channel, service_client):
    return hello_services.HelloServiceStub(grpc_channel)


@pytest.fixture
def target(grpc_channel, service_client):
    return targets_services.TargetServiceStub(grpc_channel)
