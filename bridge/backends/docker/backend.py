from typing import Any, Coroutine
from bridge.backends.base import ContainerBackend
from channels.layers import get_channel_layer

from bridge.models import Flavour


class DockerBackend(ContainerBackend):

    pass

    def __init__(self) -> None:
        super().__init__()
        self.channel_layer = get_channel_layer()


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


