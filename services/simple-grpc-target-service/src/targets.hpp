#pragma once

#include <cstdint>
#include <string>
#include <string_view>

#include <fuzzing/targets_client.usrv.pb.hpp>
#include <fuzzing/targets_service.usrv.pb.hpp>
#include <userver/engine/mutex.hpp>
#include <userver/ugrpc/client/simple_client_component.hpp>

namespace simple_grpc_target_service {
namespace api = ::fuzzing::target;

using DecisionClient =
    userver::ugrpc::client::SimpleClientComponent<api::DecisionServiceClient>;

class Targets final : public api::TargetServiceBase::Component {
 public:
  static constexpr std::string_view kName = "grpc-targets";
  Targets(const userver::components::ComponentConfig&,
          const userver::components::ComponentContext&);

  StatelessCrashResult StatelessCrash(CallContext&, api::Numbers&&) override;
  StatelessErrorResult StatelessError(CallContext&, api::ModeValue&&) override;
  SequenceResult Sequence(CallContext&, api::Command&&) override;
  PrepareResult Prepare(CallContext&, api::Value&&) override;
  CommitResult Commit(CallContext&, api::Ticket&&) override;
  DependencyCrashResult DependencyCrash(CallContext&,
                                        api::ModeValue&&) override;

 private:
  userver::engine::Mutex sequence_mutex_;
  api::Stage::Kind stage_ = api::Stage::IDLE;
  userver::engine::Mutex shared_mutex_;
  std::uint64_t next_ticket_ = 0;
  std::string ticket_;
  int value_ = 0;
  bool committed_ = false;
  api::DecisionServiceClient& decision_client_;
};
}  // namespace simple_grpc_target_service
