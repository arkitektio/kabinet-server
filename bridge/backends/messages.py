from pydantic import BaseModel

class PullUpdate(BaseModel):
    status: str
    progress: float