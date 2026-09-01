"""The selector vocabulary: hardware/capability requirements of a flavour.

One model set serves the whole lifecycle — the GraphQL ``SelectorInput``
members (kante merged union in :mod:`bridge.repo.types`), the JSON stored on
``Flavour.selectors``, and the ``Flavour.selectors`` GraphQL output types
(:mod:`bridge.types`). Input, storage and output cannot drift apart because
they are the same classes; that asymmetry is what used to make a stored
``cpu`` or ``oneapi`` selector crash every query embedding the flavour.

Semantics (documented in full in ``docs/selectors.md``):

- ``required: true`` is a hard constraint — a deployer MUST NOT place the
  flavour on a backend that fails it (Kubernetes'
  ``requiredDuringSchedulingIgnoredDuringExecution``).
- ``required: false`` marks a preference; ``weight`` scores it. Deployers
  SHOULD prefer candidates with the highest sum of satisfied preferred
  weights (Kubernetes' ``preferredDuringScheduling...`` weight).
- ``label`` selectors match a backend resource's ``qualifiers`` — the
  nodeSelector analog. A ``null`` value means "key exists".
- Kabinet itself only stores and serves selectors; evaluation happens in
  the deployer that places pods. There is deliberately no server-side
  matching endpoint.

A service dependency is NEVER a selector: services an app needs (mikro,
rekuest, ...) are Requirements (``InspectionInput.requirements``), which the
deployment composes — selectors only constrain *hardware placement*.
"""

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class BaseSelector(BaseModel):
    """Fields every selector kind shares: the hard/soft split.

    ``extra="forbid"`` is deliberate and relied upon twice: kante's merged
    ``SelectorInput`` uses it to turn a field that contradicts ``kind`` into
    an error naming both, and the storage round trip uses it to catch drift
    the moment it is introduced.
    """

    required: bool = Field(
        default=True,
        description="If true, a backend failing this selector must not run the flavour (hard constraint). If false, the selector is a preference scored by `weight`.",
    )
    weight: int = Field(
        default=1,
        description="Scoring weight of a preferred (non-required) selector; deployers prefer candidates with the highest sum of satisfied weights.",
    )

    model_config = ConfigDict(
        extra="forbid",
        validate_by_name=True,
    )


class CpuSelector(BaseSelector):
    """CPU requirements of the flavour."""

    kind: Literal["cpu"] = "cpu"
    min_count: Optional[int] = Field(default=None, alias="minCount", description="The minimum number of CPU cores required.")
    frequency: Optional[float] = Field(default=None, description="The minimum CPU frequency required, in MHz.")
    arch: Optional[str] = Field(default=None, description="The CPU architecture the image is built for (docker platform / kubernetes.io/arch values, e.g. 'amd64', 'arm64').")


class RamSelector(BaseSelector):
    """System-memory requirements of the flavour."""

    kind: Literal["ram"] = "ram"
    min: Optional[int] = Field(default=None, description="The minimum amount of system memory required, in MB.")


class CudaSelector(BaseSelector):
    """Requires a CUDA-capable (NVIDIA) GPU."""

    kind: Literal["cuda"] = "cuda"
    compute_capability: Optional[str] = Field(default=None, alias="computeCapability", description="The minimum CUDA compute capability required (e.g. '8.6') — NVIDIA's standard placement key.")
    cuda_version: Optional[str] = Field(default=None, alias="cudaVersion", description="The minimum CUDA (driver/runtime) version required.")
    memory: Optional[int] = Field(default=None, description="The minimum GPU memory (VRAM) required, in MB.")
    count: Optional[int] = Field(default=None, description="The number of GPUs required (a Docker device-reservation count; unset lets the deployer decide).")
    cuda_cores: Optional[int] = Field(default=None, alias="cudaCores", description="Deprecated: the minimum number of CUDA cores. Prefer computeCapability and memory.")


class RocmSelector(BaseSelector):
    """Requires a ROCm-capable (AMD) GPU."""

    kind: Literal["rocm"] = "rocm"
    api_version: Optional[str] = Field(default=None, alias="apiVersion", description="The minimum ROCm API version required.")
    api_thing: Optional[str] = Field(default=None, alias="apiThing", description="An additional ROCm capability qualifier.")


class OneApiSelector(BaseSelector):
    """Requires a oneAPI-capable (Intel) accelerator."""

    kind: Literal["oneapi"] = "oneapi"
    oneapi_version: Optional[str] = Field(default=None, alias="oneapiVersion", description="The minimum oneAPI version required.")


class LabelSelector(BaseSelector):
    """Requires the backend resource to carry a qualifier — the nodeSelector analog."""

    kind: Literal["label"] = "label"
    key: str = Field(description="The qualifier key the backend resource must carry.")
    value: Optional[str] = Field(default=None, description="The value the qualifier must have; null means the key merely has to exist.")


Selector = Annotated[
    Union[CpuSelector, RamSelector, CudaSelector, RocmSelector, OneApiSelector, LabelSelector],
    Field(discriminator="kind"),
]


class SelectorFieldJson(BaseModel):
    """The shape of the ``Flavour.selectors`` JSONField."""

    selectors: List[Selector] = Field(
        description="The selectors are used to place this image on backends.",
        default_factory=list,
    )
