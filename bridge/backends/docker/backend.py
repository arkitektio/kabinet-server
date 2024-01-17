from typing import Any, Coroutine, AsyncGenerator
from bridge.backends.base import ContainerBackend
from channels.layers import get_channel_layer
from bridge.backends.messages import PullUpdate
from bridge.models import Flavour
import docker
import os
import logging

logger = logging.getLogger(__name__)

api = docker.from_env()

DOWNLOAD_STATUS = "Downloading"
EXTRACTING_STATUS = "Extracting"
PULL_COMPLETE = "Pull complete"
DOWNLOAD_COMPLETE = "Download complete"
PULLED = "Pulled"
WAITING = "Waiting"


class DockerBackend(ContainerBackend):

    pass

    def __init__(self) -> None:
        super().__init__()
        self.api = docker.from_env()

    async def apull_flavour(self, flavour: Flavour) -> AsyncGenerator[PullUpdate, None]:
        logger.info("Pulling Image: " + flavour.image)
        s = api.api.pull(flavour.image, stream=True, decode=True)

        keeping_progress = []
        finished = []


        yield PullUpdate(status="Pulling", progress=0.5)


        for f in s:
            if "status" in f:
                logger.info(f["status"])
                if f["status"] in [WAITING]:
                    keeping_progress.append(f["id"])

                if f["status"] in [PULL_COMPLETE]:
                    if f["id"] in keeping_progress:
                        finished.append(f["id"])

                    progress = len(finished) / (
                        len(keeping_progress) if len(keeping_progress) > 0 else 1
                    )

                    logger.info(
                        "Progress: " + flavour.image + " " + str(progress)
                    )

                    yield PullUpdate(status="Pulling", progress=progress)
                

        yield PullUpdate(status="Pulled", progress=1)



