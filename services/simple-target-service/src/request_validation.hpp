#pragma once

#include <initializer_list>
#include <string>
#include <string_view>

#include <userver/formats/json/value.hpp>
#include <userver/server/handlers/exceptions.hpp>

namespace simple_target_service {

inline void CheckFields(const userver::formats::json::Value& body,
                        std::initializer_list<std::string_view> fields) {
  if (!body.IsObject() || body.GetSize() != fields.size()) {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{"Unexpected JSON fields"});
  }
  for (const auto field : fields) {
    if (!body.HasMember(field)) {
      throw userver::server::handlers::ClientError(
          userver::server::handlers::ExternalBody{"Missing JSON field"});
    }
  }
}

inline int ReadNumber(const userver::formats::json::Value& body,
                      std::string_view field) {
  const auto value = body[field];
  if (!value.IsInt() || value.As<int>() < 0 || value.As<int>() > 100) {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{
            "Expected integer in [0, 100]"});
  }
  return value.As<int>();
}

inline std::string ReadText(const userver::formats::json::Value& body,
                            std::string_view field) {
  if (!body[field].IsString()) {
    throw userver::server::handlers::ClientError(
        userver::server::handlers::ExternalBody{"Expected string"});
  }
  return body[field].As<std::string>();
}

}  // namespace simple_target_service
