"""What a flavour's bloks draw: their component trees, parsed once and stored beside them.

An app sends its bloks as an SDK writes them, as BSX ``source``. ``Flavour.bloks`` keeps them
exactly so (a stored blok must stay a valid ``BlokImplementationInput``, which refuses one with
both a ``source`` and ``components``); what a client renders is ``Flavour.blok_renders``, keyed
by the blok's key:

- ``component_tree``: the tree as a list of roots, in the wire spelling (snake_case, nothing
  that is None), which is what rekuest serves as ``Blok.componentTree``. Parsed by arkitekt-spec's
  v2 parser (``arkitekt_spec.blok.bsx``), the one takt's own is held to. Null when the source
  does not parse. kabinet reads blok language v2 only: one ``<Blok kind=... context=...>`` root,
  whose ``<local>``, ``<query>`` and ``<subscription>`` nodes declare what the blok owns.
- ``hash``: ``sha256:`` of what the blok draws (its tree, context and what it declares beside
  it: demo, catalogs, module), so a client can keep a drawing under it. kabinet's own: it is
  not rekuest's ``Blok.hash``.
- ``parse_error``: why the source does not parse, or why its root is no ``<Blok>`` of the
  context it is sent as; null when neither.

``Flavour.action_logos`` maps each action's definition hash to the key of the action logo (a
LOGO blok whose root says ``kind="action"``) its implementation names as its ``logo``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from arkitekt_spec.blok.bsx import parse_bsx
from pydantic import ValidationError

from rekuest_core.inputs.models import ComponentNodeInputModel
from rekuest_core.vocabulary import BlokError, BlokHeader, blok_header

#: What a blok declares beside its tree that changes what it draws.
DECLARED = ("vocab", "catalogs", "module", "demo")


def _tree(blok: dict[str, Any]) -> list[dict[str, Any]]:
    components = blok.get("components")
    if components:
        return components
    source = blok.get("source")
    if not source:
        raise ValueError("The blok has neither components nor a source")
    return [parse_bsx(source).model_dump(mode="json", exclude_none=True)]


def header_of(component_tree: Any) -> BlokHeader:
    """What the ``<Blok>`` root of a stored tree (a list of roots) says.

    Raises:
        BlokError: ``blok.root`` or ``blok.attribute`` when the root is no readable ``<Blok>``.
        ValidationError: When the tree is no component tree at all.
    """
    return blok_header(ComponentNodeInputModel.model_validate(component_tree[0]))


def root_kind(component_tree: Any) -> str | None:
    """The kind a stored tree's ``<Blok>`` says (``agent``, ``action``, ...); None without one."""
    if not component_tree:
        return None
    try:
        return header_of(component_tree).kind
    except (BlokError, ValidationError):
        return None


def blok_hash(component_tree: Any, context: Any, declared: dict[str, Any]) -> str:
    """``sha256:`` of what a blok draws: the same tree, context and declarations hash alike."""
    parts = {"component_tree": component_tree, "context": context}
    parts.update(
        {key: value for key, value in declared.items() if value not in (None, [], {})}
    )
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def render_blok(blok: dict[str, Any]) -> dict[str, Any]:
    """The render of one stored blok (``model_dump(mode="json")`` of a ``BlokImplementationInput``)."""
    try:
        tree = _tree(blok)
        error = None
    except Exception as e:  # noqa: BLE001 - any parser failure is the blok's, never the import's
        tree, error = None, str(e) or e.__class__.__name__
    if tree is not None:
        try:
            said = header_of(tree).context
            context = blok.get("context")
            if context and said != context:
                error = f"It is sent as a {context} blok, but its <Blok> says {said}"
        except (BlokError, ValidationError) as e:
            error = str(e)
    return {
        "component_tree": tree,
        "hash": blok_hash(
            tree, blok.get("context"), {key: blok.get(key) for key in DECLARED}
        ),
        "parse_error": error,
    }


def render_bloks(bloks: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The renders of a flavour's bloks, by key."""
    return {blok["key"]: render_blok(blok) for blok in bloks if blok.get("key")}


def action_logos(pairs: Iterable[tuple[str, str | None]]) -> dict[str, str]:
    """``{definition hash: logo blok key}`` from ``(definition hash, implementation.logo)`` pairs."""
    return {definition_hash: logo for definition_hash, logo in pairs if logo}
