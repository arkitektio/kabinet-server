from enum import Enum

import strawberry


@strawberry.enum(description="The lifecycle status of a pod.")
class PodStatus(str, Enum):
    """The lifecycle status of a pod."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    UNKOWN = "UNKOWN"


@strawberry.enum
class DemandKind(str, Enum):
    ARGS = "args"
    RETURNS = "returns"


@strawberry.enum(description="The container runtime used to run a pod.")
class ContainerType(str, Enum):
    APPTAINER = "APPTAINER"
    DOCKER = "DOCKER"


def map_string_to_pod_status(string: str) -> PodStatus:
    """Map a string to a DaskClusterState

    Dask Gateway sometimes returns a string instead of an enum. This function
    maps the string to the corresponding DaskClusterState.

    Parameters
    ----------
    string : str
        The string to map to a DaskClusterState

    Returns
    -------
    DaskClusterState
        The DaskClusterState that corresponds to the given string

    """

    try:
        return PodStatus[string.upper()]
    except KeyError:
        return PodStatus.FAILED


@strawberry.enum(
    description="What an app's flavours run on: an accelerator (GPU) or a plain CPU backend."
)
class AppHardware(str, Enum):
    """The hardware an app can be run on, read off its flavours' required selectors."""

    GPU = "GPU"
    CPU = "CPU"


@strawberry.enum(description="How the repository a catalog entry names is read.")
class CatalogEntryKind(str, Enum):
    """How the repository a catalog entry names is read."""

    OCI = "oci"
    GITHUB = "github"
