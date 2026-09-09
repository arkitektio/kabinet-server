"""The selector vocabulary: one model set from input to storage to output.

The old split models made a stored ``cpu`` or ``oneapi`` selector crash every
query embedding the flavour (the output union either forbade the input's
fields or lacked the kind entirely). These tests push every kind through the
real ``createAppImage`` wire and read the selectors back over GraphQL, so
that class of drift cannot return unnoticed. The migration's rewrite function
is covered separately and needs no database.
"""

import importlib

import pytest
import yaml
from kante.context import HttpContext

from bridge.repo.selectors import SelectorFieldJson
from tests.utils import build_relative_dir, execute

_migration = importlib.import_module("bridge.migrations.0005_selector_vocabulary")


ALL_KINDS_WIRE = [
    {"kind": "cuda", "computeCapability": "8.6", "memory": 8000, "count": 2},
    {"kind": "cpu", "minCount": 4, "arch": "arm64"},
    {"kind": "ram", "min": 16000},
    {"kind": "rocm", "apiVersion": "5.7"},
    {"kind": "oneapi", "oneapiVersion": "2024.1"},
    {"kind": "label", "key": "microscope", "value": "lightsheet", "required": False, "weight": 10},
]

CREATE_APP_IMAGE = """
    mutation CreateAppImage($input: AppImageInput!) {
        createAppImage(input: $input) { id flavours { id } }
    }
"""

FLAVOUR_SELECTORS = """
    query Flavour($id: ID!) {
        flavour(id: $id) {
            selectors {
                kind
                required
                weight
                ... on CudaSelector { computeCapability memory count }
                ... on CPUSelector { minCount arch }
                ... on RAMSelector { min }
                ... on RocmSelector { apiVersion }
                ... on OneApiSelector { oneapiVersion }
                ... on LabelSelector { key value }
            }
        }
    }
"""


def _app_image_with_all_selectors() -> dict:
    with open(build_relative_dir("deployments/deployments.yaml")) as f:
        app_image = yaml.safe_load(f)["app_images"][0]
    app_image["inspection"]["implementations"] = []
    app_image["selectors"] = ALL_KINDS_WIRE
    return app_image


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_every_selector_kind_round_trips(authenticated_context: HttpContext):
    """Author → store → serve for all six kinds, through the real wire."""
    created = await execute(
        CREATE_APP_IMAGE, authenticated_context, {"input": _app_image_with_all_selectors()}
    )
    flavour_id = created["createAppImage"]["flavours"][0]["id"]

    served = await execute(FLAVOUR_SELECTORS, authenticated_context, {"id": flavour_id})
    selectors = served["flavour"]["selectors"]

    by_kind = {selector["kind"]: selector for selector in selectors}
    assert set(by_kind) == {"cuda", "cpu", "ram", "rocm", "oneapi", "label"}

    assert by_kind["cuda"]["computeCapability"] == "8.6"
    assert by_kind["cuda"]["memory"] == 8000
    assert by_kind["cuda"]["count"] == 2
    assert by_kind["cpu"]["minCount"] == 4
    assert by_kind["cpu"]["arch"] == "arm64"
    assert by_kind["ram"]["min"] == 16000
    assert by_kind["rocm"]["apiVersion"] == "5.7"
    assert by_kind["oneapi"]["oneapiVersion"] == "2024.1"
    # The hard/soft split survives the trip; defaults apply where unset.
    assert by_kind["label"] == {
        "kind": "label", "required": False, "weight": 10,
        "key": "microscope", "value": "lightsheet",
    }
    assert by_kind["cuda"]["required"] is True
    assert by_kind["cuda"]["weight"] == 1


def test_stored_json_round_trips_without_aliases():
    """Storage dumps python field names; the read side must accept them."""
    stored = [
        {"kind": "cuda", "compute_capability": "8.6", "cuda_cores": 100},
        {"kind": "cpu", "min_count": 2},
        {"kind": "oneapi", "oneapi_version": "2024.1"},
    ]
    parsed = SelectorFieldJson(selectors=stored).selectors
    assert [selector.kind for selector in parsed] == ["cuda", "cpu", "oneapi"]
    assert parsed[0].compute_capability == "8.6"


def test_migration_moves_cpu_memory_into_a_ram_selector():
    rewritten = _migration._rewrite(
        [
            {"kind": "cpu", "frequency": 2400, "memory": 8000},
            {"kind": "cuda", "cuda_cores": 100},
        ]
    )
    assert rewritten == [
        {"kind": "cpu", "frequency": 2400},
        {"kind": "ram", "min": 8000},
        {"kind": "cuda", "cuda_cores": 100},
    ]


def test_migration_drops_unknown_kinds():
    assert _migration._rewrite([{"kind": "service"}, {"kind": "ram", "min": 1}]) == [
        {"kind": "ram", "min": 1}
    ]
