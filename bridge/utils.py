from kante.types import Info
from bridge import models, types


async def aget_backend_for_info(info: Info) -> models.Backend:
    """Get the backend for the given info object.

    Clients are one-to-one with backends, so the backend is uniquely resolved
    from the authenticated (user, client, organization) on the request context.
    """

    backend, _ = await models.Backend.objects.aget_or_create(
        user=info.context.request.user,
        client=info.context.request.client,
        organization=info.context.request.organization,
    )

    return backend


def get_backend_for_info(info: Info) -> models.Backend:
    """Get the backend for the given info object.

    Clients are one-to-one with backends, so the backend is uniquely resolved
    from the authenticated (user, client, organization) on the request context.
    """

    backend, _ = models.Backend.objects.get_or_create(
        user=info.context.request.user,
        client=info.context.request.client,
        organization=info.context.request.organization,
    )

    return backend
