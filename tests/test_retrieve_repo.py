import pytest
from asgiref.sync import sync_to_async
from authentikate.models import Organization
from django.contrib.auth import get_user_model

from bridge.models import GithubRepo
from bridge.repo.db import parse_config
from bridge.repo.models import KabinetConfigFile
from tests.utils import load_yaml


@pytest.mark.asyncio
async def test_parse_deployments(db: None) -> None:
    deployment = load_yaml("deployments/deployments.yaml")

    config = KabinetConfigFile(**deployment)

    assert len(config.app_images) >= 1 and (
        config.app_images[0].flavour_name == "vanilla"
    ), "First deployment should be vanilla"


@pytest.mark.asyncio
async def test_db_deployments(db: None) -> None:
    organization, _ = await Organization.objects.aget_or_create(
        identifier="test-organization"
    )

    user, _ = await get_user_model().objects.aget_or_create(
        username="test", defaults=dict(email="test@gmail.com")
    )

    github_repo = await GithubRepo.objects.acreate(
        name="test",
        creator=user,
        organization=organization,
    )

    deployment = load_yaml("deployments/deployments.yaml")

    config = KabinetConfigFile(**deployment)

    flavours = await sync_to_async(parse_config)(config, github_repo, organization)

    assert len(flavours) == 1, "Should have three flavours"
