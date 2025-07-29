import cv2

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
            items.update(flatten_with_types(v, full_key, sep=sep))
        else:
            items[full_key] = type(v)
    return items

def comma_seperated_to_list(value):
    if isinstance(value, str):
        return [v.strip() for v in value.split(',') if v.strip()]
    return []