#pragma once

#include <string_view>

#include <userver/server/handlers/http_handler_json_base.hpp>

namespace simple_target_service {

class StatelessCrash final
    : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-stateless-crash";
  using HttpHandlerJsonBase::HttpHandlerJsonBase;

  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;
};

class StatelessError final
    : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-stateless-error";
  using HttpHandlerJsonBase::HttpHandlerJsonBase;

  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;
};

}  // namespace simple_target_service
