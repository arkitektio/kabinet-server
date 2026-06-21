from pydantic import BaseModel, Field
from strawberry.experimental import pydantic


class PodUpdateMessageModel(BaseModel):
    """A status update for a pod, pushed over a subscription."""

    id: str = Field(description="The ID of the pod this update is about.")
    status: str = Field(description="The new status of the pod.")
    created: bool = Field(description="Whether this update corresponds to the pod's creation.")
    progress: int | None = Field(default=None, description="Optional progress indicator for the update, as a percentage.")


@pydantic.type(PodUpdateMessageModel, description="A status update for a pod, pushed over a subscription.")
class PodUpdateMessage:
    """A status update for a pod, pushed over a subscription."""

    id: str
    status: str
    created: bool
    progress: int | None = None
