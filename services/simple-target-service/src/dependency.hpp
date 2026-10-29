#pragma once

#include <string>
#include <string_view>

#include <userver/clients/http/client.hpp>
#include <userver/server/handlers/http_handler_json_base.hpp>
#include <userver/yaml_config/schema.hpp>

namespace simple_target_service {

class DependencyCrash final
    : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-dependency-crash";

  DependencyCrash(const userver::components::ComponentConfig&,
                  const userver::components::ComponentContext&);
  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;
  static userver::yaml_config::Schema GetStaticConfigSchema();

 private:
  std::string FetchDecision(const Value& body) const;

  userver::clients::http::Client& http_client_;
  const std::string dependency_url_;
};

}  // namespace simple_target_service
