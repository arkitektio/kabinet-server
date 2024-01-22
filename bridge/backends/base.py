from bridge.models import Flavour, Setup, Pod, Release
from bridge.backends.errors import NotImplementedByBackendError
from typing import AsyncGenerator
from channels.layers import get_channel_layer, InMemoryChannelLayer
from bridge.backends import messages
import typing
import logging
from kante.types import Info
from pydantic import BaseModel
from bridge import enums

logger = logging.getLogger(__name__)


T = typing.TypeVar("T")

class ContainerBackend:
    """ A backend for running containers
    
    A backend is responsible for pulling images, running containers and managing their lifecycle, as well
    as providing an interface for interacting with the container.
    
    
    """

    backend_worker: str = "backend"

    def __init__(self) -> None:
        self.channel_layer: InMemoryChannelLayer = get_channel_layer()

    async def apull_flavour(self, flavour: Flavour) -> None:
        """A function to pull a flavour from the registry

        This function is called by the API when a user requests a flavour to be pulled. This should
        cause the flaovur to be pulled from a public registry and stored locally. This function
        should return immediately. The flavour should be pulled in the background.

        Args:
            flavour (Flavour): The flavour to pull

        Raises:
            NotImplementedError: This function should be implemented by subclasses

        """
         
          
           
        raise NotImplementedByBackendError("Subclasses should implement this!")
    
    async def aget_fitting_flavour(self, release: Release) -> Flavour:
        """ A function to get the flavour that best fits a release

        This function is called by the API when a user requests a release to be run. This should
        cause the flavour that best fits the release to be returned. This function
        should return immediately

        Args:
            release (Release): The release to get the flavour for

        Raises:
            NotImplementedError: This function should be implemented by subclasses

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
    

    async def ais_image_pulled(self,image: str) -> bool:
        """ A function to check if a flavour is pulled"""
    
   

    async def aup_setup(self, setup: Setup) -> Pod:
        """ A function to set up a flavour
        
        This function is called by the API when a user requests to setup a release. This function
        should then choose the best flavour to run the release on, and then run the release on that
        flavour creating a Pod, that should reference the container (in any lifecycle state) that
        is running the release.

        Args:
            setup (Setup): The setup to run, contains the release to run and environment variables

        Raises:
            NotImplementedError: This function should be implemented by subclasses

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
       

    async def aget_status(self, pod: Pod) -> enums.PodStatus:
        """ A function to get the status of a pod

        This function is called by the API when a user requests the status of a pod. This function
        should then return the status of the pod. The status should
        be one of the statuses defined in the PodStatus enum.

        Args:
            pod (Pod): The pod to get the status of

        Raises:
            NotImplementedError: This function should be implemented by subclasses

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass

    async def aget_logs(self, pod: Pod) -> str:
        """ A function to get the logs of a pod

        This function is called by the API when a user requests the status of a pod. This function
        should then return the status of the pod. The status should
        be one of the statuses defined in the PodStatus enum.

        Args:
            pod (Pod): The pod to get the status of

        Raises:
            NotImplementedError: This function should be implemented by subclasses

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass

    def awatch_flavour(self, info: Info, flavour: Flavour) -> AsyncGenerator[messages.FlavourUpdate, None]:
        """ A async generator that yields updates to a flavour

        This function is called by the API when a user requests to watch a flavour within a graphql
        subscription. This function should then yield updates to the flavour, which will be sent to
        the user.
        
        Most like this should delegate to the alisten function, which is implemented by the backend
        base class and allows for easy listening to channels.

        Args:
            info (Info): The info object from the graphql query
            flavour (Flavour): The flavour to watch

        Raises:
            NotImplementedError: This function should be implemented by subclasses

    

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass

    def awatch_flavours(self, info: Info) -> AsyncGenerator[messages.FlavourUpdate, None]:
        """ A async generator that yields updates to all flavours

        This function is called by the API when a user requests to watch all flavours within a graphql
        subscription. This function should then yield updates to all flavours, which will be sent to
        the user.
        
        Most like this should delegate to the alisten function, which is implemented by the backend
        base class and allows for easy listening to channels.

        Args:
            info (Info): The info object from the graphql query

        Raises:
            NotImplementedError: This function should be implemented by subclasses

    

        """
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass


    async def asend_background(self, function: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        """ A function to send a background task to the backend
        
        This function is an utilizy function that allow for sending a background task to the backend
        consumer. This function should be called by subclasses when they want to send a long running
        background task to the backend consumer. The backend consumer will then call the function

        Args:
            function (str): The name of the function to call
            *args (typing.Any): The arguments to pass to the function
            **kwargs (typing.Any): The keyword arguments to pass to the function

        Raises:
            AttributeError: If the backend does not have the given function
 """

        assert hasattr(self, function), "Backend does not have function {}".format(function)
        logger.info("Sending background task to backend: {}".format(function))

        await self.channel_layer.send(
            self.backend_worker,
            {
                "type": "call.function",
                "function_name": function,
                "args": args,
                "kwargs": kwargs,
            },
        )
        return None
    

    async def abroadcast(self, channel: str, message: BaseModel, groups: typing.Optional[typing.List[typing.Any]] = None) -> None:
        """ A function to broadcast a message to a channel

        This function is an utilizy function that allow for sending a message to a channel. This
        function should be called by subclasses when they want to send a message to a channel, that another
        consumer is listening to. 

        Args:
            channel (str): The name of the channel to send the message to
            message (BaseModel): The message to send: must be a pydantic model
            groups (typing.Optional[typing.List[typing.Any]], optional): The groups to send the message to. Defaults to None.

        Raises:
            AttributeError: If the backend does not have the given function
        
        """
        if groups is None:
            groups = ["default"]


        for group in groups:
            logger.debug(f"Sending message to group {group}")
            await self.channel_layer.group_send(
                f"_{group}",
                {
                    "type": f"backend.{channel}",
                    "message": message.dict(),
                }
            )


    async def alisten(self, info: Info, channel: str, serializer: typing.Type[T],  groups:  typing.Optional[typing.List[typing.Any]] = None, ) -> AsyncGenerator[T, None]:
        """ A function to listen to a channel

        This function is an utilizy function that allow for listening to a channel. This
        function should be called by subclasses when they want to listen to a channel, that another
        consumer is broadcasting to.

        Args:
            info (Info): The info object from the graphql subscription
            channel (str): The name of the channel to listen to
            serializer (typing.Type[T]): The serializer to use for the message
            groups (typing.Optional[typing.List[typing.Any]], optional): The groups to listen to. Defaults to None.

        
        """
        
        if groups is None:
            groups = ["default"]
        ws = info.context.consumer
        channel_layer = ws.channel_layer

        for group in groups:
            # Join room group
            logger.debug(f"Joining group {group} for channel {ws.channel_name}")
            await channel_layer.group_add(f"_{group}", ws.channel_name)

        async with ws.listen_to_channel(f"backend.{channel}", groups=[f"_{g}" for g in groups]) as cm:
            async for message in cm:
                yield serializer(**message["message"])

















