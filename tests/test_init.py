import pytest
from bridge.backends.docker import DockerBackend
from bridge.models import Flavour, App, Release, GithubRepo, Setup
from django.contrib.auth import get_user_model
import typing


def test_init() -> None:
    """Test that the backend can be initialised."""
    backend = DockerBackend()
    assert backend is not None
    assert backend.channel_layer is not None, "Backend should have a channel layer"

@pytest.mark.asyncio
@pytest.mark.docker
async def test_pull_flavour(db: typing.Any) -> None:

    backend = DockerBackend()

    user, _ = await get_user_model().objects.aget_or_create(
        username="test",
        defaults=dict(email="test@gmail.com")
    )

    github_repo = await GithubRepo.objects.acreate(
        name="test",
        creator=user,
    )

    app = await App.objects.acreate(
        identifier="test",
    )

    release = await Release.objects.acreate(
        version="test",
        app=app,
    )

    flavour = await Flavour.objects.acreate(
        release=release,
        name="test",
        repo=github_repo,
        image="hello-world",
    )

    latest_update = None

    async for update in backend.apull_flavour(flavour):
        assert update.status in ["Pulling", "Pulled"]
        assert update.progress >= 0, "Progress should be greater than 0"
        assert update.progress <= 1, "Progress should be less than 1"

    

@pytest.mark.asyncio
@pytest.mark.docker
async def test_up_setup(db: typing.Any) -> None:
    backend = DockerBackend()

    user, _ = await get_user_model().objects.aget_or_create(
        username="test",
        defaults=dict(email="test@gmail.com")
    )

    github_repo = await GithubRepo.objects.acreate(
        name="test",
        creator=user,
    )

    app = await App.objects.acreate(
        identifier="test",
    )

    release = await Release.objects.acreate(
        version="test",
        app=app,
    )

    # Creating two different flavours, of which one has a selector
    # Should just create one container

    cuda_flavour = await Flavour.objects.acreate(
        release=release,
        name="cuda",
        repo=github_repo,
        image="hello-world",
        selectors=[
            {
                "type": "cuda",
            }
        ]
    )

    vanilla_flavour = await Flavour.objects.acreate(
        release=release,
        name="vanilla",
        repo=github_repo,
        image="hello-world",
        selectors=[]
    )

    setup = await Setup.objects.prefetch_related("release.flavours").acreate(
        release=release,
        installer=user,
        command=""
    )


    latest_update = None

    pod = await backend.aup_setup(setup)


    assert pod is not None, "Pod should be created"
    assert pod.setup == setup, "Pod should have the correct setup"
    assert pod.flavour == vanilla_flavour, "Pod should have the correct flavour"
    assert pod.backend == "docker", "Pod should have the correct backend"



