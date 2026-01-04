from setuptools import setup, Extension
import pybind11
import os

# Adjust these paths based on your installation
TFLITE_PATH = os.path.expanduser("~/tflite")  # or your TFLite installation path
OPENCV_INCLUDE = "/usr/include/opencv4"  # or "/usr/local/include/opencv4" on macOS

ext_modules = [
    Extension(
        'rubik_detector',
        sources=['src/rubik_python_wrapper.cpp'],
        include_dirs=[
            pybind11.get_include(),
            OPENCV_INCLUDE,
            f"{TFLITE_PATH}/include",
        ],
        libraries=['tensorflowlite_c', 'opencv_core', 'opencv_imgproc'],
        library_dirs=[
            f"{TFLITE_PATH}/lib",
            "/usr/local/lib",
            "/usr/lib",
        ],
        language='c++',
        extra_compile_args=['-std=c++11', '-O3', '-Wall'],
        extra_link_args=['-Wl,-rpath,' + f"{TFLITE_PATH}/lib"],
    ),
]

setup(
    name='rubik_detector',
    version='0.1.0',
    ext_modules=ext_modules,
    install_requires=['pybind11>=2.6.0', 'numpy'],
    zip_safe=False,
)