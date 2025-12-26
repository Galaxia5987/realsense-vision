from app.config import ConfigManager
from app.core import logging_config

logger = logging_config.get_logger(__name__)


def _resolve_camera_type(camera_type) -> str:
    try:
        return camera_type.value
    except AttributeError:
        return str(camera_type)


def create_camera():
    config = ConfigManager().get()
    resolution_str = config.camera.resolution.value
    width, height = list(map(int, resolution_str.split("x")))
    camera_type = _resolve_camera_type(config.camera.type)

    if camera_type == "usb":
        from app.components.detection.usb_camera import UsbCamera

        return UsbCamera(
            width, height, config.camera.fps, device_index=config.camera.usb_device_index
        )

    if camera_type == "realsense":
        try:
            from app.components.detection.realsense_camera import RealSenseCamera
        except ImportError as exc:
            logger.error(f"Failed to import RealSense support: {exc}")
            return None

        return RealSenseCamera(width, height, config.camera.fps)

    logger.warning(f"Unknown camera type '{camera_type}', defaulting to realsense")
    try:
        from app.components.detection.realsense_camera import RealSenseCamera
    except ImportError as exc:
        logger.error(f"Failed to import RealSense support: {exc}")
        return None

    return RealSenseCamera(width, height, config.camera.fps)