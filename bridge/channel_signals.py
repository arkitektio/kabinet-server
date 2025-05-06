from pydantic import BaseModel, Field


class PodSignal(BaseModel):
    """A model representing a pod update event."""
    create: int | None = Field(None, description="The pod that was updated.")
    update: int | None = Field(None, description="The pod that was updated.")
    delete: int | None = Field(None, description="The pod that was deleted.")