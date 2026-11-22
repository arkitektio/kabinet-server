import json
import os
import threading
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

import yaml
from aiohttp import web
from joserfc.jwk import OKPKey
from kante.context import HttpContext
from strawberry.types import ExecutionResult

from bridge.repo.fetch import RepoCoordinates

#: The repository the fake raw file host (the ``fake_github`` fixture) serves.
COORDINATES = RepoCoordinates("arkitektio-apps", "ome", "main")

#: The instance key the ``intake`` fixture configures and trusts.
INTAKE_KEY = OKPKey.generate_key("Ed25519")


class ServeRepo(Protocol):
    """The ``fake_github`` fixture: serve ``{repo path: body or status}`` as the raw file host."""

    async def __call__(
        self,
        tree: Mapping[str, str | int],
        handler: Callable[[web.Request], Awaitable[web.StreamResponse]] | None = None,
    ) -> RepoCoordinates: ...


@dataclass
class ReceivedSignal:
    """One request the intake received."""

    path: str
    headers: dict[str, str]
    body: bytes
    #: The body as ``json.loads`` reads it.
    json: dict[str, Any]


class Intake:
    """A local HTTP server standing in for rekuest's signal intake (the ``intake`` fixture)."""

    def __init__(self) -> None:
        self.received: list[ReceivedSignal] = []
        intake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = self.rfile.read(int(self.headers["Content-Length"]))
                intake.received.append(
                    ReceivedSignal(
                        path=self.path,
                        headers=dict(self.headers),
                        body=body,
                        json=json.loads(body),
                    )
                )
                self.send_response(202)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def of(
        self, identifier: str, count: int = 1, timeout: float = 10
    ) -> list[ReceivedSignal]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = [r for r in self.received if r.json["identifier"] == identifier]
            if len(found) >= count:
                return found
            time.sleep(0.05)
        return [r for r in self.received if r.json["identifier"] == identifier]


async def execute(
    query: str, context: HttpContext, variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run a GraphQL document against the schema and assert it produced data.

    Mirrors how ``test_inspect_repo.test_create_github_repo`` drives the schema, so
    endpoint tests can stay one-liners: it fails loudly on any GraphQL error.
    """

    result = await execute_raw(query, context, variables)
    assert not result.errors, result.errors
    assert result.data is not None
    return result.data


async def execute_raw(
    query: str, context: HttpContext, variables: dict[str, Any] | None = None
) -> ExecutionResult:
    """Run a GraphQL document and hand back the raw result, errors and all.

    ``execute`` asserts success, so it cannot express a negative case. Every test that
    needed one -- a cross-tenant read, a validation failure, a nullable field coming back
    null -- had to re-declare this escape hatch locally; ``test_org_scoping`` carried its
    own copy.
    """
    from kabinet_server.schema import schema

    return await schema.execute(
        query, variable_values=variables or {}, context_value=context
    )


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


def load_yaml(path: str) -> dict[str, Any]:
    """The YAML document at ``path`` (relative to ``tests/``), as ``yaml.safe_load`` reads it."""
    with open(build_relative_dir(path)) as f:
        return yaml.safe_load(f)
