import json

import numpy as np

import app.core.logging_config as logging_config
from app.components.retry_utils import retry_with_backoff
from app.config import ConfigManager
from utils import singleton

logger = logging_config.get_logger(__name__)
NTCORE = True
try:
    import ntcore
    from wpimath.geometry import Pose3d, Rotation3d, Translation3d
except ImportError:
    logger.warning("Cannot import robotpy libraries - skipping...")
    NTCORE = False


class NumpyEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, np.ndarray):
            return o.tolist()
        elif isinstance(o, (np.integer,)):
            return int(o)
        elif isinstance(o, (np.floating,)):
            return float(o)
        elif isinstance(o, (np.bool_)):
            return bool(o)
        return super().default(o)


@singleton
class NetworkTablesPublisher:
    def __init__(self):
        if not NTCORE:
            return
        config = ConfigManager().get()

        table_name = config.network_tables.table
        server = config.network_tables.server

        logger.info(
            f"Initializing NetworkTables connection to {server} with table {table_name}",
            operation="init",
            status="starting",
        )
        try:
            self._initialize_connection(table_name, server)
            self.connected = True
            self.publish_count = 0
            self.error_count = 0

            logger.info(
                "NetworkTables initialized successfully",
                operation="init",
                status="success",
            )
        except Exception as e:
            self.connected = False
            logger.exception(
                f"Failed to initialize NetworkTables: {e}", operation="init"
            )
            raise

    @retry_with_backoff(max_attempts=3, initial_delay=1.0)
    def _initialize_connection(self, table_name, server):
        """Initialize NetworkTables connection with retry logic."""
        if not NTCORE:
            return
        logger.debug("Creating NetworkTables instance", operation="init_connection")

        self.inst = ntcore.NetworkTableInstance.getDefault()
        self.inst.startClient4(table_name)
        self.inst.setServer(server)

        logger.debug(
            f"NetworkTables client started for server {server}",
            operation="init_connection",
        )

        self.table = self.inst.getTable(table_name)
        logger.debug(
            f"NetworkTables table '{table_name}' acquired", operation="init_connection"
        )

        # Struct array publisher instead of single struct
        self.pose_pub = self.table.getStructArrayTopic("poses", Pose3d).publish()
        logger.debug("Pose publisher created", operation="init_connection")

    def publish_detections(self, detections):
        """Publish detection results to NetworkTables with error handling."""
        if not NTCORE:
            return
        try:
            if not detections:
                self.clear()
                return

            poses = []
            for i, det in enumerate(detections):
                try:
                    y, z, x = det["point"]  # your order
                    pose = Pose3d(Translation3d(x, y, -z), Rotation3d(0.0, 0.0, 0.0))
                    poses.append(pose)
                except Exception as e:
                    logger.warning(
                        f"Failed to create pose for detection {i}: {e}",
                        operation="publish_detections",
                    )

            # Publish as struct array
            if poses:
                self.pose_pub.set(poses)
                self.publish_count += 1

                if self.publish_count % 30 == 0:  # Log every 30 publishes
                    logger.debug(
                        f"Published {len(poses)} detections (total publishes: {self.publish_count})",
                        operation="publish_detections",
                    )
            else:
                self.clear()

        except Exception as e:
            self.error_count += 1
            logger.error(
                f"Error publishing detections: {e}", operation="publish_detections"
            )

    def clear(self):
        """Clear published detections."""
        if not NTCORE:
            return
        try:
            # Publish an empty array
            self.pose_pub.set([])
        except Exception as e:
            logger.warning(f"Error clearing detections: {e}", operation="clear")
