import cv2
import numpy as np

def frames_to_jpeg_bytes(frame, resolution=(640, 480)):
    resized = cv2.resize(frame, resolution)
    ret, jpeg = cv2.imencode('.jpg', resized)
    if not ret:
        return None
    return jpeg.tobytes()

def unflatten_dict(flat, sep='.'):
    result = {}
    for key, value in flat.items():
        parts = key.split(sep)
        d = result
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = value
    return result


def flatten_with_types(d, parent_key='', sep='.'):
    items = {}
    for k, v in d.items():
        full_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            # Handle enum case separately
            if 'enum' in v and 'value' in v and isinstance(v['enum'], list):
                items[full_key + '.value'] = type(v['value'])
            else:
                items.update(flatten_with_types(v, full_key, sep=sep))
        else:
            items[full_key] = type(v)
    return items

def get_enum_options_by_path(d, path):
    for key in path:
        d = d.get(key, {})
    return d.get('enum', [])

def comma_seperated_to_list(value):
    if isinstance(value, str):
        return [v.strip() for v in value.split(',') if v.strip()]
    return []

def generate_stream_disabled_image(width=640, height=480, text="Stream Disabled"):
    image = np.zeros((height, width, 3), dtype=np.uint8)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 1.5
    font_color = (255, 255, 255)  # white
    thickness = 2

    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    text_width, text_height = text_size

    x = (width - text_width) // 2
    y = (height + text_height) // 2

    cv2.putText(image, text, (x, y), font, font_scale, font_color, thickness, lineType=cv2.LINE_AA)

    return image
