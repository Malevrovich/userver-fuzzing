#include "dependency.hpp"

#include <chrono>
#include <cstdlib>

#include <userver/clients/http/component.hpp>
#include <userver/clients/http/error.hpp>
#include <userver/clients/http/request.hpp>
#include <userver/clients/http/response.hpp>
#include <userver/components/component_config.hpp>
#include <userver/components/component_context.hpp>
#include <userver/formats/json/exception.hpp>
#include <userver/formats/json/inline.hpp>
#include <userver/formats/json/serialize.hpp>
#include <userver/server/handlers/exceptions.hpp>
#include <userver/yaml_config/merge_schemas.hpp>

#include "request_validation.hpp"

namespace simple_target_service {
namespace {

using BadGateway = userver::server::handlers::ExceptionWithCode<
    userver::server::handlers::HandlerErrorCode::kBadGateway>;
constexpr std::chrono::milliseconds kDependencyTimeout{500};

}  // namespace

DependencyCrash::DependencyCrash(
    const userver::components::ComponentConfig& config,
    const userver::components::ComponentContext& context)
    : HttpHandlerJsonBase(config, context),
      http_client_(context.FindComponent<userver::components::HttpClient>()
                       .GetHttpClient()),
      dependency_url_(config["dependency-url"].As<std::string>()) {}

std::string DependencyCrash::FetchDecision(const Value& body) const {
  try {
    const auto response =
        http_client_.CreateRequest()
            .post(dependency_url_, userver::formats::json::ToString(body))
            .headers({{"Content-Type", "application/json"}})
            .timeout(kDependencyTimeout)
            .retry(1)
            .follow_redirects(false)
            .perform();
    if (!response->IsOk()) {
      throw BadGateway(userver::server::handlers::ExternalBody{
          "Dependency returned a non-200 status"});
    }
    const auto result =
        userver::formats::json::FromString(response->body_view());
    if (!result.IsObject() || result.GetSize() != 1 ||
        !result.HasMember("decision") || !result["decision"].IsString()) {
      throw BadGateway(userver::server::handlers::ExternalBody{
          "Invalid dependency response"});
    }
    auto decision = result["decision"].As<std::string>();
    if (decision != "accept" && decision != "retry") {
      throw BadGateway(userver::server::handlers::ExternalBody{
          "Unknown dependency decision"});
    }
    return decision;
  } catch (const userver::clients::http::BaseException&) {
    throw BadGateway(
        userver::server::handlers::ExternalBody{"Dependency request failed"});
  } catch (const userver::formats::json::Exception&) {
    throw BadGateway(
        userver::server::handlers::ExternalBody{"Invalid dependency JSON"});
  }
}

DependencyCrash::Value DependencyCrash::HandleRequestJsonThrow(
    const HttpRequest&, const Value& body, RequestContext&) const {
  CheckFields(body, {"mode", "value"});
  const auto mode = ReadText(body, "mode");
  const auto value = ReadNumber(body, "value");
  if (mode != "safe" && mode != "fast") {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{"Unknown mode"});
  }

  const auto decision = FetchDecision(body);
  if (mode == "fast" && value == 13 && decision == "retry") {
    // Intentional fault: neither the request nor the dependency reply alone
    // kills the process.
    std::abort();
  }
  return userver::formats::json::MakeObject("value", value, "decision",
                                            decision);
}

userver::yaml_config::Schema DependencyCrash::GetStaticConfigSchema() {
  return userver::yaml_config::MergeSchemas<
      userver::server::handlers::HttpHandlerJsonBase>(R"(
type: object
description: Fuzzing target that calls an external HTTP dependency
additionalProperties: false
properties:
    dependency-url:
        type: string
        description: URL of the decision dependency
)");
}

}  // namespace simple_target_service
