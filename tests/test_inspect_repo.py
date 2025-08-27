import pytest
from django.contrib.auth import get_user_model
from kabinet_server.schema import schema

from kante.context import HttpContext

@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_create_github_repo(db, authenticated_context: HttpContext):
    
    assert authenticated_context.request.organization is not None, "Organization should be set"

    query = """
        mutation {
            createGithubRepo(input: {identifier: "arkitektio-apps/ome"}) {
                id
            }
        }
    """

    sub = await schema.execute(
        query,
        context_value=authenticated_context,
    )

    assert sub.data, sub.errors

    assert sub.data["createGithubRepo"]["id"] is not None
