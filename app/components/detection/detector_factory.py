from app.config import ConfigManager
from app.core import logging_config
from app.components.detection.detector_base import DetectorBase
from models.models import ChipType

logger = logging_config.get_logger(__name__)


def create_detector(model_path: str, imgsz: int = 640) -> DetectorBase:
    chip_type = ConfigManager().get().chip_type

    if chip_type == ChipType.qcs6490:
        from app.components.detection.rubik_detector import RubikDetector

        return RubikDetector(model_path)

    if chip_type == ChipType.rk3588:
        from app.components.detection.detector import YOLODetector

        return YOLODetector(model_path, imgsz=imgsz)

    logger.warning(
        f"Unknown chip_type {chip_type}, defaulting to RKNN detector",
        operation="init",
    )
    from app.components.detection.detector import YOLODetector

    return YOLODetector(model_path, imgsz=imgsz)
