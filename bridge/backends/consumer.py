from channels.consumer import AsyncConsumer
import logging
from bridge.backends.docker import DockerBackend
from bridge.models import Flavour
from bridge.channel import whale_pull_broadcast
from typing import Dict, Any


logger = logging.getLogger(__name__)


class BackendConsumer(AsyncConsumer):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.backend = DockerBackend()



    async def pull_flavour(self, message: Dict[str, Any] ) -> None:

        print("Pulling flavour")

        flavour = await Flavour.objects.aget(id=message["flavour_id"])


        async for update in self.backend.apull_flavour(flavour):
            whale_pull_broadcast(update, [flavour.id])


    