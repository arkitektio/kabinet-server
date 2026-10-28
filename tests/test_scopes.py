"""What an app may do here is what its token's scopes say: every root field asks for one of kabinet's
own (the ``@auth`` directive publishes it, a generated client gathers it), and `kabinet_all` stands
for all of them. What a member may do is their role: a deployer deploys, only an approver approves."""

import pytest
from kante.context import HttpContext, UniversalRequest
from strawberry.http.temporal_response import TemporalResponse

from arkitekt_service.graphql import scope_gaps
from kabinet_server.schema import schema

DECLARE_BACKEND = 'mutation { declareBackend(input: {name: "scoped", kind: "docker"}) { id } }'
BACKENDS = "query { backends { id } }"
REVOKE = 'mutation { revokeApproval(input: {id: "1"}) { id } }'


def _as(token: str) -> HttpContext:
    return HttpContext(request=UniversalRequest(_extensions={}), response=TemporalResponse(), headers={"Authorization": f"Bearer {token}"}, type="http")


def _reason(result) -> str | None:
    return result.errors[0].extensions.get("reason") if result.errors else None


def test_every_root_field_asks_for_a_scope_kabinet_declares():
    assert scope_gaps(schema) == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_an_app_granted_reads_reads_and_writes_nothing(backend_stack):
    assert (await schema.execute(BACKENDS, context_value=_as("readertest"))).errors is None
    refused = await schema.execute(DECLARE_BACKEND, context_value=_as("readertest"))
    assert _reason(refused) == "INSUFFICIENT_SCOPE"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_the_all_scope_writes(backend_stack):
    made = await schema.execute(DECLARE_BACKEND, context_value=_as("test"))
    assert made.errors is None, made.errors


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_a_deployer_deploys_but_does_not_approve(backend_stack):
    declared = await schema.execute(DECLARE_BACKEND, context_value=_as("othertest"))
    assert declared.errors is None, declared.errors
    refused = await schema.execute(REVOKE, context_value=_as("othertest"))
    assert _reason(refused) == "INSUFFICIENT_ROLE"
