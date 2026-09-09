import os
from typing import Any


async def execute(query: str, context: Any, variables: dict | None = None) -> dict:
    """Run a GraphQL document against the schema and assert it produced data.

    Mirrors how ``test_inspect_repo.test_create_github_repo`` drives the schema, so
    endpoint tests can stay one-liners: it fails loudly on any GraphQL error.
    """
    from kabinet_server.schema import schema

    result = await execute_raw(query, context, variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


async def execute_raw(query: str, context: Any, variables: dict | None = None):
    """Run a GraphQL document and hand back the raw result, errors and all.

    ``execute`` asserts success, so it cannot express a negative case. Every test that
    needed one -- a cross-tenant read, a validation failure, a nullable field coming back
    null -- had to re-declare this escape hatch locally; ``test_org_scoping`` carried its
    own copy.
    """
    from kabinet_server.schema import schema

    return await schema.execute(query, variable_values=variables or {}, context_value=context)


def build_relative_dir(path: str) -> str:
    """Build a relative directory from a path

    Parameters
    ----------
    path : str
        The path to build a relative directory from

    Returns
    -------
    str
        The relative directory
    """
    return os.path.join(os.path.dirname(__file__), path)
