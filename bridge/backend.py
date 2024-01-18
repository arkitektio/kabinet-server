from contextvars import ContextVar
from strawberry.extensions import SchemaExtension
from kante.types import ChannelsWSContext
from bridge.backends.base import ContainerBackend
from bridge.backends.docker import DockerBackend


current_backend: ContextVar[ContainerBackend] = ContextVar("current_backend")

def create_backend(context: ChannelsWSContext) -> ContainerBackend:
    """Create a new Dask Gateway connection

    Parameters
    ----------
    context : ChannelsWSContext
        The context of the GraphQL request

    Returns
    -------
    Gateway
        The Dask Gateway connection

    """
    backend = DockerBackend()
    return backend




backend = create_backend({})
current_backend.set(backend)



def get_backend() -> ContainerBackend:
    """Get the current Dask Gateway connection

    This function gets the current Dask Gateway connection from the context
    of the GraphQL request. If no Dask Gateway connection is found, an
    exception is raised.

    Returns
    -------
    Gateway
        The Dask Gateway connection

    Raises
    ------
    Exception
        If no Dask Gateway connection is found

    """
    global backend
    return backend


