cmake_minimum_required(VERSION 3.15)
project(OCRProject)

find_package(Python3 REQUIRED COMPONENTS Interpreter)

add_custom_target(run
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_SOURCE_DIR}/src/main.py
)