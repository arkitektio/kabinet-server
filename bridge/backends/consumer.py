from channels.consumer import AsyncConsumer
import logging
from bridge.backends.docker import DockerBackend
from bridge.models import Flavour
from bridge.channel import whale_pull_broadcast
from typing import Dict, Any
import typing

logger = logging.getLogger(__name__)


class BackendConsumer(AsyncConsumer):
    """ Consumer for backend tasks
    
    This consumer is responsible for calling backend functions
    if they are set to be dalayed. This is done by sending a message
    to the backend worker channel, which is then picked up by this
    consumer. The consumer then calls the function with the given
    arguments.
    
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        """ Initialize the backend consumer. """
        super().__init__(*args, **kwargs)
        self.backend = DockerBackend() #TODO: Make this configurable



    async def call_function(self, message: Dict[str, Any] ) -> None:
        """ A function to call a function on the backend.
        
        This function is called by the backend worker channel when
        a message is received. The message contains the function name
        and the arguments to be passed to the function. The function
        is then called with the given arguments.
        
        """
        logger.info("Calling function {}".format(message["function_name"]))
        try:
            function = getattr(self.backend, message["function_name"])
        except AttributeError:
            logger.error("Backend does not have function {}".format(message["function_name"]))
            return None
        
        try:
            await function(*message.get("args", []), **message.get("kwargs", {}))
        except Exception:
            logger.error("Error calling function {}".format(message["function_name"]), exc_info=True)
            return None
        

    




    