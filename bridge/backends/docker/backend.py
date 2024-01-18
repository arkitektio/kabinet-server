from typing import Any, Coroutine, AsyncGenerator
from bridge.backends.base import ContainerBackend
from channels.layers import get_channel_layer
from bridge.backends.messages import PullUpdate, UpUpdate, FlavourUpdate
from bridge.models import Flavour, Setup, Pod
from bridge.repo import selectors
import docker
import os
from kante.types import Info
import logging
from typing import List

logger = logging.getLogger(__name__)


DOWNLOAD_STATUS = "Downloading"
EXTRACTING_STATUS = "Extracting"
PULL_COMPLETE = "Pull complete"
DOWNLOAD_COMPLETE = "Download complete"
PULLED = "Pulled"
WAITING = "Waiting"


class RateError(Exception):
    pass


class DockerBackend(ContainerBackend):
    """ This is a backend that uses docker to run containers
    
    It implements the ContainerBackend interface, and is responsible for
    pulling images, running containers and managing their lifecycle, as well
    as providing an interface for interacting with the container.

    TODO: We will have to make this backend configurable, so that we can
    automatically retrieve information about the backend from the environment,
    and to check if for examples GPUs are available.

    
    """

    pass

    def __init__(self, gpu_available: bool = False, cpu_frequency: int = True) -> None:
        super().__init__()
        self.api = docker.from_env()
        self.gpu_available = gpu_available



    async def aget_my_networks(self) -> List[str]:
        """ A function to get the networks that the backend,
        i.e. the container that is running this code, is connected t
        

        Returns:
            List[str]: A list of networks that the backend is connected to
        """


        try:
            container_id = os.getenv("HOSTNAME")
            container = self.api.containers.get(container_id)
            print(container)

            network_settings = container.attrs["NetworkSettings"]
            networks = network_settings["Networks"]
            print("Network Settings:", network_settings)

            expanded_networks = []

            for network_name, network_detail in networks.items():
                network_id = network_detail["NetworkID"]
                network = self.api.networks.get(network_id)
                expanded_networks.append(network)

            return expanded_networks
        except Exception as e:
            logger.error("Could not get networks. Returning Bridge", exc_info=True)
            return ["bridge"]
        

    async def awatch_flavour(self, info: Info, flavour: Flavour) -> AsyncGenerator[FlavourUpdate, None]:
        """ Watches a flavour for updates and sends them to the client  """
        async for i in self.alisten(info, "whale_pull", FlavourUpdate, groups=[flavour.id]):
            yield i
        

   
    

    async def abackground_pull_flavour(self, flavour_id: str) -> None:
        """ Background task to pull a flavour
        
        
        This function is called by the backend consumer and will cause a docker image to be pulled
        in the background. The function will send updates to the client through the channel layer
        to inform them about the progress of the pull.

        Args:
            flavour_id (str): The id of the flavour to pull

        
        """
        flavour = await Flavour.objects.aget(id=flavour_id)

        logger.info("Pulling Image: " + flavour.image)
        s = self.api.api.pull(flavour.image, stream=True, decode=True)

        keeping_progress = []
        finished = []


        await self.abroadcast("whale_pull", FlavourUpdate(status="Pulling", progress=0.5, flavour=flavour.id), groups=[flavour.id])


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

                    await self.abroadcast("whale_pull", FlavourUpdate(status="Pulling", progress=progress, flavour=flavour.id), groups=[flavour.id])
                

        await self.abroadcast("whale_pull", FlavourUpdate(status="Pulling", progress=1, flavour=flavour.id), groups=[flavour.id])


    async def apull_flavour(self, flavour: Flavour) -> None:
        """ A function to pull a flavour"""
        await self.asend_background("abackground_pull_flavour", flavour.id)
        return None
        


    async def arate_flavour(self, flavour: Flavour) -> int:
        """A function that rates flavours based on their ability to be
        deployed. The higher the rating, the more likely it is to be
        deployed.

        Args:
            flavour (Flavour): The flavour to rate

        Returns:
            int: The rating of the flavour (-1 if it cannot be deployed)

        Raises:
            RateError: If the flavour cannot be deployed
        """

        count = 0


        try:
            self.api.images.get(flavour.image)
        except docker.errors.ImageNotFound:
            raise RateError(f"Image {flavour.image} not found")

        for selector in flavour.get_selectors():
            if isinstance(selector, selectors.CudaSelector):
                if not self.gpu_available:
                    if selector.required:
                        raise RateError(f"Flavour {flavour} requires GPU. But GPU is not available")
                    else:
                        count += 0
                else:
                    count += selector.weight
            
            else:
                count += selector.weight
            
            #TODO: Test for more selectors


        return count
    

    async def aup_setup_with_flavour(self, setup: Setup, flavour: Flavour) -> Pod:


        # Create a pod


        container_id = f"{setup.id}-{flavour.id}"


        device_requests = []


        for selector in flavour.get_selectors():
            if isinstance(selector, selectors.CudaSelector):
                device_requests.append(
                    docker.types.DeviceRequest(
                        count=-1,
                        capabilities=[
                            ["gpu"]
                        ]
                    )
                )



        networks = await self.aget_my_networks()

        network = networks[0].name


        try:
            # Lets see if a pod already exists
            container = self.api.containers.get(container_id)
            print(f"Container {container} Exists, doing nothing")
        except Exception: # TODO: Find the right exception
            container = self.api.containers.run(
                flavour.image,
                command=setup.command,
                detach=True,
                name=container_id,
                labels={
                    "setup": f"{setup.id}",
                    "instance": f"{setup.instance}",
                },
                restart_policy={"Name": "on-failure", "MaximumRetryCount": 5},
                device_requests=device_requests,
                environment={
                    "FAKTS_URL": setup.fakts_url,
                    "FAKTS_TOKEN": setup.api_token,
                    "REKUEST_INSTANCE": setup.instance,
                },
                network=network,
            )


        pod = await Pod.objects.acreate(
            setup=setup,
            flavour=flavour,
            pod_id=container_id,
            backend="docker",
        )

        return pod

    async def aget_status(self, pod: Pod) -> str:
        try:
            container = self.api.containers.get(pod.pod_id)
            return container.status
        except docker.errors.NotFound:
            return "Not Found"
        

    async def aget_logs(self, pod: Pod) -> str:
        try:
            container = self.api.containers.get(pod.pod_id)
            return container.logs().decode("utf-8")
        except docker.errors.NotFound:
            return "Not Found"



    async def aup_setup(self, setup: Setup) -> Pod:


        # Iterate over flavours and pull them

        flavour_dict = {}

        error_dict = {}

        async for flavour in Flavour.objects.filter(release=setup.release).all():
            try:
                rating = await self.arate_flavour(flavour)
                flavour_dict[flavour] = rating
            except RateError as e:
                logger.warning(f"Flavour {flavour} cannot be deployed")
                error_dict[flavour] = e

            

        # Sort flavours by rating
        sorted_flavours = sorted(flavour_dict.items(), key=lambda x: x[1])

        # Pull the best flavour

        try:
            best_flavour = sorted_flavours[0][0]
        except IndexError:
            logger.error("No flavours available for setup")

            error_string = "\n".join([f"{k.name}: {v}" for k, v in error_dict.items()])


            raise Exception("No flavours available for setup: " +error_string)

        return await self.aup_setup_with_flavour(setup, best_flavour)

        






