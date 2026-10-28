#pragma once

#include <string>
#include <string_view>

namespace simple_target_service {

enum class UserType { kFirstTime, kKnown };

std::string SayHelloTo(std::string_view name, UserType type);

}  // namespace simple_target_service