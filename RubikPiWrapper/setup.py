from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os
import sys
import subprocess
import shutil
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

        import platform
        machine = platform.machine().lower()
        opencv_arch = 'linuxarm64' if 'aarch64' in machine or 'arm64' in machine else 'linuxx86-64'
        cmake_args += [f'-DOPENCV_ARCH={opencv_arch}']

        if hasattr(self, 'parallel') and self.parallel:
            build_args += [f'-j{self.parallel}']
        else:
            build_args += ['-j4']

        os.makedirs(self.build_temp, exist_ok=True)

        # Configure and build
        subprocess.check_call(['cmake', ext.sourcedir] + cmake_args, cwd=self.build_temp)
        subprocess.check_call(['cmake', '--build', '.'] + build_args, cwd=self.build_temp)

        # Copy stub next to the .so
        stub_src = os.path.join(self.build_temp, 'stubs', f'{ext.name}.pyi')
        if os.path.exists(stub_src):
            stub_dst = os.path.join(extdir, f'{ext.name}.pyi')
            shutil.copy(stub_src, stub_dst)
            print(f"Copied stub {stub_src} -> {stub_dst}")

setup(
    name='rubik_detector',
    version='0.1.0',
    author='AdarWa,rakrakon',
    description='Tensorflow YOLOv11 wrapper for the Rubik Pi 3, utilizing its NPU',
    ext_modules=[CMakeExtension('rubik_detector')],
    cmdclass={'build_ext': CMakeBuild},
    install_requires=[
        'pybind11>=2.6.0',
        'numpy>=1.19.0',
    ],
    python_requires='>=3.7',
    zip_safe=False,
    data_files=[('', ['stubs/rubik_detector.pyi'])],  # installs the stub next to the module
)
