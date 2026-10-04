cmake_minimum_required(VERSION 3.24)
project(userver-fuzzing LANGUAGES CXX)

set(USERVER_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/userver"
    CACHE PATH "Path to the userver source checkout")

if(NOT EXISTS "${USERVER_SOURCE_DIR}/CMakeLists.txt")
    message(FATAL_ERROR
        "userver sources are missing. Run git submodule update --init --recursive "
        "or configure with -DUSERVER_SOURCE_DIR=/path/to/userver.")
endif()

add_subdirectory("${USERVER_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/userver")
userver_setup_environment()

add_subdirectory(services/minimal)
