from pydantic import BaseModel

class PullUpdate(BaseModel):
    status: str
    progress: float


class UpUpdate(PullUpdate):
    status: str
    progress: float


class FlavourUpdate(BaseModel):
    id: str
    status: str
    progress: float