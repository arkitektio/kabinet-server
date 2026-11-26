"""The matching engine: which definitions satisfy a port demand.

Rekuest's (``facade/managers.py``) on the JSONB a definition keeps its ports in: the same
match fields, the same demand sets (``anyDemands``), unbounded nesting and the same
``requires`` / ``provides`` check. Change one, change both.
"""

from __future__ import annotations

import json
import re
import typing as t
from dataclasses import dataclass

from django.db.models.expressions import RawSQL

from rekuest_core.inputs.types import PortMatchInput

if t.TYPE_CHECKING:
    from bridge.inputs import PortDemandInput

#: The constraints a port states on the objects that flow through it, by demand type: an
#: argument ``requires``, a return ``provides``.
CONSTRAINT_FIELD = {"args": "requires", "returns": "provides"}


def _jsonpath_condition(constraint: str) -> str:
    """One stored ``{key, operator, value}`` constraint as the JSONPath predicate rekuest compiles.

    The SQL twin of rekuest's ``facade.descriptors._compile_descriptor_condition``, read off
    the port's JSON instead of compiled at write time: kabinet keeps its ports as JSONB, and a
    constraint asked of the row as it is needs no column to keep in step. Keys and values are
    rendered as JSON text, which is valid JSONPath for the same reason it is in rekuest. What
    rekuest would refuse to compile (an unknown operator, a list where a scalar belongs)
    compiles to ``false`` here: the port accepts nothing rather than failing the query, and
    never to NULL, which ``string_agg`` would drop and so lift the constraint.
    """
    key = f"to_jsonb(CASE WHEN left({constraint}->>'key', 2) = '$.' THEN substr({constraint}->>'key', 3) ELSE {constraint}->>'key' END)::text"
    path = f"'$.' || {key}"
    value = f"{constraint}->'value'"
    scalar = f"jsonb_typeof({value}) NOT IN ('array', 'object')"
    member = "jsonb_typeof(member) NOT IN ('array', 'object')"

    def compare(op: str, suffix: str = "") -> str:
        return f"CASE WHEN {scalar} THEN {path} || '{suffix} {op} ' || ({value})::text ELSE 'false' END"

    def listed(op: str, joiner: str, empty: str) -> str:
        # A list member that is not a scalar has no JSONPath literal: it makes the list false.
        terms = f"(SELECT CASE WHEN bool_and({member}) IS NOT FALSE THEN string_agg({path} || ' {op} ' || member::text, ' {joiner} ') ELSE 'false' END FROM jsonb_array_elements({value}) member)"
        return f"CASE WHEN jsonb_typeof({value}) = 'array' THEN '(' || COALESCE({terms}, '{empty}') || ')' ELSE 'false' END"

    return (
        f"CASE {constraint}->>'operator'"
        f" WHEN 'EXISTS' THEN CASE WHEN {value} IS NULL OR {value} IN ('null'::jsonb, 'true'::jsonb) THEN 'exists(' || {path} || ')'"
        f" WHEN {value} = 'false'::jsonb THEN '!(exists(' || {path} || '))' ELSE 'false' END"
        f" WHEN 'EQUALS' THEN {compare('==')}"
        f" WHEN 'MATCHES' THEN {compare('==')}"
        f" WHEN 'NOT_EQUALS' THEN {compare('!=')}"
        f" WHEN 'GTE' THEN {compare('>=')}"
        f" WHEN 'LTE' THEN {compare('<=')}"
        f" WHEN 'CONTAINS' THEN {compare('==', '[*]')}"
        f" WHEN 'IN' THEN {listed('==', '||', 'false')}"
        f" WHEN 'NOT_IN' THEN {listed('!=', '&&', 'true')}"
        " ELSE 'false' END"
    )


def accepts_object(port: str, field: str, object_param: str) -> str:
    """Whether the port at ``port`` (a JSONB expression) accepts the candidate object.

    Rekuest's micro-constraint: every constraint of the port, AND-ed into one JSONPath, must
    match the object, evaluated silently so a value of the wrong type is a miss and not an
    error. A port without constraints accepts any object, as a NULL ``compiled_jsonpath`` does
    there.
    """
    constraints = f"{port}->'{field}'"
    compiled = f"(SELECT string_agg({_jsonpath_condition('constraint_')}, ' && ') FROM jsonb_array_elements({constraints}) constraint_)"
    return f"(jsonb_typeof({constraints}) IS DISTINCT FROM 'array' OR jsonb_array_length({constraints}) = 0 OR COALESCE(jsonb_path_match(%({object_param})s::jsonb, {compiled}::jsonpath, '{{}}'::jsonb, true), false))"


def candidate_object(item: PortMatchInput) -> str:
    """The match's descriptors as the object they describe (a repeated key: the last wins)."""
    return json.dumps(
        {descriptor.key: descriptor.value for descriptor in item.descriptors or []}
    )


#: The table the demands select from.
DEFINITION_TABLE = "bridge_definition"

#: The named bind parameters of a statement built here.
Params = dict[str, int | str | bool]
#: Positional bind parameters, as a ``RawSQL`` embedded in an ORM query takes them.
PositionalParams = list[int | str | bool]


@dataclass(frozen=True)
class PortDemand:
    """What the ports on one side of a definition (its args, or its returns) must look like."""

    kind: t.Literal["args", "returns"]
    matches: list[PortMatchInput] | None = None
    force_length: int | None = None
    force_non_nullable_length: int | None = None
    force_structure_length: int | None = None

    @classmethod
    def of(cls, demand: PortDemandInput) -> PortDemand:
        """The demand a GraphQL ``PortDemandInput`` states."""
        return cls(
            kind=_demand_kind(demand.kind.value),
            matches=list(demand.matches) if demand.matches is not None else None,
            force_length=demand.force_length,
            force_non_nullable_length=demand.force_non_nullable_length,
            force_structure_length=demand.force_structure_length,
        )


def _demand_kind(kind: str) -> t.Literal["args", "returns"]:
    """Which side of a definition a demand is about."""
    if kind == "args":
        return "args"
    if kind == "returns":
        return "returns"
    raise ValueError("Type must be either 'args' or 'returns'")


def _elements(ports: str) -> str:
    """``ports`` (a JSONB expression) as rows; anything but an array (a missing or null
    ``children``) is no rows, where ``jsonb_array_elements`` would raise on a scalar."""
    return f"jsonb_array_elements(CASE WHEN jsonb_typeof({ports}) = 'array' THEN {ports} ELSE '[]'::jsonb END)"


def _build_match_exists(
    match: PortMatchInput,
    ports: str,
    field: str,
    id_path: str,
    params: Params,
    root: bool,
) -> str:
    """One ``EXISTS`` over the ports at ``ports`` for a single match: rekuest's
    ``_build_match_exists`` on the JSONB a definition keeps its ports in.

    A root match scans the definition's ``args`` / ``returns``, a child its parent port's
    ``children``; children recurse, so nesting depth is unbounded. ``at`` is a port's 0-based
    position among its siblings, as rekuest's ``index``. The ``descriptors`` activate the
    object-level check: the port's ``requires`` / ``provides`` must accept the object they
    describe (``accepts_object``).
    """
    alias = f"p_{id_path}"
    port = f"{alias}.item"
    conditions: list[str] = []

    if match.at is not None:
        key = f"at_{id_path}"
        # WITH ORDINALITY counts from 1.
        params[key] = match.at + 1
        conditions.append(f"{alias}.idx = %({key})s")

    if match.key is not None:
        key = f"key_{id_path}"
        params[key] = match.key
        conditions.append(f"{port}->>'key' = %({key})s")

    if match.kind is not None:
        key = f"kind_{id_path}"
        params[key] = match.kind.value
        conditions.append(f"{port}->>'kind' = %({key})s")

    if match.identifier is not None:
        key = f"ident_{id_path}"
        params[key] = match.identifier
        conditions.append(f"{port}->>'identifier' = %({key})s")

    if match.dimension is not None:
        key = f"dim_{id_path}"
        params[key] = match.dimension
        conditions.append(f"{port}->>'dimension' = %({key})s")

    if match.nullable is not None:
        # A stored port states its nullability (``PortModel.nullable`` defaults to false).
        key = f"null_{id_path}"
        params[key] = match.nullable
        conditions.append(
            f"COALESCE(({port}->>'nullable')::boolean, false) = %({key})s"
        )

    if match.descriptors and root:
        # As in rekuest: a root match with ONLY descriptors would evaluate the constraints
        # against every root port of the organization; a structural field must narrow first.
        # A child is exempt, its parent already narrows.
        if all(
            value is None
            for value in (
                match.at,
                match.key,
                match.kind,
                match.identifier,
                match.dimension,
            )
        ):
            raise ValueError(
                "A root port match with descriptors must also narrow structurally (identifier, kind, key, at or dimension) — descriptor-only matches would scan every port in the organization."
            )
    if match.descriptors:
        key = f"obj_{id_path}"
        params[key] = candidate_object(match)
        conditions.append(accepts_object(port, field, key))

    for child_index, child in enumerate(match.children or []):
        conditions.append(
            _build_match_exists(
                child,
                f"{port}->'children'",
                field,
                f"{id_path}_{child_index}",
                params,
                root=False,
            )
        )

    inner = " AND ".join(conditions) if conditions else "TRUE"
    return f"EXISTS (SELECT 1 FROM {_elements(ports)} WITH ORDINALITY AS {alias}(item, idx) WHERE {inner})"


def _root_count(
    ports: str, condition: str, key: str, value: int, params: Params
) -> str:
    """A ``(SELECT COUNT(*) ...) = N`` clause over a definition's root ports."""
    params[key] = value
    return f"(SELECT COUNT(*) FROM {_elements(ports)} AS pc(item) WHERE {condition}) = %({key})s"


def _port_demand_sql(
    demands: t.Sequence[PortDemand], organization_id: int | str | None = None
) -> tuple[str, Params]:
    """The (sql, named params) selecting the ids of the definitions satisfying EVERY demand."""
    alias = "d"
    clauses: list[str] = []
    params: Params = {}

    if organization_id is not None:
        params["org"] = organization_id
        clauses.append(f"{alias}.organization_id = %(org)s")

    for demand_index, demand in enumerate(demands):
        ports = f"{alias}.{demand.kind}"
        field = CONSTRAINT_FIELD[demand.kind]

        for match_index, match in enumerate(demand.matches or []):
            clauses.append(
                _build_match_exists(
                    match,
                    ports,
                    field,
                    f"{demand_index}_{match_index}",
                    params,
                    root=True,
                )
            )

        if demand.force_length is not None:
            key = f"force_length_{demand_index}"
            params[key] = demand.force_length
            clauses.append(
                f"jsonb_array_length(CASE WHEN jsonb_typeof({ports}) = 'array' THEN {ports} ELSE '[]'::jsonb END) = %({key})s"
            )

        if demand.force_non_nullable_length is not None:
            clauses.append(
                _root_count(
                    ports,
                    "NOT COALESCE((pc.item->>'nullable')::boolean, false)",
                    f"force_non_nullable_{demand_index}",
                    demand.force_non_nullable_length,
                    params,
                )
            )

        if demand.force_structure_length is not None:
            clauses.append(
                _root_count(
                    ports,
                    "pc.item->>'kind' = 'STRUCTURE'",
                    f"force_structure_{demand_index}",
                    demand.force_structure_length,
                    params,
                )
            )

    if not clauses:
        raise ValueError("No search params provided")

    sql = f"SELECT {alias}.id FROM {DEFINITION_TABLE} {alias} WHERE " + " AND ".join(
        clauses
    )
    return sql, params


_NAMED_PARAM_RE = re.compile(r"%\((\w+)\)s")


def _to_positional(sql: str, params: Params) -> tuple[str, PositionalParams]:
    """Convert pyformat named placeholders to positional ``%s`` ones.

    ``RawSQL`` params are combined with the rest of the query's params into one flat
    sequence by the ORM compiler, so a mapping cannot be passed through — the same
    statement needs its params positional to be embeddable as a subquery.
    """
    ordered_keys = _NAMED_PARAM_RE.findall(sql)
    return _NAMED_PARAM_RE.sub("%s", sql), [params[key] for key in ordered_keys]


def get_port_demand_subquery(
    demands: t.Sequence[PortDemand], organization_id: int | str
) -> RawSQL:
    """The definitions of the organization satisfying every demand, as a ``RawSQL`` id
    subquery for ``Q(id__in=...)``.

    Nested in the list's own query: one round trip, no ids materialized in Python, and
    composable with ``OR`` / ``NOT``. A guest's narrowing to their collaborations stays the
    list's; this only ever keeps rows of the request's organization, a superset of theirs.
    """
    return RawSQL(*_to_positional(*_port_demand_sql(demands, organization_id)))


def get_any_port_demand_subquery(
    sets: t.Sequence[t.Sequence[PortDemand]], organization_id: int | str
) -> RawSQL:
    """The definitions satisfying every demand of at least one set, as one ``UNION`` id subquery.

    Spelled out rather than left to ``OR``, as in rekuest: ``id IN (A) OR id IN (B)`` cannot
    be a semi-join, ``id IN (A UNION B)`` can.
    """
    if any(len(demands) == 0 for demands in sets):
        raise ValueError("Every set of anyDemands needs at least one demand.")
    statements = [
        _to_positional(*_port_demand_sql(demands, organization_id)) for demands in sets
    ]
    return RawSQL(
        " UNION ".join(sql for sql, _ in statements),
        [param for _, params in statements for param in params],
    )
