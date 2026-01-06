import os
import subprocess
import shutil
import platform

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
LIB_DIR = os.path.join(ROOT_DIR, "lib")
TF_DIR = os.path.join(ROOT_DIR, "third_party", "tensorflow")

TFLITE_LIBS = [
    "libtensorflowlite.so",
    "libtensorflowlite_c.so",
    "libexternal_delegate.so",
]

TF_VERSION = "v2.19.0"


def tflite_available():
    if not os.path.isdir(LIB_DIR):
        return False
    return all(
        os.path.isfile(os.path.join(LIB_DIR, lib))
        for lib in TFLITE_LIBS
    )


def build_tflite():
    os.makedirs(LIB_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(TF_DIR), exist_ok=True)

    if not os.path.isdir(TF_DIR):
        print("Cloning TensorFlow...")
        subprocess.check_call(
            [
                "git",
                "clone",
                "--branch",
                TF_VERSION,
                "--depth",
                "1",
                "https://github.com/tensorflow/tensorflow.git",
                TF_DIR,
            ]
        )

    machine = platform.machine().lower()

    # Native ARM device
    if machine in ("aarch64", "arm64"):
        bazel_config = "linux"
    else:
        # Cross compile from x86_64
        bazel_config = "elinux_aarch64"


    env = os.environ.copy()
    env["TF_ENABLE_XLA"] = "0"

    def bazel_build(target):
        print(f"Building {target}")
        subprocess.check_call(
            [
                "bazelisk",
                "build",
                f"--config={bazel_config}",
                "-c",
                "opt",
                target,
            ],
            cwd=TF_DIR,
            env=env,
        )

    bazel_build("//tensorflow/lite:libtensorflowlite.so")
    bazel_build("//tensorflow/lite/c:libtensorflowlite_c.so")
    bazel_build("//tensorflow/lite/delegates/external:external_delegate")

    bazel_bin = os.path.join(TF_DIR, "bazel-bin")

    shutil.copy(
        os.path.join(bazel_bin, "tensorflow/lite/libtensorflowlite.so"),
        LIB_DIR,
    )
    shutil.copy(
        os.path.join(bazel_bin, "tensorflow/lite/c/libtensorflowlite_c.so"),
        LIB_DIR,
    )
    shutil.copy(
        os.path.join(
            bazel_bin,
            "tensorflow/lite/delegates/external/libexternal_delegate.so"
        ),
        LIB_DIR,
    )

    print("TensorFlow Lite build complete")


if __name__ == "__main__":
    if tflite_available():
        print("TensorFlow Lite already available")
    else:
        build_tflite()
