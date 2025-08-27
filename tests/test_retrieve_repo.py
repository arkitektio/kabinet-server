import pytest
from bridge.models import Flavour, App, Release, GithubRepo
from django.contrib.auth import get_user_model
import typing
from bridge.repo.models import KabinetConfigFile
import yaml
from tests.utils import build_relative_dir
from rekuest_core.enums import PortKind
from bridge.repo.db import parse_config


@pytest.mark.asyncio
async def test_parse_deployments(db: typing.Any) -> None:
    with open(
        build_relative_dir("deployments/deployments.yaml"), "r"
    ) as deployment_file:
        deployment = yaml.safe_load(deployment_file)

    config = KabinetConfigFile(**deployment)

    assert len(config.app_images) >= 1 and (
        config.app_images[0].flavour_name == "vanilla"
    ), "First deployment should be vanilla"
   
    

    


@pytest.mark.asyncio
async def test_db_deployments(db: typing.Any) -> None:
    user, _ = await get_user_model().objects.aget_or_create(
        username="test", defaults=dict(email="test@gmail.com")
    )

    github_repo = await GithubRepo.objects.acreate(
        name="test",
        creator=user,
    )

    with open(
        build_relative_dir("deployments/deployments.yaml"), "r"
    ) as deployment_file:
        deployment = yaml.safe_load(deployment_file)

    config = KabinetConfigFile(**deployment)

    flavours = await parse_config(config, github_repo)

    assert len(flavours) == 1, "Should have three flavours"
