from contextvars import ContextVar
from strawberry.extensions import SchemaExtension
from kante.types import ChannelsWSContext
from bridge.backends.base import ContainerBackend
from bridge.backends.docker import DockerBackend


current_backend: ContextVar[ContainerBackend] = ContextVar("current_backend")




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
    try:
        return current_backend.get()
    except LookupError:
        raise Exception("No Dask Gateway connection found")


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


class ContainerBackendExtension(SchemaExtension):
    """A Strawberry Schema Extension for Dask Gateway"""
    async def on_operation(self) -> None:  # type: ignore
        """Create a new Dask Gateway connection and add it to the context.
        
        Hook is called before the operation is executed. This hook creates a new
        Dask Gateway connection and adds it to the context of the GraphQL request.
        """
        print("Starting operation")
        try:
            gateway = create_backend(self.execution_context.context)
            token = current_backend.set(gateway)

            try:
                yield
            finally:
                current_backend.reset(token)
        except Exception as e:
            print(e)
            yield
