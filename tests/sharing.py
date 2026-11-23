"""What the sharing tests build: apps pushed as app images (``createAppImage``), the actions their
flavours provide, and where the organization runs them, which is never shared."""

import copy
import datetime
import json
import pathlib
import uuid
from dataclasses import dataclass
from typing import Any

import yaml
from arkitekt_service.collaborations.models import Collaboration
from asgiref.sync import sync_to_async
from authentikate.models import Client
from joserfc import jwt
from joserfc.jwk import OKPKey
from kante.context import HttpContext
from strawberry.types import ExecutionResult

from bridge import models
from kabinet_server.schema import schema
from tests.conftest import token_context
from tests.utils import build_relative_dir

#: A GraphQL payload, as strawberry hands it over.
GraphQLData = dict[str, object]

KEY = OKPKey.import_key(
    json.loads(
        (pathlib.Path(__file__).parent / "fixtures" / "provenance_key.json").read_text()
    )
)

#: The fixture's first app image, as the spec spells it.
APP_IMAGE: dict[str, Any] = yaml.safe_load(
    pathlib.Path(build_relative_dir("deployments/deployments.yaml")).read_text()
)["app_images"][0]

PUSH = """
mutation ($input: AppImageInput!) {
  createAppImage(input: $input) { id app { id } flavours { id } }
}
"""


def task_token(task: str, root: str) -> str:
    """A task token as rekuest signs it for the static test user ("1"): the task ``task`` of the workflow ``root``."""
    now = int(datetime.datetime.now(datetime.UTC).timestamp())
    return jwt.encode(
        {"alg": "Ed25519", "kid": "kabinet-test-provenance"},
        {
            "iss": "rekuest",
            "aud": ["kabinet"],
            "sub": "1",
            "act": {"sub": "1", "cid": "static", "iss": "static_issuer"},
            "iat": now,
            "exp": now + 300,
            "jti": uuid.uuid4().hex,
            "tsk": task,
            "ptk": root if task != root else None,
            "rtk": root,
            "rcb": "1",
            "ahs": "e3b0c44298fc1c14",
            "aha": "sha256-canonical-v1",
        },
        KEY,
        algorithms=["Ed25519"],
    )


async def run(ctx: HttpContext, query: str, **variables: object) -> ExecutionResult:
    return await schema.execute(
        query, context_value=ctx, variable_values=variables or None
    )


async def member(
    query: str, task: str | None = None, **variables: object
) -> GraphQLData:
    """Run ``query`` as the full member, as a request of its own (under the task token ``task``)."""
    result = await run(token_context("test", task=task), query, **variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


def refused(result: ExecutionResult, reason: str) -> None:
    assert result.errors, "it was let through"
    extensions = result.errors[0].extensions
    assert extensions is not None, result.errors
    assert extensions.get("reason") == reason, result.errors


def ids(data: GraphQLData, field: str) -> set[str]:
    rows = data[field]
    assert isinstance(rows, list)
    return {str(row["id"]) for row in rows}


@dataclass(frozen=True)
class Pushed:
    """An app image as ``createAppImage`` filed it: its app, release and flavour."""

    app: models.App
    release: models.Release
    flavour: models.Flavour


async def push(identifier: str, version: str, task: str | None = None) -> Pushed:
    """Push the fixture's app image as ``identifier`` ``version`` (under the task token ``task``)."""
    image = copy.deepcopy(APP_IMAGE)
    image["inspection"]["specVersion"] = image["inspection"].pop("spec_version")
    image["inspection"]["implementations"] = []
    image["manifest"]["identifier"] = identifier
    image["manifest"]["version"] = version
    image["appImageId"] = f"{identifier}-{version}"
    image["image"]["imageString"] = f"registry.example/{identifier}:{version}"
    pushed = await member(PUSH, task=task, input=image)
    release = pushed["createAppImage"]
    assert isinstance(release, dict)
    [flavour] = release["flavours"]
    return Pushed(
        app=await models.App.objects.aget(pk=release["app"]["id"]),
        release=await models.Release.objects.aget(pk=release["id"]),
        flavour=await models.Flavour.objects.aget(pk=flavour["id"]),
    )


@sync_to_async
def provide(
    ctx: HttpContext, flavour: models.Flavour, name: str, **fields: object
) -> models.Definition:
    """An action the flavour provides."""
    definition = models.Definition.objects.create(
        name=name,
        hash=uuid.uuid4().hex,
        organization=ctx.request.organization,
        **fields,
    )
    definition.flavours.add(flavour)
    return definition


@dataclass(frozen=True)
class Running:
    """Where the organization runs a flavour, approved: never shared."""

    backend: models.Backend
    approval: models.ReleaseApproval
    deployment: models.Deployment
    pod: models.Pod


@sync_to_async
def deploy(ctx: HttpContext, flavour: models.Flavour) -> Running:
    """Run ``flavour`` on a backend of the organization, under an approval of its release."""
    client, _ = Client.objects.get_or_create(client_id=f"deployer-{uuid.uuid4().hex}")
    backend = models.Backend.objects.create(
        organization=ctx.request.organization,
        user=ctx.request.user,
        client=client,
        name="docker",
        kind="docker",
    )
    approval = models.ReleaseApproval.objects.create(
        release=flavour.release,
        organization=ctx.request.organization,
        approver=ctx.request.user,
        mandate_id=uuid.uuid4().hex,
        agent="deployer",
        digest="sha256:0",
    )
    deployment = models.Deployment.objects.create(
        flavour=flavour,
        backend=backend,
        approval=approval,
        secret_params={"token": "never a guest's"},
    )
    pod = models.Pod.objects.create(
        backend=backend, deployment=deployment, pod_id=uuid.uuid4().hex
    )
    return Running(backend=backend, approval=approval, deployment=deployment, pod=pod)


async def collaboration(ctx: HttpContext, *objects: tuple[str, object]) -> str:
    """A collaboration of the organization holding ``objects`` (``(identifier, id)``), as a full
    member puts them in: under a fresh key, in one ``addManyToCollaboration``. Its key."""
    key = str(uuid.uuid4())
    added = await member(
        "mutation ($input: AddManyToCollaborationInput!) { addManyToCollaboration(input: $input) { key } }",
        input={
            "collaboration": key,
            "name": "Shared",
            "objects": [
                {"identifier": identifier, "object": str(pk)}
                for identifier, pk in objects
            ],
        },
    )
    assert added["addManyToCollaboration"] == {"key": key}
    assert await Collaboration.objects.filter(
        key=key, organization=ctx.request.organization
    ).aexists()
    return key
