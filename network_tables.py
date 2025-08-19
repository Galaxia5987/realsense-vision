import json
import ntcore
from wpimath.geometry import Pose3d, Rotation3d, Translation3d
import numpy as np
import logging

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer,)):
            return int(obj)
        elif isinstance(obj, (np.floating,)):
            return float(obj)
        elif isinstance(obj, (np.bool_)):
            return bool(obj)
        return super().default(obj)

class NetworkTablesPublisher:
    def __init__(self, table_name="RealsenseVision", server="10.0.0.2"):
        logging.info(f"Connecting to NetworkTables server at {server} with table {table_name}")
        
        self.inst = ntcore.NetworkTableInstance.getDefault()
        self.inst.startClient4("RealsenseVision")
        self.inst.setServer(server)
        self.table = self.inst.getTable(table_name)
        self.topic = self.table.getTopic("detection")

    def publish_detections(self, detections):
        if not detections:
            self.clear()
            return
        x,y,z = detections[0]["point"]
        self.topic.genericPublishEx("raw",
            {
                "translation": {
                    "x": x,
                    "y": y,
                    "z": z
                }
            }
        )

    def clear(self):
        # self.topic.=
        pass
