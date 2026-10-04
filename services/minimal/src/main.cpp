#include <userver/clients/dns/component.hpp>
#include <userver/clients/http/component_list.hpp>
#include <userver/components/minimal_server_component_list.hpp>
#include <userver/server/handlers/ping.hpp>
#include <userver/server/handlers/tests_control.hpp>
#include <userver/testsuite/testsuite_support.hpp>
#include <userver/utils/daemon_run.hpp>

int main(int argc, char* argv[]) {
    const auto components = userver::components::MinimalServerComponentList()
                                .Append<userver::clients::dns::Component>()
                                .AppendComponentList(userver::clients::http::ComponentList())
                                .Append<userver::server::handlers::Ping>()
                                .Append<userver::components::TestsuiteSupport>()
                                .Append<userver::server::handlers::TestsControl>();

    return userver::utils::DaemonMain(argc, argv, components);
}
