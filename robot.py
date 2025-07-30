import json
from networktables import NetworkTables
import numpy as np
import logging

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

class NetworkTablesPublisher:
    def __init__(self, table_name="RealsenseVision", server="10.0.0.2"):
        print(f"Connecting to NetworkTables server at {server} with table {table_name}")
        NetworkTables.initialize(server=server)
        def connectionListener(connected, info):
            print(info, "; Connected=%s" % connected)
        NetworkTables.addConnectionListener(connectionListener, immediateNotify=True)
        self.table = NetworkTables.getTable(table_name)

    def publish_detections(self, detections):
        json_array = [json.dumps(det,cls=NumpyEncoder) for det in detections]
        self.table.putStringArray("detections", json_array)

    def clear(self):
        self.table.putStringArray("detections", [])
