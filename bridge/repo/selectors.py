from typing import List, Union, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class BaseSelector(BaseModel):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    required: bool = True
    weight: int = 1
    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )



class RAMSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    kind: Literal["ram"]
    min: Optional[int] = None


class CPUSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    kind: Literal["cpu"]
    min_count: Optional[int] = None
    frequency: Optional[float] = None


class CudaSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    kind: Literal["cuda"]
    cuda_cores: Optional[int] = Field(default=None, description="The number of cuda cores", alias="cudaCores")
    cuda_version: Optional[str] = Field(default=None, description="The minimum cuda version", alias="cudaVersion")


class RocmSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    kind: Literal["rocm"]
    api_thing: Optional[str] = Field(alias="apiThing")
    api_version: Optional[str] = Field(alias="apiVersion")


class LabelSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute action. It contains the action_id, the selector and the flavour_id.
    """

    kind: Literal["label"]
    key: Optional[str] = None
    value: Optional[str] = None


class ServiceSelector(BaseSelector):
    """A service selector is a way to describe a flavours preference for a
    service. It contains the service_id,
    """

    kind: Literal["service"]


Selector = Union[RAMSelector, CPUSelector, CudaSelector, RocmSelector, LabelSelector, ServiceSelector]


class SelectorFieldJson(BaseModel):
    selectors: List[Selector] = Field(
        description="The selectors are used to place this image on the actions",
        default_factory=list,
    )
