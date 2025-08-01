import pyrealsense2 as rs

ctx = rs.context()
devices = ctx.query_devices()
print(f"Found {len(devices)} device(s)")
for dev in devices:
    print("Device name:", dev.get_info(rs.camera_info.name))
    print("Serial number:", dev.get_info(rs.camera_info.serial_number))
