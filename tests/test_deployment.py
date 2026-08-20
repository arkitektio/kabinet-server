"""``updateDeployment``, which used to accept a status and throw it away.

The mutation took a mandatory ``status``, and the Deployment model had no field to put it
in -- so the resolver re-saved an unmodified row and returned it. A client got a
successful-looking response and no way to tell that nothing had happened. The model now
carries ``status``, mirroring ``Pod.status``.
"""

import pytest
from kante.context import HttpContext

from tests.test_pods import setup_pod
from tests.utils import execute, execute_raw

UPDATE_DEPLOYMENT = """
    mutation UpdateDeployment($input: UpdateDeploymentInput!) {
        updateDeployment(input: $input) { id status }
    }
"""

DEPLOYMENT = """
    query Deployment($id: ID!) {
        deployment(id: $id) { id status localId }
    }
"""


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_update_deployment_persists_the_status(authenticated_context: HttpContext, flavour_id: str):
    """The status round-trips: it is stored, and a later read sees it."""
    ids = await setup_pod(authenticated_context, flavour_id)
    deployment_id = ids["deployment"]["id"]

    # A fresh deployment starts PENDING, the same default Pod uses.
    initial = (await execute(DEPLOYMENT, authenticated_context, {"id": deployment_id}))["deployment"]
    assert initial["status"] == "PENDING"

    updated = (
        await execute(UPDATE_DEPLOYMENT, authenticated_context, {"input": {"deployment": deployment_id, "status": "RUNNING"}})
    )["updateDeployment"]
    assert updated["status"] == "RUNNING"

    # Read back through a separate query, so this cannot pass on the in-memory instance.
    reread = (await execute(DEPLOYMENT, authenticated_context, {"id": deployment_id}))["deployment"]
    assert reread["status"] == "RUNNING"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_update_deployment_is_org_scoped(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
    flavour_id: str,
):
    """Another organization cannot move a deployment's status."""
    ids = await setup_pod(authenticated_context, flavour_id)
    deployment_id = ids["deployment"]["id"]

    result = await execute_raw(UPDATE_DEPLOYMENT, other_org_context, {"input": {"deployment": deployment_id, "status": "STOPPED"}})

    assert result.errors, "a cross-tenant update should not succeed"

    # And the status is untouched for the owning organization.
    unchanged = (await execute(DEPLOYMENT, authenticated_context, {"id": deployment_id}))["deployment"]
    assert unchanged["status"] == "PENDING"
