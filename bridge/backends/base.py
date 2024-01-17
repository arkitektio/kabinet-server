from bridge.models import Whale, Flavour
from bridge.backends.errors import NotImplementedByBackendError


class ContainerBackend:
    backend_worker: str = "backend"


    async def aget_running_whales(self) -> str:
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass


    async def pull_whale(self, whale: Whale) -> str:
        raise NotImplementedByBackendError("Subclasses should implement this!")
        pass


    async def adelay_pull_flavour(self, flavour: Flavour) -> str:

        raise NotImplementedByBackendError("Subclasses should implement this!")














