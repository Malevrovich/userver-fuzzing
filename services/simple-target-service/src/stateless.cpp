#include "stateless.hpp"

#include <cstdlib>
#include <stdexcept>

#include <userver/formats/json/inline.hpp>

#include "request_validation.hpp"

namespace simple_target_service {

StatelessCrash::Value StatelessCrash::HandleRequestJsonThrow(
    const HttpRequest&, const Value& body, RequestContext&) const {
  CheckFields(body, {"x", "y"});
  const auto x = ReadNumber(body, "x");
  const auto y = ReadNumber(body, "y");

  if (x + y == 42) {
    if (x == y) {
      // Intentional fault: terminate the process even in Release, without
      // undefined behavior.
      std::abort();
    }
  }
  return userver::formats::json::MakeObject("sum", x + y);
}

StatelessError::Value StatelessError::HandleRequestJsonThrow(
    const HttpRequest&, const Value& body, RequestContext&) const {
  CheckFields(body, {"mode", "value"});
  const auto mode = ReadText(body, "mode");
  const auto value = ReadNumber(body, "value");
  if (mode != "safe" && mode != "fast") {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{"Unknown mode"});
  }

  if (mode == "fast" && value == 13) {
    // Intentional fault: userver converts the unhandled exception into HTTP
    // 500.
    throw std::runtime_error("Intentional fast-mode failure");
  }
  return userver::formats::json::MakeObject("value", value);
}

}  // namespace simple_target_service
