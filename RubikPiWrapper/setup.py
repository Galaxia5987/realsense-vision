from setuptools import setup, Extension
import os
import sys
import subprocess
import glob

# Import pybind11 - will fail with clear error if not installed
try:
    import pybind11
except ImportError:
    raise ImportError(
        "pybind11 is required to build this package. "
        "Install it with: pip install pybind11"
    )

def find_opencv_include():
    """Try to find OpenCV include directory."""
    candidates = [
        "/usr/include/opencv4",
        "/usr/local/include/opencv4",
        "/opt/homebrew/include/opencv4",  # macOS ARM
        "/usr/local/opt/opencv/include/opencv4",  # macOS Intel
    ]
    
    # Try pkg-config first
    try:
        result = subprocess.run(
            ['pkg-config', '--cflags-only-I', 'opencv4'],
            capture_output=True, text=True, check=True
        )
        path = result.stdout.strip().replace('-I', '')
        if path and os.path.exists(path):
            return path
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Fall back to candidates
    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError("OpenCV headers not found!")

def find_opencv_libs():
    """Try to find OpenCV library directory."""
    candidates = [
        "/usr/local/lib",
        "/usr/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",  # ARM64
        "/opt/homebrew/lib",
    ]
    
    for path in candidates:
        if os.path.exists(path):
            return path
    
    raise FileNotFoundError("OpenCV shared libraries not found!")

def find_tflite_include(base_path):
    """Try to find TensorFlow Lite include directory."""
    candidates = [
        os.path.join(base_path, "include"),
        os.path.join(base_path, "tensorflow"),  # If tensorflow is at the root
        base_path,  # If headers are directly in base_path
    ]
    
    # Check if tensorflow/lite/c/c_api.h exists in any candidate
    for candidate in candidates:
        test_path = os.path.join(candidate, "tensorflow", "lite", "c", "c_api.h")
        if os.path.exists(test_path):
            print(f"Found TensorFlow Lite headers in: {candidate}")
            return candidate
    
    raise FileNotFoundError("Tensorflow Lite headers not found!")

def find_tflite_lib(base_path):
    """Try to find TensorFlow Lite library directory and library name."""
    lib_dirs = [
        os.path.join(base_path, "lib"),
        os.path.join(base_path, "libs"),
        os.path.join(base_path, "lib64"),
        base_path,
    ]
    
    # Possible library names (in order of preference)
    lib_patterns = [
        "libtensorflowlite_c.so*",
        "libtensorflowlite_c.a",
        "libtensorflowlite.so*",
        "libtensorflowlite.a",
        "libtensorflow-lite.so*",
        "libtensorflow-lite.a",
    ]
    
    for lib_dir in lib_dirs:
        if not os.path.exists(lib_dir):
            continue
            
        for pattern in lib_patterns:
            matches = glob.glob(os.path.join(lib_dir, pattern))
            if matches:
                # Extract library name without 'lib' prefix and extension
                lib_file = os.path.basename(matches[0])
                if lib_file.startswith('lib'):
                    lib_name = lib_file[3:].split('.')[0]
                    print(f"Found TensorFlow Lite library: {matches[0]}")
                    print(f"Using library name: {lib_name}")
                    return lib_dir, lib_name
    
    # If we get here, library not found
    print(f"ERROR: Could not find TensorFlow Lite library in {base_path}")
    print("Searched in:")
    for lib_dir in lib_dirs:
        print(f"  - {lib_dir}")
    print("Searched for patterns:", lib_patterns)
    raise FileNotFoundError("TensorFlow Lite library not found!")

# Configure paths
TFLITE_PATH = os.path.expanduser(
    os.environ.get('TFLITE_PATH', '~/tflite')
)

# Verify TFLite path exists
if not os.path.exists(TFLITE_PATH):
    raise FileNotFoundError(
        f"TFLite path not found: {TFLITE_PATH}\n"
        "Set TFLITE_PATH environment variable to your TensorFlow Lite installation.\n"
        "Example: export TFLITE_PATH=/path/to/tflite"
    )

print(f"Using TFLite path: {TFLITE_PATH}")

# Find all required paths
OPENCV_INCLUDE = os.environ.get('OPENCV_INCLUDE', find_opencv_include())
OPENCV_LIB = find_opencv_libs()
TFLITE_INCLUDE = find_tflite_include(TFLITE_PATH)
TFLITE_LIB_DIR, TFLITE_LIB_NAME = find_tflite_lib(TFLITE_PATH)

# Platform-specific settings
extra_link_args = []
if sys.platform == 'darwin':  # macOS
    extra_link_args.extend(['-Wl,-rpath,@loader_path'])
elif sys.platform == 'linux':
    extra_link_args.extend([
        '-Wl,-rpath,$ORIGIN',
        f'-Wl,-rpath,{TFLITE_LIB_DIR}'
    ])

# Define extension module
ext_modules = [
    Extension(
        'rubik_detector',
        sources=['src/rubik_python_wrapper.cpp'],
        include_dirs=[
            pybind11.get_include(),
            OPENCV_INCLUDE,
            TFLITE_INCLUDE,  # TensorFlow Lite headers
        ],
        libraries=[
            TFLITE_LIB_NAME,  # Dynamically detected library name
            'opencv_core',
            'opencv_imgproc',
            'opencv_imgcodecs',  # often needed for image I/O
        ],
        library_dirs=[
            TFLITE_LIB_DIR,
            OPENCV_LIB,
            "/usr/local/lib",
            "/usr/lib",
        ],
        language='c++',
        extra_compile_args=['-std=c++11', '-O3', '-Wall', '-fPIC'],
        extra_link_args=extra_link_args,
    ),
]

setup(
    name='rubik_detector',
    version='0.1.0',
    author='AdarWa,rakrakon',
    description='Tensorflow YOLOv11 wrapper for the Rubik Pi 3, utilizing its NPU',
    ext_modules=ext_modules,
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