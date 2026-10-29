#include "targets.hpp"

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <mutex>
#include <utility>

#include <grpcpp/support/status.h>
#include <userver/components/component_context.hpp>
#include <userver/ugrpc/client/call_options.hpp>
#include <userver/ugrpc/client/exceptions.hpp>

namespace simple_grpc_target_service {
namespace {
bool ValidNumber(int value) { return value >= 0 && value <= 100; }
bool ValidModeValue(const api::ModeValue& request) {
  return request.has_mode() && request.has_value() &&
         ValidNumber(request.value()) &&
         (request.mode() == api::MODE_SAFE || request.mode() == api::MODE_FAST);
}
grpc::Status Invalid() {
  return {grpc::StatusCode::INVALID_ARGUMENT,
          "Missing or invalid application fields"};
}
}  // namespace

Targets::Targets(const userver::components::ComponentConfig& config,
                 const userver::components::ComponentContext& context)
    : api::TargetServiceBase::Component(config, context),
      decision_client_(context.FindComponent<DecisionClient>("decision-client")
                           .GetClient()) {}

Targets::StatelessCrashResult Targets::StatelessCrash(CallContext&,
                                                      api::Numbers&& request) {
  if (!request.has_x() || !request.has_y() || !ValidNumber(request.x()) ||
      !ValidNumber(request.y()))
    return Invalid();
  if (request.x() + request.y() == 42 && request.x() == request.y()) {
    // Intentional fault, matching the REST target.
    std::abort();
  }
  api::Sum response;
  response.set_sum(request.x() + request.y());
  return response;
}

Targets::StatelessErrorResult Targets::StatelessError(
    CallContext&, api::ModeValue&& request) {
  if (!ValidModeValue(request)) return Invalid();
  if (request.mode() == api::MODE_FAST && request.value() == 13) {
    // Intentional server error: the gRPC counterpart of HTTP 500.
    return grpc::Status{grpc::StatusCode::INTERNAL,
                        "Intentional fast-mode failure"};
  }
  api::Value response;
  response.set_value(request.value());
  return response;
}

Targets::SequenceResult Targets::Sequence(CallContext&,
                                          api::Command&& request) {
  if (!request.has_action() || request.action() < api::ACTION_BEGIN ||
      request.action() > api::ACTION_RESET)
    return Invalid();
  const std::lock_guard lock(sequence_mutex_);
  switch (request.action()) {
    case api::ACTION_BEGIN:
      stage_ = api::Stage::BEGUN;
      break;
    case api::ACTION_ADVANCE:
      stage_ =
          stage_ == api::Stage::BEGUN ? api::Stage::ADVANCED : api::Stage::IDLE;
      break;
    case api::ACTION_FINISH:
      if (stage_ == api::Stage::ADVANCED) {
        // Intentional fault: begin -> advance -> finish.
        std::abort();
      }
      stage_ = api::Stage::IDLE;
      break;
    default:
      stage_ = api::Stage::IDLE;
      break;
  }
  api::Stage response;
  response.set_stage(stage_);
  return response;
}

Targets::PrepareResult Targets::Prepare(CallContext&, api::Value&& request) {
  if (!request.has_value() || !ValidNumber(request.value())) return Invalid();
  const std::lock_guard lock(shared_mutex_);
  ticket_ = std::to_string(++next_ticket_);
  value_ = request.value();
  committed_ = false;
  api::Ticket response;
  response.set_ticket(ticket_);
  return response;
}

Targets::CommitResult Targets::Commit(CallContext&, api::Ticket&& request) {
  const auto& ticket = request.ticket();
  if (!request.has_ticket() || ticket.empty() || ticket.size() > 20 ||
      !std::all_of(ticket.begin(), ticket.end(),
                   [](char c) { return c >= '0' && c <= '9'; }))
    return Invalid();
  const std::lock_guard lock(shared_mutex_);
  if (ticket != ticket_)
    return grpc::Status{grpc::StatusCode::FAILED_PRECONDITION,
                        "Unknown or expired ticket"};
  if (committed_ && value_ == 42) {
    // Intentional fault: retrying commit for value 42.
    std::abort();
  }
  committed_ = true;
  api::CommittedValue response;
  response.set_ticket(ticket);
  response.set_value(value_);
  return response;
}

Targets::DependencyCrashResult Targets::DependencyCrash(
    CallContext&, api::ModeValue&& request) {
  if (!ValidModeValue(request)) return Invalid();
  userver::ugrpc::client::CallOptions options;
  options.SetTimeout(std::chrono::milliseconds{500});
  options.SetAttempts(1);
  try {
    const api::Decision decision =
        decision_client_.Decide(request, std::move(options));
    if (!decision.has_decision() ||
        (decision.decision() != api::DECISION_ACCEPT &&
         decision.decision() != api::DECISION_RETRY)) {
      return grpc::Status{grpc::StatusCode::UNAVAILABLE,
                          "Invalid dependency decision"};
    }
    if (request.mode() == api::MODE_FAST && request.value() == 13 &&
        decision.decision() == api::DECISION_RETRY) {
      // Intentional fault: both the request and the dependency reply are
      // required.
      std::abort();
    }
    api::ProcessedValue response;
    response.set_value(request.value());
    response.set_decision(decision.decision());
    return response;
  } catch (const userver::ugrpc::client::DeadlineExceededError&) {
    return grpc::Status{grpc::StatusCode::DEADLINE_EXCEEDED,
                        "Dependency timed out"};
  } catch (const userver::ugrpc::client::RpcError&) {
    return grpc::Status{grpc::StatusCode::UNAVAILABLE,
                        "Dependency request failed"};
  }
}
}  // namespace simple_grpc_target_service
