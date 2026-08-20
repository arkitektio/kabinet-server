import typing as t

from django.db import connection

from rekuest_core.inputs.types import PortMatchInput


def build_child_recursively(item: PortMatchInput, prefix, value_path, parts, params):
    if item.key:
        parts.append(f"{prefix}->>'key' = %({value_path}_key)s")
        params[f"{value_path}_key"] = item.key

    if item.kind:
        parts.append(f"{prefix}->>'kind' = %({value_path}_kind)s")
        params[f"{value_path}_kind"] = item.kind.value

    if item.identifier:
        parts.append(f"{prefix}->>'identifier' = %({value_path}_identifier)s")
        params[f"{value_path}_identifier"] = item.identifier

    if item.children:
        # Nested children are flattened one level up by `build_sql_for_item_recursive`;
        # a child that carries its own children is not something this SQL can express.
        # (A recursive call used to follow this raise, unreachable, and it referenced
        # `item.child`, which `PortMatchInput` does not have.)
        raise ValueError("Children should not be present in the child item")


def build_sql_for_item_recursive(item: PortMatchInput, index: int, at_value: int | None = None, prefix: str = "arg"):
    sql_parts = []
    params = {}

    if at_value is not None:
        sql_parts.append(f"idx = %({prefix}_at_{index})s")
        params[f"{prefix}_at_{index}"] = at_value + 1

    if item.key:
        sql_parts.append(f"item->>'key' = %({prefix}_key_{index})s")
        params[f"{prefix}_key_{index}"] = item.key

    if item.kind:
        sql_parts.append(f"item->>'kind' = %({prefix}_kind_{index})s")
        params[f"{prefix}_kind_{index}"] = item.kind.value

    if item.identifier:
        sql_parts.append(f"item->>'identifier' = %({prefix}_identifier_{index})s")
        params[f"{prefix}_identifier_{index}"] = item.identifier

    if item.children:
        # Adjusting the prefix for recursion
        child_parts = []
        child_params = {}
        for idx, child in enumerate(item.children):
            build_child_recursively(
                child,
                f"item->'children'->{idx + 1}",
                f"children_{index}_{idx}",
                child_parts,
                child_params,
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
            sql_part, params = build_sql_for_item_recursive(item, index, at_value=item.at)
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
