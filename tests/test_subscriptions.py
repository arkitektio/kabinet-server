"""The pod subscriptions, which did not work at all.

Four independent defects, none of which a test would have let through:

1. The resolvers called ``pod_channel.alisten(...)``. kante's ``Channel`` has ``listen``,
   ``broadcast`` and ``abroadcast`` -- there is no ``alisten``, so the first message was
   an ``AttributeError``.
2. Neither resolver contained a ``yield``. Annotated ``AsyncGenerator`` but built only
   from ``return`` statements, they were coroutines, and a coroutine cannot drive a
   subscription.
3. ``bridge/signals.py`` broadcast with no groups, which kante defaults to ``["default"]``,
   while listeners joined ``[pod_id]`` or the literal ``"all"``. Even with 1 and 2 fixed,
   no message could have arrived.
4. The schema declared ``PodUpdateMessage``; the resolvers built ``PodEvent``, a type in
   no schema at all. ``PodUpdateMessage`` was never constructed anywhere.

These tests drive the resolvers directly rather than over a websocket -- the whole suite
calls ``schema.execute`` rather than going through the transport -- so what they pin down
is the group keying and the event shape. The transport itself
(``kante.testing.GraphQLWebSocketTestClient``) is still uncovered.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from asgiref.sync import sync_to_async
from kante.context import HttpContext

from tests.test_pods import setup_pod


@dataclass
class _Info:
    """The one attribute the subscription resolvers read off ``Info``.

    The rest of the suite drives resolvers through ``schema.execute``, which builds a
    real ``Info``. Subscriptions are async generators, so they are driven directly here
    -- and all they take from ``info`` is ``info.context``.
    """

    context: Any


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pod_signal_broadcasts_to_pod_and_org_groups(authenticated_context: HttpContext, flavour_id: str):
    """Saving a pod publishes to both its own group and its organization's group.

    The publisher and the subscribers agree on the group names because both derive them
    from ``bridge.channels``; before that they simply did not overlap.
    """
    from bridge import channels

    sent: list[tuple[object, list[str]]] = []

    def record(message, groups=None):
        sent.append((message, groups))

    original = channels.pod_channel.broadcast
    channels.pod_channel.broadcast = record
    try:
        ids = await setup_pod(authenticated_context, flavour_id)
    finally:
        channels.pod_channel.broadcast = original

    assert sent, "saving a Pod should have broadcast at least one signal"

    message, groups = sent[-1]
    from bridge.models import Pod

    pod = await Pod.objects.select_related("backend").aget(id=ids["pod"]["id"])

    assert set(groups) == {
        channels.pod_group(pod.id),
        channels.org_group(pod.backend.organization_id),
    }
    assert message.create == pod.id or message.update == pod.id


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pod_subscription_refuses_another_organization(
    authenticated_context: HttpContext,
    other_org_context: HttpContext,
    flavour_id: str,
):
    """Subscribing to a foreign pod is refused before the stream is established."""
    from bridge import models
    from bridge.subscriptions.pod import pod as pod_subscription

    ids = await setup_pod(authenticated_context, flavour_id)

    stream = pod_subscription(_Info(context=other_org_context), ids["pod"]["id"])

    with pytest.raises(models.Pod.DoesNotExist):
        await stream.__anext__()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_pod_event_resolves_each_kind(authenticated_context: HttpContext, flavour_id: str):
    """A signal becomes the matching PodEvent; a vanished pod is skipped, not fatal."""
    from bridge.channel_signals import PodSignal
    from bridge.subscriptions.pod import _resolve

    ids = await setup_pod(authenticated_context, flavour_id)
    pod_id = int(ids["pod"]["id"])

    created = await _resolve(_Info(context=authenticated_context), PodSignal(create=pod_id))
    assert created.create is not None and created.update is None and created.delete is None

    updated = await _resolve(_Info(context=authenticated_context), PodSignal(update=pod_id))
    assert updated.update is not None and updated.create is None

    # A delete carries only the ID: the row is gone, so there is nothing to resolve.
    deleted = await _resolve(_Info(context=authenticated_context), PodSignal(delete=pod_id))
    assert deleted.delete == str(pod_id)
    assert deleted.create is None and deleted.update is None

    # A pod that disappeared between broadcast and lookup is skipped rather than
    # tearing down the subscriber's stream.
    assert await _resolve(_Info(context=authenticated_context), PodSignal(update=987654321)) is None


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_broadcast_waits_for_commit(authenticated_context: HttpContext, flavour_id: str):
    """Nothing is published until the surrounding transaction commits.

    ``post_save`` fires before commit, and no write path here was atomic, so a subscriber
    could be told about a pod that a rolled-back transaction never created.
    """
    from django.db import transaction

    from bridge import channels, models

    ids = await setup_pod(authenticated_context, flavour_id)

    sent: list[object] = []
    original = channels.pod_channel.broadcast
    channels.pod_channel.broadcast = lambda message, groups=None: sent.append(message)

    def touch_then_roll_back():
        try:
            with transaction.atomic():
                pod = models.Pod.objects.get(id=ids["pod"]["id"])
                pod.status = "RUNNING"
                pod.save()
                assert not sent, "broadcast fired before the transaction committed"
                raise RuntimeError("rollback")
        except RuntimeError:
            pass

    try:
        await sync_to_async(touch_then_roll_back)()
    finally:
        channels.pod_channel.broadcast = original

    assert not sent, "a rolled-back write must not announce itself"
