from typing import AsyncGenerator

import strawberry
from kante.types import Info

from bridge import channels, models, types
from bridge.channels import org_group, pod_group
from bridge.scoping import aget_for_org


@strawberry.type(description="Something that happened to a pod: it was created, updated or deleted.")
class PodEvent:
    """A pod lifecycle event.

    Exactly one of the three fields is set. `create` and `update` carry the pod itself;
    `delete` carries only the ID, because by the time the event is delivered the row is
    gone and there is nothing left to resolve.
    """

    create: types.Pod | None = strawberry.field(default=None, description="The pod that was just created, if this event is a creation.")
    update: types.Pod | None = strawberry.field(default=None, description="The pod that just changed, if this event is an update.")
    delete: strawberry.ID | None = strawberry.field(default=None, description="The ID of the pod that was deleted, if this event is a deletion.")


async def _resolve(info: Info, message: channels.PodSignal) -> PodEvent | None:
    """Turn a broadcast signal into an event, or None if it should be skipped.

    A pod can be deleted between the broadcast and this lookup, and a subscriber should
    not have their stream torn down by a race. `DoesNotExist` is therefore a skip rather
    than an error -- the tenancy question was already settled by the group the message
    arrived on.
    """
    if message.delete is not None:
        return PodEvent(delete=strawberry.ID(str(message.delete)))

    pod_id = message.create if message.create is not None else message.update
    if pod_id is None:
        return None

    try:
        pod = await aget_for_org(models.Pod, info, id=pod_id)
    except models.Pod.DoesNotExist:
        return None

    return PodEvent(create=pod) if message.create is not None else PodEvent(update=pod)


async def pod(info: Info, pod_id: strawberry.ID) -> AsyncGenerator[PodEvent, None]:
    """Stream lifecycle events for one pod.

    Scoped up front: `aget_for_org` raises `DoesNotExist` for a pod in another
    organization, so a cross-tenant subscription is refused before it is established
    rather than filtered afterwards.
    """
    await aget_for_org(models.Pod, info, id=pod_id)

    async for message in channels.pod_channel.listen(info.context, groups=[pod_group(pod_id)]):
        event = await _resolve(info, message)
        if event is not None:
            yield event


async def pods(info: Info) -> AsyncGenerator[PodEvent, None]:
    """Stream lifecycle events for every pod in the caller's organization.

    Listens on a per-organization group. It used to listen on the literal group "all" and
    lean on `aget_for_org` raising per message to filter -- which meant another tenant's
    pod did not get skipped, it terminated the subscriber's stream. Tenancy is a property
    of the group now, so a foreign event never arrives in the first place.
    """
    organization = info.context.request.organization

    async for message in channels.pod_channel.listen(info.context, groups=[org_group(organization.id)]):
        event = await _resolve(info, message)
        if event is not None:
            yield event
