#include <userver/clients/dns/component.hpp>
#include <userver/clients/http/component_list.hpp>
#include <userver/components/component.hpp>
#include <userver/components/component_list.hpp>
#include <userver/components/minimal_server_component_list.hpp>
#include <userver/congestion_control/component.hpp>
#include <userver/server/handlers/ping.hpp>
#include <userver/server/handlers/tests_control.hpp>
#include <userver/testsuite/testsuite_support.hpp>

#include <userver/utils/daemon_run.hpp>

#include <hello.hpp>
#include "sequence.hpp"
#include "shared.hpp"
#include "stateless.hpp"

int main(int argc, char* argv[]) {
  auto component_list =
      userver::components::MinimalServerComponentList()
          .Append<userver::server::handlers::Ping>()
          .Append<userver::components::TestsuiteSupport>()
          .AppendComponentList(userver::clients::http::ComponentList())
          .Append<userver::clients::dns::Component>()
          .Append<userver::server::handlers::TestsControl>()
          .Append<userver::congestion_control::Component>()
          .Append<simple_target_service::Hello>()
          .Append<simple_target_service::StatelessCrash>()
          .Append<simple_target_service::StatelessError>()
          .Append<simple_target_service::Sequence>()
          .Append<simple_target_service::SharedState>()
          .Append<simple_target_service::Prepare>()
          .Append<simple_target_service::Commit>();

  return userver::utils::DaemonMain(argc, argv, component_list);
}
