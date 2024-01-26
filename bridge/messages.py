from pydantic import BaseModel
from strawberry.experimental import pydantic


class PodUpdateMessageModel(BaseModel):
    """Create a dask cluster input model"""

    id: str
    status: str
    created: bool


@pydantic.type(PodUpdateMessageModel, description="An update on a pod")
class PopUpdateMessage:
    """Create a dask cluster input"""

    id: str
    status: str
    created: bool
