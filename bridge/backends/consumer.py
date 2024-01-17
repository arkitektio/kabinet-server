from channels.consumer import AsyncConsumer
import logging
from bridge.backends.docker import DockerBackend
from bridge.models import Flavour
from bridge.channel import whale_pull_broadcast



logger = logging.getLogger(__name__)


class BackendConsumer(AsyncConsumer):



    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.backend = DockerBackend()



    async def pull_flavour(self, flavour_id: str) -> None:

        print("Pulling Image", flavour_id)

        for update in self.backend.pull_whale(whale):
            logger.info(f"Pulling Image: {whale}")
            whale_pull_broadcast(update, [whale.id])
