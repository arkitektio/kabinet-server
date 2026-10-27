"""What a flavour's bloks draw: their component trees, parsed once and stored beside them.

An app sends its bloks as an SDK writes them, as BSX ``source``. ``Flavour.bloks`` keeps them
exactly so (a stored blok must stay a valid ``BlokImplementationInput``, which refuses one with
both a ``source`` and ``components``); what a client renders is ``Flavour.blok_renders``, keyed
by the blok's key:

- ``component_tree``: the tree as a list of roots, in the wire spelling (snake_case, nothing
  that is None), which is what rekuest serves as ``Blok.componentTree``. Parsed by arkitekt-spec's
  v2 parser (``arkitekt_spec.blok.bsx``), the one takt's own is held to. Null when the source
  does not parse. kabinet reads blok language v2 only.
- ``hash``: ``sha256:`` of what the blok draws (its tree, context and what it declares beside
  it: locals, demo, queries, subscriptions, catalogs, module), so a client can keep a
  drawing under it. kabinet's own: it is not rekuest's ``Blok.hash``.
- ``parse_error``: why the source does not parse, or null.

``Flavour.action_logos`` maps each action's definition hash to the key of the ACTION_LOGO blok
its implementation names as its ``logo``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from arkitekt_spec.blok.bsx import parse_bsx

#: What a blok declares beside its tree that changes what it draws.
DECLARED = ("vocab", "catalogs", "module", "locals", "demo", "queries", "subscriptions")


def _tree(blok: dict[str, Any]) -> list[dict[str, Any]]:
    components = blok.get("components")
    if components:
        return components
    source = blok.get("source")
    if not source:
        raise ValueError("The blok has neither components nor a source")
    return [parse_bsx(source).model_dump(mode="json", exclude_none=True)]


def blok_hash(component_tree: Any, context: Any, declared: dict[str, Any]) -> str:
    """``sha256:`` of what a blok draws: the same tree, context and declarations hash alike."""
    parts = {"component_tree": component_tree, "context": context}
    parts.update({key: value for key, value in declared.items() if value not in (None, [], {})})
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def render_blok(blok: dict[str, Any]) -> dict[str, Any]:
    """The render of one stored blok (``model_dump(mode="json")`` of a ``BlokImplementationInput``)."""
    try:
        tree = _tree(blok)
        error = None
    except Exception as e:  # noqa: BLE001 - any parser failure is the blok's, never the import's
        tree, error = None, str(e) or e.__class__.__name__
    return {
        "component_tree": tree,
        "hash": blok_hash(tree, blok.get("context"), {key: blok.get(key) for key in DECLARED}),
        "parse_error": error,
    }


def render_bloks(bloks: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The renders of a flavour's bloks, by key."""
    return {blok["key"]: render_blok(blok) for blok in bloks if blok.get("key")}


def action_logos(pairs: Iterable[tuple[str, str | None]]) -> dict[str, str]:
    """``{definition hash: logo blok key}`` from ``(definition hash, implementation.logo)`` pairs."""
    return {definition_hash: logo for definition_hash, logo in pairs if logo}
