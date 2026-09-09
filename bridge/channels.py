"""The pod event channel, and the group names it is keyed by.

Broadcasts used to carry no groups at all, which meant they landed on kante's default
group ``["default"]`` while subscribers joined ``[pod_id]`` or the literal ``"all"`` --
so no message could ever reach a listener. The group names live here, next to the
channel, so the publisher (`bridge/signals.py`) and the subscribers
(`bridge/subscriptions/pod.py`) cannot drift apart again.

The organization group is what makes the fan-out subscription tenant-safe: a listener
only ever joins its own organization's group, so another tenant's events are not
filtered out after arrival -- they never arrive.
"""

from kante.channel import build_channel

from bridge.channel_signals import PodSignal

pod_channel = build_channel(PodSignal)


def pod_group(pod_id: object) -> str:
    """The group carrying events for one specific pod."""
    return f"pod-{pod_id}"


def org_group(organization_id: object) -> str:
    """The group carrying events for every pod belonging to one organization."""
    return f"pod-org-{organization_id}"
