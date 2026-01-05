from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os
import sys
import subprocess
from build_tflite import tflite_available, build_tflite

class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=''):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)

class CMakeBuild(build_ext):
    def build_extension(self, ext):
        if not tflite_available():
            print("TensorFlow Lite not found, building it now")
            build_tflite()

        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        
        # Required for auto-detection of auxiliary "native" libs
        if not extdir.endswith(os.path.sep):
            extdir += os.path.sep

        cmake_args = [
            f'-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}',
            f'-DPYTHON_EXECUTABLE={sys.executable}',
            '-DBUILD_PYTHON=ON',
        ]

        cfg = 'Debug' if self.debug else 'Release'
        build_args = ['--config', cfg]

        cmake_args += [f'-DCMAKE_BUILD_TYPE={cfg}']
        
        # Detect architecture for OpenCV download
        import platform
        machine = platform.machine().lower()
        if 'aarch64' in machine or 'arm64' in machine:
            opencv_arch = 'linuxarm64'
        elif 'x86_64' in machine or 'amd64' in machine:
            opencv_arch = 'linuxx86-64'
        else:
            opencv_arch = 'linuxx86-64'  # default
        
        cmake_args += [f'-DOPENCV_ARCH={opencv_arch}']

        # Add parallel build
        if hasattr(self, 'parallel') and self.parallel:
            build_args += [f'-j{self.parallel}']
        else:
            build_args += ['-j4']

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        # Configure
        subprocess.check_call(
            ['cmake', ext.sourcedir] + cmake_args,
            cwd=self.build_temp
        )
        
        # Build
        subprocess.check_call(
            ['cmake', '--build', '.'] + build_args,
            cwd=self.build_temp
        )

setup(
    name='rubik_detector',
    version='0.1.0',
    author='AdarWa,rakrakon',
    description='Tensorflow YOLOv11 wrapper for the Rubik Pi 3, utilizing its NPU',
    long_description='',
    ext_modules=[CMakeExtension('rubik_detector')],
    cmdclass={'build_ext': CMakeBuild},
    install_requires=[
        'pybind11>=2.6.0',
        'numpy>=1.19.0',
    ],
    python_requires='>=3.7',
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: C++',
    ],
)