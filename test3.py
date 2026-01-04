import tensorflow as tf

# Load the saved_model
converter = tf.lite.TFLiteConverter.from_saved_model('./best_saved_model')

# Enable quantization
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# Provide representative dataset for calibration
converter.representative_dataset = representative_dataset_gen

# Force UINT8 quantization for inputs and outputs
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
converter.inference_input_type = tf.uint8
converter.inference_output_type = tf.uint8

# Convert
print("Converting to UINT8 quantized TFLite...")
tflite_quant_model = converter.convert()

# Save
output_path = 'best_uint8.tflite'
with open(output_path, 'wb') as f:
    f.write(tflite_quant_model)

print(f"✓ UINT8 quantized model saved to: {output_path}")

# Get model size
import os
size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"Model size: {size_mb:.2f} MB")