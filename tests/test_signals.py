"""kabinet's model signals: what it declares to the hub's rekuest, and that a save reaches it signed.

The save goes to a real local HTTP server standing in for rekuest's signal intake, and is
checked the way rekuest checks it (the instance-key JWT, the body).
"""

import pytest
from arkitekt_service import trust
from authentikate.models import Organization

from kabinet_server.service import service
from tests.utils import Intake

EXPECTED = {
    "@kabinet/release": ["CREATED", "UPDATED"],
    "@kabinet/flavour": ["CREATED", "UPDATED"],
    "@kabinet/definition": ["CREATED", "UPDATED"],
    "@kabinet/deployment": ["CREATED", "UPDATED", "DELETED"],
    "@kabinet/pod": ["CREATED", "UPDATED", "DELETED"],
    "@kabinet/app": ["CREATED"],
    "@kabinet/githubrepo": ["CREATED", "DELETED"],
}


def _organization() -> Organization:
    return Organization.objects.get_or_create(
        identifier="static_issuer#signals-test-org"
    )[0]


def test_the_manifest_declares_every_model_signal() -> None:
    assert {
        s["identifier"]: s["kinds"] for s in service.manifest()["signals"]
    } == EXPECTED


def test_the_manifest_lists_what_kabinet_hosts_with_its_descriptors() -> None:
    hosted = {s["identifier"]: s for s in service.manifest()["structures"]}
    # Everything kabinet hosts is signalled, and nothing else is.
    assert set(hosted) == set(EXPECTED)
    assert hosted["@kabinet/pod"]["label"] == "Pod"
    assert [(d["key"], d["type"]) for d in hosted["@kabinet/pod"]["descriptors"]] == [
        ("@kabinet/status", "STRING"),
        ("@kabinet/backend_kind", "STRING"),
    ]
    assert (
        hosted["@kabinet/deployment"]["descriptors"]
        == hosted["@kabinet/pod"]["descriptors"]
    )
    assert [
        (d["key"], d["type"]) for d in hosted["@kabinet/definition"]["descriptors"]
    ] == [
        ("@kabinet/kind", "STRING"),
        ("@kabinet/pure", "BOOL"),
        ("@kabinet/idempotent", "BOOL"),
        ("@kabinet/n_args", "INT"),
        ("@kabinet/n_returns", "INT"),
    ]
    assert [
        (d["key"], d["type"]) for d in hosted["@kabinet/flavour"]["descriptors"]
    ] == [
        ("@kabinet/flavour_name", "STRING"),
        ("@kabinet/selector_kinds", "LIST"),
        ("@kabinet/gpu", "STRING"),
        ("@kabinet/arch", "LIST"),
        ("@kabinet/min_ram_mb", "INT"),
        ("@kabinet/min_vram_mb", "INT"),
    ]
    assert [
        (d["key"], d["type"]) for d in hosted["@kabinet/release"]["descriptors"]
    ] == [("@kabinet/version", "STRING"), ("@kabinet/channel", "STRING")]
    # A signal carries exactly the keys its structure declares.
    for signal in service.manifest()["signals"]:
        assert signal["descriptors"] == [
            d["key"] for d in hosted[signal["identifier"]]["descriptors"]
        ], signal["identifier"]
    assert (
        hosted["@kabinet/app"]["descriptors"]
        == hosted["@kabinet/githubrepo"]["descriptors"]
        == []
    )


@pytest.mark.django_db(transaction=True)
def test_a_save_is_signalled_signed_by_this_instance(intake: Intake) -> None:
    from bridge.models import App

    org = _organization()
    obj = App.objects.create(identifier="signalled.app", organization=org)

    (received,) = intake.of("@kabinet/app")
    assert (
        received.json["kind"],
        received.json["object"],
        received.json["organization"],
    ) == ("CREATED", str(obj.pk), org.identifier)
    assert received.path == "/agi/signal/kabinet"
    verified = trust.verify(
        "POST",
        received.path,
        received.body,
        received.headers["Authorization"],
        audience="rekuest",
    )
    assert verified.issuer == "kabinet"
