from pydantic import BaseModel


class Log(BaseModel):
    latency: float
    log: str
