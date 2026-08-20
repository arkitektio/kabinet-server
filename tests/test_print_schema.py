"""The rendered GraphQL schema must match the committed ``schema.graphql``.

``schema.graphql`` is this service's published contract. Two copies live
downstream — the turms client in ``packages/kabinet`` and the snapshot mounted
into the rekuest container at ``configs/schemas/kabinet_v1.graphql`` — and both
were previously kept in sync by hand, which is how the stale ``order:`` argument
survived in the latter long after the server renamed it to ``ordering:``.

This test turns any schema change into a reviewable diff of one tracked file.
It needs no database: it only imports and stringifies the schema, so it must
stay off the ``backend_stack`` fixture and stay fast.

Regenerate with::

    python manage.py printschema
"""

import difflib

from bridge.management.commands.printschema import SCHEMA_PATH, render_sdl


def test_schema_snapshot_is_current():
    """The committed SDL is byte-identical to what the schema renders today."""
    assert SCHEMA_PATH.exists(), f"{SCHEMA_PATH} is missing. Run `python manage.py printschema`."

    rendered = render_sdl()
    committed = SCHEMA_PATH.read_text()

    if committed != rendered:
        diff = "".join(
            difflib.unified_diff(
                committed.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile="schema.graphql (committed)",
                tofile="schema.graphql (rendered)",
            )
        )
        raise AssertionError(
            "The GraphQL schema changed but schema.graphql was not regenerated.\n"
            "Run `python manage.py printschema` and commit the result — then check\n"
            "whether packages/kabinet and configs/schemas/kabinet_v1.graphql need\n"
            f"regenerating too.\n\n{diff}"
        )


def test_schema_sdl_is_not_empty():
    """Guard against a schema that builds but renders to nothing."""
    assert render_sdl().strip(), "Schema SDL should not be empty"
