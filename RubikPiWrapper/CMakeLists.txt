cmake_minimum_required(VERSION 3.10)
project(rubik_detector)
set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(ENABLE_ASAN)
    message(STATUS "BUILD WITH ADDRESS SANITIZER")
    set(CMAKE_C_FLAGS_DEBUG
        "${CMAKE_C_FLAGS_DEBUG} -fno-omit-frame-pointer -fsanitize=address -fsanitize=undefined"
    )
    set(CMAKE_CXX_FLAGS_DEBUG
        "${CMAKE_CXX_FLAGS_DEBUG} -fno-omit-frame-pointer -fsanitize=address -fsanitize=undefined"
    )
    set(CMAKE_LINKER_FLAGS_DEBUG
        "${CMAKE_LINKER_FLAGS_DEBUG} -fno-omit-frame-pointer -fsanitize=address -fsanitize=undefined"
    )
endif()

set(BUILD_SHARED_LIBS ON)

# Find Python
find_package(Python3 COMPONENTS Interpreter Development REQUIRED)
message(STATUS "Python3_INCLUDE_DIRS=${Python3_INCLUDE_DIRS}")
message(STATUS "Python3_LIBRARIES=${Python3_LIBRARIES}")

# Find pybind11
execute_process(
    COMMAND ${Python3_EXECUTABLE} -c "import pybind11; print(pybind11.get_cmake_dir())"
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    RESULT_VARIABLE PYBIND11_RESULT
)

if(PYBIND11_RESULT EQUAL 0)
    list(APPEND CMAKE_PREFIX_PATH ${PYBIND11_CMAKE_DIR})
    find_package(pybind11 REQUIRED)
    message(STATUS "Found pybind11: ${pybind11_INCLUDE_DIRS}")
else()
    message(FATAL_ERROR "pybind11 not found. Install with: pip install pybind11")
endif()

set(OPENCV_YEAR "frc2025")
set(OPENCV_VERSION "4.10.0-3")
set(OPENCV_TYPE "")

# Download opencv, and save the path
include(FetchContent)
FetchContent_Declare(
    opencv_lib
    URL
        https://frcmaven.wpi.edu/artifactory/release/edu/wpi/first/thirdparty/${OPENCV_YEAR}/opencv/opencv-cpp/${OPENCV_VERSION}/opencv-cpp-${OPENCV_VERSION}-${OPENCV_ARCH}${OPENCV_TYPE}.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(opencv_lib)

# Download OpenCV headers
FetchContent_Declare(
    opencv_header
    URL
        https://frcmaven.wpi.edu/artifactory/release/edu/wpi/first/thirdparty/${OPENCV_YEAR}/opencv/opencv-cpp/${OPENCV_VERSION}/opencv-cpp-${OPENCV_VERSION}-headers.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(opencv_header)

file(
    GLOB_RECURSE OPENCV_LIB_PATH
    "${opencv_lib_SOURCE_DIR}/**/*.lib"
    "${opencv_lib_SOURCE_DIR}/**/*.so*"
)
set(OPENCV_INCLUDE_PATH ${opencv_header_SOURCE_DIR})
message("Depending on opencv ${OPENCV_LIB_PATH}")

# Download TensorFlow Lite headers
FetchContent_Declare(
    tflite_header
    URL https://github.com/tensorflow/tensorflow/archive/refs/tags/v2.19.0.zip
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(tflite_header)

# Set TensorFlow Lite headers
set(TFLITE_INCLUDE_DIR
    "${tflite_header_SOURCE_DIR}"
    CACHE PATH
    "Path to TensorFlow Lite include directory"
)

# Set TensorFlow Lite library - use absolute path and verify it exists
set(LIB_PATH
    "${CMAKE_CURRENT_SOURCE_DIR}/lib/"
    CACHE FILEPATH
    "Path to TensorFlow Lite library"
)

# Check if the library path exists
if(NOT EXISTS ${LIB_PATH})
    message(WARNING "Library directory not found at: ${LIB_PATH}, will try system paths")
else()
    message(STATUS "Found library directory: ${LIB_PATH}")
endif()

set(CMAKE_INSTALL_RPATH "lib")
set(THREADS_PREFER_PTHREAD_FLAG ON)
find_package(Threads REQUIRED)

# Create Python module
pybind11_add_module(${PROJECT_NAME} src/rubik_python_wrapper.cpp)

target_link_libraries(
    ${PROJECT_NAME}
    PRIVATE
        Threads::Threads
        ${OPENCV_LIB_PATH}
)

# Link TensorFlow Lite libraries
if(EXISTS ${LIB_PATH})
    target_link_libraries(
        ${PROJECT_NAME}
        PRIVATE
            ${LIB_PATH}/libtensorflowlite_c.so
            ${LIB_PATH}/libtensorflowlite.so
            ${LIB_PATH}/libexternal_delegate.so
    )
else()
    # Try system libraries
    target_link_libraries(
        ${PROJECT_NAME}
        PRIVATE
            tensorflowlite_c
            tensorflowlite
    )
endif()

target_include_directories(
    ${PROJECT_NAME}
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}
        ${CMAKE_CURRENT_SOURCE_DIR}/include
        ${Python3_INCLUDE_DIRS}
        ${OPENCV_INCLUDE_PATH}
        ${TFLITE_INCLUDE_DIR}
)

set_target_properties(${PROJECT_NAME} PROPERTIES INSTALL_RPATH "\\\$ORIGIN/")

include(GNUInstallDirs)
install(TARGETS ${PROJECT_NAME} LIBRARY DESTINATION .)

# Install TensorFlow Lite libraries if they exist in LIB_PATH
if(EXISTS ${LIB_PATH})
    install(
        FILES
            ${LIB_PATH}/libtensorflowlite_c.so
            ${LIB_PATH}/libtensorflowlite.so
            ${LIB_PATH}/libexternal_delegate.so
        DESTINATION .
        OPTIONAL
    )
endif()

find_program(PYBIND11_STUBGEN pybind11-stubgen REQUIRED)

add_custom_command(
    TARGET ${PROJECT_NAME}
    POST_BUILD
    COMMAND
        ${Python3_EXECUTABLE} -m pybind11_stubgen
            ${PROJECT_NAME}
            -o ${CMAKE_CURRENT_BINARY_DIR}/stubs
    WORKING_DIRECTORY
        $<TARGET_FILE_DIR:${PROJECT_NAME}>
    COMMENT "Generating Python type stubs for ${PROJECT_NAME}"
)

install(
    DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/stubs/${PROJECT_NAME}
    DESTINATION .
)
