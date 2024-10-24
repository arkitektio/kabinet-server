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

    def build_docker_params(self) -> List[str]:
        """Builds the docker params for this selector

        Should return a list of strings that can be used as docker params
        If the selector is not required, it should return an empty list

        Returns
        -------
        List[str]
            The docker params for this selector
        """
        return []

    def build_arkitekt_params(self) -> List[str]:
        """Builds the arkitekt params for this selector

        Returns
        -------
        List[str]
            The docker params for this selector
        """
        return []


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
    frequency: Optional[int] = Field(default=None, description="The frequency in MHz")
    memory: Optional[int] = Field(default=None, description="The memory in MB")
    architecture: Optional[str] = Field(
        default=None, description="The architecture of the GPU"
    )
    compute_capability: str = Field(
        default="3.5", description="The minimum compute capability"
    )
    cuda_cores: Optional[int] = None
    cuda_version: str = Field(default="10.2", description="The minimum cuda version")

    def build_docker_params(self) -> List[str]:
        """Builds the docker params for this selector

        Should return a list of strings that can be used as docker params
        If the selector is not required, it should return an empty list

        Returns
        -------
        List[str]
            The docker params for this selector
        """
        return [
            "--gpus",
            "all",
        ]


class RocmSelector(BaseSelector):
    """A selector is a way to describe a flavours preference for a
    compute node. It contains the node_id, the selector and the flavour_id.
    """

    kind: Literal["rocm"]
    min: Optional[int] = None
    frequency: Optional[int] = None
    memory: Optional[int] = None
    architecture: Optional[str] = None
    compute_capability: Optional[str] = None
    cuda_cores: Optional[int] = None
    cuda_version: Optional[str] = None

    def build_docker_params(self) -> List[str]:
        """Builds the docker params for this selector"""

        return [
            "--device=/dev/kfd",
            "--device=/dev/dri",
            "--group-add",
            "video",
            "--cap-add=SYS_PTRACE",
            "--security-opt",
            "seccomp=unconfined",
        ]


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
