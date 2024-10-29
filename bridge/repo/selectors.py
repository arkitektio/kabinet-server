from typing import List, Union, Optional, Literal
from pydantic import BaseModel, Field


class BaseSelector(BaseModel):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    required: bool = True
    weight: int = 1

    class Config:
        extra = "forbid"
        allow_population_by_field_name = True



class RAMSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["ram"]
    min: Optional[int] = None


class CPUSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["cpu"]
    min_count: Optional[int] = None
    frequency: Optional[int] = None


class CudaSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["cuda"]
    cuda_cores: Optional[int] = Field(default=None, description="The number of cuda cores", alias="cudaCores")
    cuda_version: str = Field(default="10.2", description="The minimum cuda version", alias="cudaVersion")

   


class RocmSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["rocm"]
    api_thing: Optional[str] = Field(alias="apiThing")
    api_version: Optional[str] = Field(alias="apiVersion")

    

class LabelSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["label"]
    key: Optional[str] = None
    value: Optional[str] = None


class ServiceSelector(BaseSelector):
    """A service selector is a way to describe a flavours preference for a
    service. It contains the service_id,
    """

    kind: Literal["service"]


Selector = Union[
    RAMSelector, CPUSelector, CudaSelector, RocmSelector, LabelSelector, ServiceSelector
]


class SelectorFieldJson(BaseModel):
    selectors: List[Selector] = Field(
        description="The selectors are used to place this image on the nodes",
        default_factory=list,
    )
