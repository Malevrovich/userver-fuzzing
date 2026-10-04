project(minimal-service LANGUAGES CXX)

add_executable(${PROJECT_NAME} src/main.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE userver::core)

userver_testsuite_add_simple()
