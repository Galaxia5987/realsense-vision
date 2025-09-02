import json
import ntcore
import numpy as np
import logging
import struct
from wpimath.geometry import Pose3d, Translation3d, Rotation3d

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
        self.pose_pub = self.table.getStructTopic("pose", Pose3d).publish()
        # self.topic = self.table.getTopic("detection")
        # self.topic.publish()

    def publish_detections(self, detections):
        if not detections:
            self.clear()
            return
        x,y,z = detections[0]["point"]
        pose = Pose3d(
            Translation3d(x,y,z),
            Rotation3d(0.0, 0.0, 0)
        )

        self.pose_pub.set(pose)

    def clear(self):
        pass
