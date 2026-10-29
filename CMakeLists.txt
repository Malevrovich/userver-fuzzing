cmake_minimum_required(VERSION 3.24)
project(userver-fuzzing LANGUAGES CXX)

if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/third_party/userver/CMakeLists.txt")
    message(FATAL_ERROR
        "userver sources are missing. Run git submodule update --init --recursive.")
endif()

enable_testing()
add_subdirectory(services/simple-target-service)
add_subdirectory(services/simple-grpc-target-service)
