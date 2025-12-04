from typing import NamedTuple

class Point3d(NamedTuple):
    x: float
    y: float
    z: float
    
    def __str__(self) -> str:
        return f"({round(self.x, 2)},{round(self.y, 2)},{round(self.z, 2)})"

class Point2d(NamedTuple):
    x: float
    y: float

    def __str__(self) -> str:
        return f"({round(self.x, 2)},{round(self.y, 2)})"

class Detection(NamedTuple):
    point: Point3d
    center: Point2d
    depth: float