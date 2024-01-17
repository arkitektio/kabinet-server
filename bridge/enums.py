import strawberry
from enum import Enum


@strawberry.enum(description="The state of a dask cluster")
class DaskClusterState(int, Enum):
    """The state of a dask cluster"""

    PENDING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4
    FAILED = 5


def map_string_to_enum(string: str) -> DaskClusterState:
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


    return DaskClusterState[string.upper()]
