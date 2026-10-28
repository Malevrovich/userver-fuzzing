#pragma once

#include <string_view>

#include <userver/engine/mutex.hpp>
#include <userver/server/handlers/http_handler_json_base.hpp>

namespace simple_target_service {

class Sequence final : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-sequence";
  using HttpHandlerJsonBase::HttpHandlerJsonBase;

  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;

 private:
  enum class Stage { kIdle, kBegun, kAdvanced };
  mutable userver::engine::Mutex mutex_;
  mutable Stage stage_ = Stage::kIdle;
};

}  // namespace simple_target_service
