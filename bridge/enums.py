import strawberry
from enum import Enum


@strawberry.enum(description="The state of a dask cluster")
class PodStatus(str, Enum):
    """The state of a dask cluster"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    UNKOWN = "UNKOWN"


@strawberry.enum(description="The state of a dask cluster")
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
