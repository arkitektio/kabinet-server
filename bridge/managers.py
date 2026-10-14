import json
import typing as t

from django.db import connection

from rekuest_core.inputs.types import PortMatchInput

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
    return json.dumps({descriptor.key: descriptor.value for descriptor in item.descriptors or []})


def build_port_conditions(item: PortMatchInput, port: str, value_path: str, field: str, parts: list[str], params: dict) -> None:
    """What ``item`` asks of one port, besides its position: shape, nullability, constraints.

    ``nullable`` and ``dimension`` used to be dropped here without a word, and ``descriptors``
    too: a demand carrying them came back with every structural match, which looks right and
    is not.
    """
    if item.key:
        parts.append(f"{port}->>'key' = %({value_path}_key)s")
        params[f"{value_path}_key"] = item.key

    if item.kind:
        parts.append(f"{port}->>'kind' = %({value_path}_kind)s")
        params[f"{value_path}_kind"] = item.kind.value

    if item.identifier:
        parts.append(f"{port}->>'identifier' = %({value_path}_identifier)s")
        params[f"{value_path}_identifier"] = item.identifier

    if item.dimension:
        parts.append(f"{port}->>'dimension' = %({value_path}_dimension)s")
        params[f"{value_path}_dimension"] = item.dimension

    if item.nullable is not None:
        # A stored port states its nullability (``PortModel.nullable`` defaults to false).
        parts.append(f"COALESCE(({port}->>'nullable')::boolean, false) = %({value_path}_nullable)s")
        params[f"{value_path}_nullable"] = item.nullable

    if item.descriptors:
        parts.append(accepts_object(port, field, f"{value_path}_object"))
        params[f"{value_path}_object"] = candidate_object(item)


def build_child_recursively(item: PortMatchInput, prefix, value_path, parts, params, field: str = "requires"):
    build_port_conditions(item, prefix, value_path, field, parts, params)

    if item.children:
        # Nested children are flattened one level up by `build_sql_for_item_recursive`;
        # a child that carries its own children is not something this SQL can express.
        # (A recursive call used to follow this raise, unreachable, and it referenced
        # `item.child`, which `PortMatchInput` does not have.)
        raise ValueError("Children should not be present in the child item")


def build_sql_for_item_recursive(item: PortMatchInput, index: int, at_value: int | None = None, prefix: str = "arg", field: str = "requires"):
    sql_parts = []
    params = {}

    if at_value is not None:
        sql_parts.append(f"idx = %({prefix}_at_{index})s")
        params[f"{prefix}_at_{index}"] = at_value + 1

    build_port_conditions(item, "item", f"{prefix}_{index}", field, sql_parts, params)

    if item.children:
        # Adjusting the prefix for recursion
        child_parts = []
        child_params = {}
        for idx, child in enumerate(item.children):
            build_child_recursively(
                child,
                # jsonb `->` on an array is 0-based (unlike the 1-based WITH ORDINALITY idx above).
                f"item->'children'->{idx}",
                f"children_{index}_{idx}",
                child_parts,
                child_params,
                field,
            )
        sql_parts += child_parts
        params.update(child_params)

    return (" AND ".join(sql_parts), params)


def build_params(
    search_params: list[PortMatchInput] | None,
    type: t.Literal["args", "returns"] = "args",
    force_length: t.Optional[int] = None,
    force_non_nullable_length: t.Optional[int] = None,
    force_structure_length: t.Optional[int] = None,
    model: str = "bridge_definition",
):
    individual_queries = []
    all_params = {}
    if search_params:
        for index, item in enumerate(search_params):
            sql_part, params = build_sql_for_item_recursive(item, index, at_value=item.at, field=CONSTRAINT_FIELD[type])
            if not sql_part:
                # Every field on `PortMatchInput` is optional, so a client can send `{}`.
                # That produced an empty predicate and rendered
                # `EXISTS (SELECT 1 FROM ... WHERE )` -- a `ProgrammingError` and a 500,
                # from a well-formed query. A match that constrains nothing matches
                # everything, so it simply contributes no clause.
                continue
            if type == "args":
                subquery = f"EXISTS (SELECT 1 FROM jsonb_array_elements(args) WITH ORDINALITY AS j(item, idx) WHERE {sql_part})"
            else:
                subquery = f"EXISTS (SELECT 1 FROM jsonb_array_elements(returns) WITH ORDINALITY AS j(item, idx) WHERE {sql_part})"

            individual_queries.append(subquery)
            all_params.update(params)

    if force_length is not None:
        individual_queries.append(f"jsonb_array_length({type}) = {force_length}")

    if force_non_nullable_length is not None:
        sql_part = "item->>'nullable'::text = 'false'"
        count_condition = f"""(SELECT COUNT(*) FROM jsonb_array_elements({type}) AS j(item) WHERE {sql_part}) = {force_non_nullable_length}"""
        individual_queries.append(count_condition)

    if force_structure_length is not None:
        sql_part = "item->>'kind' = 'STRUCTURE'"
        count_condition = f"""(SELECT COUNT(*) FROM jsonb_array_elements({type}) AS j(item) WHERE {sql_part}) = {force_structure_length}"""
        individual_queries.append(count_condition)

    if not individual_queries:
        raise ValueError("No search params provided")

    full_sql = f"SELECT id FROM {model} WHERE " + " AND ".join(individual_queries)

    return full_sql, all_params


def get_action_ids_by_demands(
    demands: list[PortMatchInput] = None,
    type: t.Literal["args", "returns"] = "args",
    force_length: t.Optional[int] = None,
    force_non_nullable_length: t.Optional[int] = None,
    force_structure_length: t.Optional[int] = None,
    model: str = "bridge_definition",
):
    if type not in ["args", "returns"]:
        raise ValueError("Type must be either 'args' or 'returns'")

    full_sql, all_params = build_params(
        demands,
        type=type,
        force_length=force_length,
        force_non_nullable_length=force_non_nullable_length,
        force_structure_length=force_structure_length,
        model=model,
    )

    with connection.cursor() as cursor:
        cursor.execute(full_sql, all_params)
        rows = cursor.fetchall()
        ids = [row[0] for row in rows]
        return ids


# `build_action_demand_params`, `build_state_params`, `filter_actions_by_demands`,
# `get_action_ids_by_action_demand` and `get_state_ids_by_demands` used to follow. None
# of them had a caller, and their default table names -- "facade_action",
# "facade_state_schema" and "facade_stateschema", three spellings of two tables -- name
# rekuest's schema, not kabinet's. Nothing in this database would have answered them.
