"""GraphQL endpoint tests for the Pod/Backend/Resource/Deployment API surface.

Everything is driven *through the schema* (``schema.execute``) exactly like
``test_inspect_repo.py::test_create_github_repo`` — no resolver/ORM assertions and no
endpoints that make external HTTP calls. The only prerequisite built outside of GraphQL
is a ``Flavour`` (there is no offline mutation that creates one): it is produced offline
via ``parse_config`` against the local ``deployments.yaml`` fixture, the same proven path
used by ``test_retrieve_repo.py::test_db_deployments``.
"""

import pytest

from kante.context import HttpContext
from tests.utils import execute


# ---------------------------------------------------------------------------
# GraphQL documents
# ---------------------------------------------------------------------------

DECLARE_BACKEND = """
    mutation DeclareBackend($input: DeclareBackendInput!) {
        declareBackend(input: $input) { id name kind }
    }
"""

CREATE_DEPLOYMENT = """
    mutation CreateDeployment($input: CreateDeploymentInput!) {
        createDeployment(input: $input) { id localId name }
    }
"""

DECLARE_RESOURCE = """
    mutation DeclareResource($input: DeclareResourceInput!) {
        declareResource(input: $input) { id name resourceId qualifiers }
    }
"""

CREATE_POD = """
    mutation CreatePod($input: CreatePodInput!) {
        createPod(input: $input) { id podId clientId status name }
    }
"""

UPDATE_POD = """
    mutation UpdatePod($input: UpdatePodInput!) {
        updatePod(input: $input) { id status }
    }
"""

DUMP_LOGS = """
    mutation DumpLogs($input: DumpLogsInput!) {
        dumpLogs(input: $input) { id logs }
    }
"""

DELETE_POD = """
    mutation DeletePod($input: DeletePodInput!) {
        deletePod(input: $input)
    }
"""


async def setup_pod(
    context: HttpContext,
    flavour_id: str,
    *,
    pod_local_id: str = "pod-1",
    client_id: str = "client-1",
    resource_local_id: str = "res-1",
) -> dict:
    """Drive declareBackend -> createDeployment -> declareResource -> createPod through
    GraphQL and return the created ids (and the create_pod payload)."""
    backend = (await execute(DECLARE_BACKEND, context, {"input": {"name": "my-backend", "kind": "docker"}}))["declareBackend"]

    deployment = (
        await execute(CREATE_DEPLOYMENT, context, {"input": {"flavour": flavour_id, "localId": "dep-1"}})
    )["createDeployment"]

    resource = (
        await execute(
            DECLARE_RESOURCE,
            context,
            {"input": {"backend": backend["id"], "localId": resource_local_id, "name": "gpu", "qualifiers": [{"key": "gpu", "value": "true"}]}},
        )
    )["declareResource"]

    pod = (
        await execute(
            CREATE_POD,
            context,
            {"input": {"deployment": deployment["id"], "localId": pod_local_id, "resource": resource["id"], "clientId": client_id}},
        )
    )["createPod"]

    return {"backend": backend, "deployment": deployment, "resource": resource, "pod": pod}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_backend_deployment_resource_pod_lifecycle(authenticated_context: HttpContext, flavour_id: str) -> None:
    """The full create chain, each step consuming the previous step's id."""
    setup = await setup_pod(authenticated_context, flavour_id)

    backend, deployment, resource, pod = setup["backend"], setup["deployment"], setup["resource"], setup["pod"]

    assert backend["id"] is not None
    assert backend["name"] == "my-backend"
    assert backend["kind"] == "docker"

    assert deployment["id"] is not None
    assert deployment["localId"] == "dep-1"

    assert resource["id"] is not None
    assert resource["resourceId"] == "res-1"

    assert pod["id"] is not None
    assert pod["podId"] == "pod-1"
    assert pod["clientId"] == "client-1"
    assert pod["status"] == "PENDING"
    # name resolver walks deployment.flavour.release.app.identifier — proves the chain.
    assert pod["name"] is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pod_queries_and_lookups(authenticated_context: HttpContext, flavour_id: str) -> None:
    """Single-object queries, list queries, and the my_pod_at / pod_for_agent lookups."""
    setup = await setup_pod(authenticated_context, flavour_id)
    ids = {k: setup[k]["id"] for k in ("backend", "deployment", "resource", "pod")}

    pod = (await execute("query($id: ID!){ pod(id: $id){ id podId } }", authenticated_context, {"id": ids["pod"]}))["pod"]
    assert pod["id"] == ids["pod"]

    pods = (await execute("query{ pods { id podId } }", authenticated_context))["pods"]
    assert [p["id"] for p in pods] == [ids["pod"]]

    backend = (await execute("query($id: ID!){ backend(id: $id){ id name } }", authenticated_context, {"id": ids["backend"]}))["backend"]
    assert backend["name"] == "my-backend"

    backends = (await execute("query{ backends { id } }", authenticated_context))["backends"]
    assert [b["id"] for b in backends] == [ids["backend"]]

    resource = (await execute("query($id: ID!){ resource(id: $id){ id resourceId } }", authenticated_context, {"id": ids["resource"]}))["resource"]
    assert resource["resourceId"] == "res-1"

    resources = (await execute("query{ resources { id } }", authenticated_context))["resources"]
    assert [r["id"] for r in resources] == [ids["resource"]]

    deployment = (await execute("query($id: ID!){ deployment(id: $id){ id localId } }", authenticated_context, {"id": ids["deployment"]}))["deployment"]
    assert deployment["localId"] == "dep-1"

    # my_pod_at resolves the backend from the (user, client, org) context — no instance_id.
    my_pod = (await execute("query($localId: ID!){ myPodAt(localId: $localId){ id podId } }", authenticated_context, {"localId": "pod-1"}))["myPodAt"]
    assert my_pod["id"] == ids["pod"]

    for_agent = (await execute("query($clientId: ID!){ podForAgent(clientId: $clientId){ id clientId } }", authenticated_context, {"clientId": "client-1"}))["podForAgent"]
    assert for_agent["id"] == ids["pod"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_update_pod_and_dump_logs(authenticated_context: HttpContext, flavour_id: str) -> None:
    setup = await setup_pod(authenticated_context, flavour_id)
    pod_id = setup["pod"]["id"]

    updated = (
        await execute(UPDATE_POD, authenticated_context, {"input": {"pod": pod_id, "localId": None, "status": "RUNNING"}})
    )["updatePod"]
    assert updated["id"] == pod_id
    assert updated["status"] == "RUNNING"

    dump = (await execute(DUMP_LOGS, authenticated_context, {"input": {"pod": pod_id, "logs": "hello logs"}}))["dumpLogs"]
    assert dump["id"] is not None
    assert dump["logs"] == "hello logs"


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_delete_pod(authenticated_context: HttpContext, flavour_id: str) -> None:
    setup = await setup_pod(authenticated_context, flavour_id)
    pod_id = setup["pod"]["id"]

    deleted = await execute(DELETE_POD, authenticated_context, {"input": {"id": pod_id}})
    assert deleted["deletePod"] is not None

    pods = (await execute("query{ pods { id } }", authenticated_context))["pods"]
    assert pod_id not in [p["id"] for p in pods]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pods_ordering_and_filtering(authenticated_context: HttpContext, flavour_id: str) -> None:
    """Exercise the new `ordering` and `filters` inputs on the pods list query."""
    setup = await setup_pod(authenticated_context, flavour_id, pod_local_id="pod-a")
    # A second pod on the same backend (clients are 1:1 with backends).
    second = (
        await execute(
            CREATE_POD,
            authenticated_context,
            {"input": {"deployment": setup["deployment"]["id"], "localId": "pod-b", "clientId": "client-1"}},
        )
    )["createPod"]

    first_id, second_id = setup["pod"]["id"], second["id"]

    asc = (
        await execute(
            "query($ordering: [PodOrder!]){ pods(ordering: $ordering){ id } }",
            authenticated_context,
            {"ordering": [{"id": "ASC"}]},
        )
    )["pods"]
    assert [p["id"] for p in asc] == sorted([first_id, second_id], key=int)

    desc = (
        await execute(
            "query($ordering: [PodOrder!]){ pods(ordering: $ordering){ id } }",
            authenticated_context,
            {"ordering": [{"id": "DESC"}]},
        )
    )["pods"]
    assert [p["id"] for p in desc] == sorted([first_id, second_id], key=int, reverse=True)

    # filters: narrow to a single pod by id.
    filtered = (
        await execute(
            "query($filters: PodFilter){ pods(filters: $filters){ id } }",
            authenticated_context,
            {"filters": {"ids": [second_id]}},
        )
    )["pods"]
    assert [p["id"] for p in filtered] == [second_id]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_list_queries_are_org_scoped(authenticated_context: HttpContext, other_org_context: HttpContext, flavour_id: str) -> None:
    """Backend/Pod/Resource list queries prescope by organization.

    Backend filters on its own ``organization``; Pod and Resource inherit it via
    ``backend__organization`` (see their get_queryset). The authed user sees its rows;
    a user in another org sees none of them.
    """
    await setup_pod(authenticated_context, flavour_id)

    for field in ("backends", "pods", "resources"):
        query = "query{ %s { id } }" % field

        mine = (await execute(query, authenticated_context))[field]
        assert len(mine) == 1, f"{field} should be visible to its own org"

        theirs = (await execute(query, other_org_context))[field]
        assert theirs == [], f"{field} must not leak to another org"
