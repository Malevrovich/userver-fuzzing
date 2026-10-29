# Keep pinned dependency headers ahead of broad Homebrew include paths.
# Installed gRPC and the userver checkout are untouched.
if(APPLE AND TARGET grpc)
    get_target_property(grpc_source_dir grpc SOURCE_DIR)
    if(TARGET libprotobuf AND TARGET absl_strings)
        get_target_property(protobuf_source_dir libprotobuf SOURCE_DIR)
        get_target_property(absl_source_dir absl_strings SOURCE_DIR)
        get_filename_component(absl_source_dir "${absl_source_dir}/../.." ABSOLUTE)
        # Broad Homebrew include directories otherwise shadow pinned headers.
        foreach(target grpc grpc++ grpcpp_channelz userver-grpc-internal userver-grpc-proto ${PROJECT_NAME}_objs ${PROJECT_NAME}_proto ${PROJECT_NAME})
            if(TARGET ${target})
                get_target_property(target_type ${target} TYPE)
                if(target_type STREQUAL "INTERFACE_LIBRARY")
                    set(include_scope INTERFACE)
                else()
                    set(include_scope PRIVATE)
                endif()
                target_include_directories(${target} SYSTEM BEFORE ${include_scope}
                    "${grpc_source_dir}/include" "${protobuf_source_dir}/src" "${absl_source_dir}")
            endif()
        endforeach()
    endif()
endif()
