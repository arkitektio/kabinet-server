"""What kabinet's objects say about themselves: the describers ``kabinet_server.service`` binds.

Each is stored on the row whenever it is saved (``stored_descriptors``), so a port's ``requires``
is answered by one indexed query and a signal carries what a picker filters on. Everything here
is read off the row itself, or off a row it points to (a deployment's backend): a flavour's
selectors, a definition's ports, a release's channel.

A flavour's hardware descriptors are what a backend MUST have to run it: they read its
``required`` selectors only, because a preference (``required: false``) is no minimum.
``@kabinet/selector_kinds`` is the exception: it names every kind of selector the flavour states.
"""

from bridge import models
from bridge.repo import selectors

Descriptors = dict[str, int | str | bool | list[str]]

#: The selector kinds that ask for an accelerator, each the value ``@kabinet/gpu`` names it by.
GPU_KINDS = ("cuda", "rocm", "oneapi")
#: ``@kabinet/gpu`` of a flavour that runs without an accelerator.
NO_GPU = "none"
#: ``@kabinet/gpu`` of a flavour that requires accelerators of more than one vendor: no single
#: vendor's backend runs it, so it matches none of theirs.
SEVERAL_GPUS = "multiple"


def flavour_descriptors(flavour: models.Flavour) -> Descriptors:
    """A flavour's descriptors: its variant name and the hardware its selectors ask a backend for."""
    stated = flavour.get_selectors()
    required = [selector for selector in stated if selector.required]
    gpus = sorted({selector.kind for selector in required if selector.kind in GPU_KINDS})
    return {
        "@kabinet/flavour_name": flavour.name,
        "@kabinet/selector_kinds": sorted({selector.kind for selector in stated}),
        "@kabinet/gpu": gpus[0] if len(gpus) == 1 else SEVERAL_GPUS if gpus else NO_GPU,
        "@kabinet/arch": sorted({selector.arch for selector in required if isinstance(selector, selectors.CpuSelector) and selector.arch}),
        "@kabinet/min_ram_mb": max((selector.min for selector in required if isinstance(selector, selectors.RamSelector) and selector.min), default=0),
        "@kabinet/min_vram_mb": max((selector.memory for selector in required if isinstance(selector, selectors.CudaSelector) and selector.memory), default=0),
    }


def release_descriptors(release: models.Release) -> Descriptors:
    """A release's descriptors: its version, and the channel it is the latest build of ("" for a release proper)."""
    return {"@kabinet/version": release.version, "@kabinet/channel": release.channel or ""}


def definition_descriptors(definition: models.Definition) -> Descriptors:
    """An action definition's descriptors: how it runs and how many ports it takes and gives."""
    return {
        "@kabinet/kind": str(definition.kind),
        "@kabinet/pure": bool(definition.pure),
        "@kabinet/idempotent": bool(definition.idempotent),
        "@kabinet/n_args": len(definition.args or []),
        "@kabinet/n_returns": len(definition.returns or []),
    }


def placement_descriptors(placed: models.Deployment | models.Pod) -> Descriptors:
    """A deployment's or a pod's descriptors: where it stands, and the kind of backend it runs on."""
    return {"@kabinet/status": str(placed.status), "@kabinet/backend_kind": placed.backend.kind}
