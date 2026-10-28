#include "shared.hpp"

#include <algorithm>
#include <cstdlib>
#include <mutex>

#include <userver/components/component_context.hpp>
#include <userver/formats/json/inline.hpp>

#include "request_validation.hpp"

namespace simple_target_service {

std::string SharedState::Prepare(int value) {
  const std::lock_guard lock(mutex_);
  ticket_ = std::to_string(++next_ticket_);
  value_ = value;
  committed_ = false;
  return ticket_;
}

int SharedState::Commit(const std::string& ticket) {
  const std::lock_guard lock(mutex_);
  if (ticket != ticket_) {
    throw userver::server::handlers::ConflictError(
        userver::server::handlers::ExternalBody{"Unknown or expired ticket"});
  }
  if (committed_ && value_ == 42) {
    // Intentional fault: retrying commit is broken only for the value 42.
    std::abort();
  }
  committed_ = true;
  return value_;
}

Prepare::Prepare(const userver::components::ComponentConfig& config,
                 const userver::components::ComponentContext& context)
    : HttpHandlerJsonBase(config, context),
      state_(context.FindComponent<SharedState>()) {}

Prepare::Value Prepare::HandleRequestJsonThrow(const HttpRequest&,
                                               const Value& body,
                                               RequestContext&) const {
  CheckFields(body, {"value"});
  const auto value = ReadNumber(body, "value");
  return userver::formats::json::MakeObject("ticket", state_.Prepare(value));
}

Commit::Commit(const userver::components::ComponentConfig& config,
               const userver::components::ComponentContext& context)
    : HttpHandlerJsonBase(config, context),
      state_(context.FindComponent<SharedState>()) {}

Commit::Value Commit::HandleRequestJsonThrow(const HttpRequest&,
                                             const Value& body,
                                             RequestContext&) const {
  CheckFields(body, {"ticket"});
  const auto ticket = ReadText(body, "ticket");
  if (ticket.empty() || ticket.size() > 20 ||
      !std::all_of(ticket.begin(), ticket.end(),
                   [](char c) { return c >= '0' && c <= '9'; })) {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{
            "Expected a numeric ticket of 1 to 20 digits"});
  }
  return userver::formats::json::MakeObject("ticket", ticket, "value",
                                            state_.Commit(ticket));
}

}  // namespace simple_target_service
