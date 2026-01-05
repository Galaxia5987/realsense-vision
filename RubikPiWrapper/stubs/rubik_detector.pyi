"""
Python wrapper for RubikDetector TensorFlow Lite inference
"""
from __future__ import annotations
import numpy
import numpy.typing
import typing
__all__: list[str] = ['BoxRect', 'DetectionResult', 'RubikDetector']
class BoxRect:
    def __init__(self) -> None:
        ...
    def __repr__(self) -> str:
        ...
    @property
    def bottom(self) -> int:
        ...
    @bottom.setter
    def bottom(self, arg0: typing.SupportsInt) -> None:
        ...
    @property
    def left(self) -> int:
        ...
    @left.setter
    def left(self, arg0: typing.SupportsInt) -> None:
        ...
    @property
    def right(self) -> int:
        ...
    @right.setter
    def right(self, arg0: typing.SupportsInt) -> None:
        ...
    @property
    def top(self) -> int:
        ...
    @top.setter
    def top(self, arg0: typing.SupportsInt) -> None:
        ...
class DetectionResult:
    box: BoxRect
    def __init__(self, arg0: typing.SupportsInt, arg1: BoxRect, arg2: typing.SupportsFloat) -> None:
        ...
    def __repr__(self) -> str:
        ...
    @property
    def confidence(self) -> float:
        ...
    @confidence.setter
    def confidence(self, arg0: typing.SupportsFloat) -> None:
        ...
    @property
    def id(self) -> int:
        ...
    @id.setter
    def id(self, arg0: typing.SupportsInt) -> None:
        ...
class RubikDetector:
    def __init__(self, model_path: str, use_qnn_delegate: bool = True) -> None:
        """
        Initialize RubikDetector with model path
        """
    def detect(self, image: typing.Annotated[numpy.typing.ArrayLike, numpy.uint8], box_threshold: typing.SupportsFloat = 0.5, nms_threshold: typing.SupportsFloat = 0.45) -> list[DetectionResult]:
        """
        Detect objects in image. Image should be numpy array (H, W, C) in BGR format.
        """
    def get_input_shape(self) -> tuple[int, int, int]:
        """
        Get expected input shape (height, width, channels)
        """
    def is_quantized(self) -> bool:
        """
        Check if the model is quantized
        """
