#include "sequence.hpp"

#include <cstdlib>
#include <mutex>

#include <userver/formats/json/inline.hpp>

#include "request_validation.hpp"

namespace simple_target_service {

Sequence::Value Sequence::HandleRequestJsonThrow(const HttpRequest&,
                                                 const Value& body,
                                                 RequestContext&) const {
  CheckFields(body, {"action"});
  const auto action = ReadText(body, "action");
  if (action != "begin" && action != "advance" && action != "finish" &&
      action != "reset") {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{"Unknown action"});
  }

  const std::lock_guard lock(mutex_);
  if (action == "begin") {
    stage_ = Stage::kBegun;
  } else if (action == "advance") {
    stage_ = stage_ == Stage::kBegun ? Stage::kAdvanced : Stage::kIdle;
  } else if (action == "finish") {
    if (stage_ == Stage::kAdvanced) {
      // Intentional fault: begin -> advance -> finish kills the process.
      std::abort();
    }
    stage_ = Stage::kIdle;
  } else {
    stage_ = Stage::kIdle;
  }

  const auto stage = stage_ == Stage::kBegun      ? "begun"
                     : stage_ == Stage::kAdvanced ? "advanced"
                                                  : "idle";
  return userver::formats::json::MakeObject("stage", stage);
}

}  // namespace simple_target_service
