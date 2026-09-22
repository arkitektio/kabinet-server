"""The rendered GraphQL schema must match the committed ``schema.graphql``.

``schema.graphql`` is this service's published contract. One copy lives downstream
— the turms client in ``packages/kabinet`` — and it is kept in sync by hand. A
second copy used to sit at ``configs/schemas/kabinet_v1.graphql``, bind-mounted into
the rekuest container; that is where the stale ``order:`` argument survived long
after the server renamed it to ``ordering:``. Nothing ever read it, so it is gone.

This test turns any schema change into a reviewable diff of one tracked file.
It needs no database: it only imports and stringifies the schema, so it must
stay off the ``backend_stack`` fixture and stay fast.

Regenerate with::

    python manage.py printschema
"""

import difflib
import re

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
            f"whether packages/kabinet needs regenerating too.\n\n{diff}"
        )


def test_schema_sdl_is_not_empty():
    """Guard against a schema that builds but renders to nothing."""
    assert render_sdl().strip(), "Schema SDL should not be empty"


#: The types that publish their stored vector as an `Embedding` string.
EMBEDDING_TYPES = {"App", "Definition", "Flavour", "GithubRepo"}


def _fields_named_embedding(sdl: str) -> dict[str, set[str]]:
    """``{"type"|"input": {names of the definitions carrying an `embedding` field}}``."""
    found: dict[str, set[str]] = {"type": set(), "input": set()}
    kind = name = None
    for line in sdl.splitlines():
        header = re.match(r"(type|input|interface)\s+(\w+)", line)
        if header:
            kind, name = header.group(1), header.group(2)
        elif line.startswith("}"):
            kind = name = None
        elif kind in found and re.match(r"\s+embedding(\(|:)", line):
            found[kind].add(name)
    return found


def test_only_the_embedded_types_publish_a_vector():
    """A vector is readable, and only where a model actually carries one.

    This used to assert the word "embedding" appeared nowhere in the SDL at all. The vectors
    are published now -- as one self-describing `Embedding` string per row -- so the blanket
    ban is gone, but the half of it that mattered is not: the exact set of types is pinned,
    so a vector column cannot arrive on a type by accident.
    """
    assert _fields_named_embedding(render_sdl())["type"] == EMBEDDING_TYPES


def test_no_input_accepts_an_embedding():
    """Read-only: a client may not write a vector, or the healer's contract is a fiction."""
    assert _fields_named_embedding(render_sdl())["input"] == set()
