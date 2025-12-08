import os

from rknn.api import RKNN

os.chdir("./calibration_images")
rknn = RKNN()
# rknn.config(
#     mean_values=[[0, 0, 0]],
#     std_values=[[255, 255, 255]],
#     target_platform='rk3588',
#     quantized_dtype='asymmetric_quantized-8',
#     optimization_level=3,
#     quantized_algorithm='normal',
#     quantized_method='channel',
# )

rknn.config(
    mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]], target_platform="rk3588"
)

# Load ONNX model
rknn.load_onnx(model="../uploads/best.onnx")
# rknn.build(do_quantization=True, dataset="./dataset_small.txt")
rknn.build(do_quantization=False)
# Export RKNN model
rknn.export_rknn("../uploads/balls_rknn_optimized_v2.rknn")
print("Hybrid quantized RKNN model saved at: uploads/balls_rknn_optimized.rknn")
