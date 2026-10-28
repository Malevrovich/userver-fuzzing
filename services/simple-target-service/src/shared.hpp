#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include <userver/components/component_base.hpp>
#include <userver/engine/mutex.hpp>
#include <userver/server/handlers/http_handler_json_base.hpp>

namespace simple_target_service {

class SharedState final : public userver::components::ComponentBase {
 public:
  static constexpr std::string_view kName = "shared-state";
  using ComponentBase::ComponentBase;

  std::string Prepare(int value);
  int Commit(const std::string& ticket);

 private:
  userver::engine::Mutex mutex_;
  std::uint64_t next_ticket_ = 0;
  std::string ticket_;
  int value_ = 0;
  bool committed_ = false;
};

class Prepare final : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-prepare";
  Prepare(const userver::components::ComponentConfig&,
          const userver::components::ComponentContext&);

  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;

 private:
  SharedState& state_;
};

class Commit final : public userver::server::handlers::HttpHandlerJsonBase {
 public:
  static constexpr std::string_view kName = "handler-commit";
  Commit(const userver::components::ComponentConfig&,
         const userver::components::ComponentContext&);

  Value HandleRequestJsonThrow(const HttpRequest&, const Value&,
                               RequestContext&) const override;

 private:
  SharedState& state_;
};

}  // namespace simple_target_service
