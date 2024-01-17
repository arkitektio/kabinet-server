from bridge.models import Whale, Flavour
from bridge.backends.errors import NotImplementedByBackendError
from typing import AsyncGenerator
from channels.layers import get_channel_layer
from bridge.backends import messages

class ContainerBackend:
    backend_worker: str = "backend"

    def __init__(self) -> None:
        self.channel_layer = get_channel_layer()


    async def aget_running_whales(self) -> str:
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass


    def apull_flavour(self, flavour: Flavour) -> AsyncGenerator[messages.PullUpdate, None]:
        """ """
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass


    async def adelay_pull_flavour(self, flavour: Flavour) -> str:
       
        await self.channel_layer.send(
            self.backend_worker,
            {
                "type": "pull.flavour",
                "flavour_id": flavour.id,
            },
        )

        print("Sent message to backend worker")

        return "OK"















