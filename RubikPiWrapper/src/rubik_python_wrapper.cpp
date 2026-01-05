/*
 * Python wrapper for RubikDetector using pybind11
 * 
 * Build with:
 * g++ -O3 -Wall -shared -std=c++11 -fPIC \
 *   $(python3 -m pybind11 --includes) \
 *   rubik_python_wrapper.cpp -o rubik_detector$(python3-config --extension-suffix) \
 *   -ltensorflowlite_c -lopencv_core -lopencv_imgproc
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <tensorflow/lite/c/c_api.h>
#include <tensorflow/lite/c/c_api_experimental.h>
#include <tensorflow/lite/delegates/external/external_delegate.h>

#include <opencv2/imgproc.hpp>
#include <opencv2/opencv.hpp>

#include <algorithm>
#include <memory>
#include <vector>
#include <cstring>

namespace py = pybind11;

// Debug print macro
#ifndef NDEBUG
#define DEBUG_PRINT(...) std::printf(__VA_ARGS__)
#else
#define DEBUG_PRINT(...) do {} while (0)
#endif

// Structure definitions
struct BoxRect {
    int left;
    int right;
    int top;
    int bottom;
};

struct DetectionResult {
    int id;
    BoxRect box;
    float confidence;
    
    // Constructor
    DetectionResult(int id, const BoxRect& box, float conf)
        : id(id), box(box), confidence(conf) {}
};

// Helper function for dequantization
static inline float get_dequant_value(void *data, TfLiteType tensor_type,
                                      int idx, float zero_point, float scale) {
    switch (tensor_type) {
        case kTfLiteUInt8:
            return (static_cast<uint8_t*>(data)[idx] - zero_point) * scale;
        case kTfLiteFloat32:
            return static_cast<float*>(data)[idx];
        default:
            break;
    }
    return 0.0f;
}

// Helper function to get tensor image dimensions
bool tensor_image_dims(const TfLiteTensor *tensor, int *w, int *h, int *c) {
    int n = TfLiteTensorNumDims(tensor);
    int cursor = 0;

    for (int i = 0; i < n; i++) {
        int dim = TfLiteTensorDim(tensor, i);
        if (dim == 0) return false;
        if (dim == 1) continue;

        switch (cursor++) {
            case 0: if (w) *w = dim; break;
            case 1: if (h) *h = dim; break;
            case 2: if (c) *c = dim; break;
            default: return false;
        }
    }

    if (cursor < 2) return false;
    if (cursor == 2 && c) *c = 1;
    if (*c > 4) return false;
    return true;
}

// IoU calculation
inline float calculateIoU(const BoxRect &box1, const BoxRect &box2) {
    const int x1 = std::max(box1.left, box2.left);
    const int y1 = std::max(box1.top, box2.top);
    const int x2 = std::min(box1.right, box2.right);
    const int y2 = std::min(box1.bottom, box2.bottom);

    if (x2 <= x1 || y2 <= y1) return 0.0f;

    const int intersectionArea = (x2 - x1) * (y2 - y1);
    const int area1 = (box1.right - box1.left) * (box1.bottom - box1.top);
    const int area2 = (box2.right - box2.left) * (box2.bottom - box2.top);

    return static_cast<float>(intersectionArea) / (area1 + area2 - intersectionArea);
}

// Non-Maximum Suppression
std::vector<DetectionResult> optimizedNMS(std::vector<DetectionResult> &candidates, 
                                          float nmsThreshold) {
    if (candidates.empty()) return {};

    std::sort(candidates.begin(), candidates.end(),
              [](const DetectionResult &a, const DetectionResult &b) {
                  return a.confidence > b.confidence;
              });

    std::vector<DetectionResult> results;
    results.reserve(candidates.size() / 4);
    std::vector<bool> suppressed(candidates.size(), false);

    for (size_t i = 0; i < candidates.size(); ++i) {
        if (suppressed[i]) continue;

        results.push_back(candidates[i]);
        const auto &currentBox = candidates[i];

        for (size_t j = i + 1; j < candidates.size(); ++j) {
            if (suppressed[j] || candidates[j].id != currentBox.id) continue;

            if (calculateIoU(currentBox.box, candidates[j].box) > nmsThreshold) {
                suppressed[j] = true;
            }
        }
    }

    return results;
}

cv::Mat letterbox(const cv::Mat& img, int target_size = 640) {
    int original_h = img.rows;
    int original_w = img.cols;

    // Compute scaling factor
    float scale = static_cast<float>(target_size) / std::max(original_h, original_w);

    int new_w = static_cast<int>(original_w * scale);
    int new_h = static_cast<int>(original_h * scale);

    // Resize the image
    cv::Mat resized;
    cv::resize(img, resized, cv::Size(new_w, new_h));

    // Create a square black image
    cv::Mat output = cv::Mat::zeros(cv::Size(target_size, target_size), img.type());

    // Compute top-left corner to place the resized image
    int top = (target_size - new_h) / 2;
    int left = (target_size - new_w) / 2;

    // Copy resized image into the square canvas
    resized.copyTo(output(cv::Rect(left, top, new_w, new_h)));

    return output;
}

// Main RubikDetector class
class RubikDetector {
private:
    TfLiteInterpreter *interpreter;
    TfLiteDelegate *delegate;
    TfLiteModel *model;
    bool use_delegate;

public:
    RubikDetector(const std::string& model_path, bool use_qnn_delegate = true) 
        : interpreter(nullptr), delegate(nullptr), model(nullptr), 
          use_delegate(use_qnn_delegate) {
        
        // Load model
        model = TfLiteModelCreateFromFile(model_path.c_str());
        if (!model) {
            throw std::runtime_error("Failed to load model file: " + model_path);
        }
        DEBUG_PRINT("INFO: Loaded model file '%s'\n", model_path.c_str());

        // Create interpreter options
        TfLiteInterpreterOptions *interpreterOpts = TfLiteInterpreterOptionsCreate();
        if (!interpreterOpts) {
            TfLiteModelDelete(model);
            throw std::runtime_error("Failed to create interpreter options");
        }

        // Optionally create and add delegate
        if (use_delegate) {
            TfLiteExternalDelegateOptions delegateOptsValue =
                TfLiteExternalDelegateOptionsDefault("libQnnTFLiteDelegate.so");
            TfLiteExternalDelegateOptions *delegateOpts = &delegateOptsValue;

            TfLiteExternalDelegateOptionsInsert(delegateOpts, "backend_type", "htp");
            TfLiteExternalDelegateOptionsInsert(delegateOpts, "htp_use_conv_hmx", "1");
            TfLiteExternalDelegateOptionsInsert(delegateOpts, "htp_performance_mode", "2");

            delegate = TfLiteExternalDelegateCreate(delegateOpts);
            if (delegate) {
                TfLiteInterpreterOptionsAddDelegate(interpreterOpts, delegate);
                DEBUG_PRINT("INFO: Created and added QNN delegate\n");
            } else {
                DEBUG_PRINT("WARNING: Failed to create delegate, continuing without it\n");
            }
        }

        // Create interpreter
        interpreter = TfLiteInterpreterCreate(model, interpreterOpts);
        TfLiteInterpreterOptionsDelete(interpreterOpts);

        if (!interpreter) {
            if (delegate) TfLiteExternalDelegateDelete(delegate);
            TfLiteModelDelete(model);
            throw std::runtime_error("Failed to create interpreter");
        }

        // Modify graph with delegate if available
        if (delegate) {
            if (TfLiteInterpreterModifyGraphWithDelegate(interpreter, delegate) != kTfLiteOk) {
                DEBUG_PRINT("WARNING: Failed to modify graph with delegate\n");
            }
        }

        // Allocate tensors
        if (TfLiteInterpreterAllocateTensors(interpreter) != kTfLiteOk) {
            TfLiteInterpreterDelete(interpreter);
            if (delegate) TfLiteExternalDelegateDelete(delegate);
            TfLiteModelDelete(model);
            throw std::runtime_error("Failed to allocate tensors");
        }

        DEBUG_PRINT("INFO: TensorFlow Lite initialization completed successfully\n");
    }

    ~RubikDetector() {
        if (interpreter) TfLiteInterpreterDelete(interpreter);
        if (delegate) TfLiteExternalDelegateDelete(delegate);
        if (model) TfLiteModelDelete(model);
        DEBUG_PRINT("INFO: RubikDetector destroyed\n");
    }

    std::vector<DetectionResult> detect(py::array_t<uint8_t> image, 
                                       double box_threshold = 0.5,
                                       double nms_threshold = 0.45) {
        // Get image info
        py::buffer_info buf = image.request();
        
        if (buf.ndim != 3) {
            throw std::runtime_error("Image must be 3-dimensional (H, W, C)");
        }

        int img_h = buf.shape[0];
        int img_w = buf.shape[1];
        int img_c = buf.shape[2];

        // Get input tensor dimensions
        TfLiteTensor *input = TfLiteInterpreterGetInputTensor(interpreter, 0);
        int in_w, in_h, in_c;
        if (!tensor_image_dims(input, &in_w, &in_h, &in_c)) {
            throw std::runtime_error("Invalid input tensor shape");
        }
    

        // Convert BGR to RGB if needed (assuming input is BGR like OpenCV)
        cv::Mat img_mat(img_h, img_w, CV_8UC3, buf.ptr);
        cv::Mat rgb;
        cv::cvtColor(img_mat, rgb, cv::COLOR_BGR2RGB);
        if (img_w != in_w || img_h != in_h) {
            img_mat = letterbox(img_mat, in_w);
        }

        // Copy to input tensor
        std::memcpy(TfLiteTensorData(input), rgb.data, TfLiteTensorByteSize(input));

        // Run inference
        if (TfLiteInterpreterInvoke(interpreter) != kTfLiteOk) {
            throw std::runtime_error("Interpreter invocation failed");
        }

        // Get output tensors
        const TfLiteTensor *boxesTensor = TfLiteInterpreterGetOutputTensor(interpreter, 0);
        const TfLiteTensor *scoresTensor = TfLiteInterpreterGetOutputTensor(interpreter, 1);
        const TfLiteTensor *classesTensor = TfLiteInterpreterGetOutputTensor(interpreter, 2);

        const TfLiteQuantizationParams boxesParams = TfLiteTensorQuantizationParams(boxesTensor);
        const TfLiteQuantizationParams scoresParams = TfLiteTensorQuantizationParams(scoresTensor);

        const int numBoxes = TfLiteTensorDim(boxesTensor, 1);

        uint8_t *boxesData = static_cast<uint8_t*>(TfLiteTensorData(boxesTensor));
        uint8_t *scoresData = static_cast<uint8_t*>(TfLiteTensorData(scoresTensor));
        uint8_t *classesData = static_cast<uint8_t*>(TfLiteTensorData(classesTensor));

        std::vector<DetectionResult> candidateResults;

        for (int i = 0; i < numBoxes; ++i) {
            float score = get_dequant_value(scoresData, kTfLiteUInt8, i, 
                                           scoresParams.zero_point, scoresParams.scale);
            if (score < box_threshold) continue;

            int classId = classesData[i];

            uint8_t raw_x_1_u8 = boxesData[i * 4 + 0];
            uint8_t raw_y_1_u8 = boxesData[i * 4 + 1];
            uint8_t raw_x_2_u8 = boxesData[i * 4 + 2];
            uint8_t raw_y_2_u8 = boxesData[i * 4 + 3];

            float x1 = get_dequant_value(&raw_x_1_u8, kTfLiteUInt8, 0, 
                                        boxesParams.zero_point, boxesParams.scale);
            float y1 = get_dequant_value(&raw_y_1_u8, kTfLiteUInt8, 0, 
                                        boxesParams.zero_point, boxesParams.scale);
            float x2 = get_dequant_value(&raw_x_2_u8, kTfLiteUInt8, 0, 
                                        boxesParams.zero_point, boxesParams.scale);
            float y2 = get_dequant_value(&raw_y_2_u8, kTfLiteUInt8, 0, 
                                        boxesParams.zero_point, boxesParams.scale);

            float clamped_x1 = std::max(0.0f, std::min(x1, static_cast<float>(img_w)));
            float clamped_y1 = std::max(0.0f, std::min(y1, static_cast<float>(img_h)));
            float clamped_x2 = std::max(0.0f, std::min(x2, static_cast<float>(img_w)));
            float clamped_y2 = std::max(0.0f, std::min(y2, static_cast<float>(img_h)));

            if (clamped_x1 >= clamped_x2 || clamped_y1 >= clamped_y2) continue;

            BoxRect box;
            box.left = static_cast<int>(std::round(clamped_x1));
            box.top = static_cast<int>(std::round(clamped_y1));
            box.right = static_cast<int>(std::round(clamped_x2));
            box.bottom = static_cast<int>(std::round(clamped_y2));

            candidateResults.emplace_back(classId, box, score);
        }

        return optimizedNMS(candidateResults, static_cast<float>(nms_threshold));
    }

    bool is_quantized() {
        TfLiteTensor *input = TfLiteInterpreterGetInputTensor(interpreter, 0);
        if (!input) return false;
        return TfLiteTensorType(input) == kTfLiteUInt8;
    }

    std::tuple<int, int, int> get_input_shape() {
        TfLiteTensor *input = TfLiteInterpreterGetInputTensor(interpreter, 0);
        int w, h, c;
        if (!tensor_image_dims(input, &w, &h, &c)) {
            throw std::runtime_error("Failed to get input dimensions");
        }
        return std::make_tuple(h, w, c);
    }
};

// Pybind11 module definition
PYBIND11_MODULE(rubik_detector, m) {
    m.doc() = "Python wrapper for RubikDetector TensorFlow Lite inference";

    py::class_<BoxRect>(m, "BoxRect")
        .def(py::init<>())
        .def_readwrite("left", &BoxRect::left)
        .def_readwrite("right", &BoxRect::right)
        .def_readwrite("top", &BoxRect::top)
        .def_readwrite("bottom", &BoxRect::bottom)
        .def("__repr__", [](const BoxRect &b) {
            return "BoxRect(left=" + std::to_string(b.left) + 
                   ", top=" + std::to_string(b.top) +
                   ", right=" + std::to_string(b.right) + 
                   ", bottom=" + std::to_string(b.bottom) + ")";
        });

    py::class_<DetectionResult>(m, "DetectionResult")
        .def(py::init<int, const BoxRect&, float>())
        .def_readwrite("id", &DetectionResult::id)
        .def_readwrite("box", &DetectionResult::box)
        .def_readwrite("confidence", &DetectionResult::confidence)
        .def("__repr__", [](const DetectionResult &d) {
            return "DetectionResult(id=" + std::to_string(d.id) + 
                   ", confidence=" + std::to_string(d.confidence) + ")";
        });

    py::class_<RubikDetector>(m, "RubikDetector")
        .def(py::init<const std::string&, bool>(),
             py::arg("model_path"),
             py::arg("use_qnn_delegate") = true,
             "Initialize RubikDetector with model path")
        .def("detect", &RubikDetector::detect,
             py::arg("image"),
             py::arg("box_threshold") = 0.5,
             py::arg("nms_threshold") = 0.45,
             "Detect objects in image. Image should be numpy array (H, W, C) in BGR format.")
        .def("is_quantized", &RubikDetector::is_quantized,
             "Check if the model is quantized")
        .def("get_input_shape", &RubikDetector::get_input_shape,
             "Get expected input shape (height, width, channels)");
}