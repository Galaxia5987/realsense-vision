from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


DetectionOutput = tuple[np.ndarray, np.ndarray, np.ndarray]


class DetectorBase(ABC):
    @abstractmethod
    def detect(self, image) -> None:
        """Run detection on an image."""

    @abstractmethod
    def get_detections(self) -> Optional[DetectionOutput]:
        """Return detection results as (boxes, confs, classes)."""

    @abstractmethod
    def get_annotated_image(self):
        """Return an annotated image if supported by the detector."""
