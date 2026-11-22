from collections import Counter

import strawberry
from kante.types import Info
from strawberry_django.filters import apply as apply_filters

from bridge import enums, models, types
from bridge.filters import AppFilter
from bridge.scoping import get_for_org


def app(info: Info, id: strawberry.ID) -> types.App:
    """Return an app by id, scoped to the request's organization."""
    return get_for_org(models.App, info, id=id)


def app_store_totals(
    info: Info, filters: AppFilter | None = None
) -> types.AppStoreTotals:
    """Counts over every app the filter keeps (as `apps` takes it), for a store's totals and service chips."""
    apps = types.App.get_queryset(models.App.objects.all(), info)
    if filters is not None:
        apps = apply_filters(filters, apps, info)
    ids = apps.order_by().values("pk")
    newest = models.Flavour.objects.filter(
        release__app__in=ids, release__in=types.newest_releases()
    )
    required: Counter[str] = Counter()
    services_by_app: dict[int, set[str]] = {}
    for app_id, requirements in models.Flavour.objects.filter(
        release__app__in=ids
    ).values_list("release__app_id", "requirements"):
        for requirement in requirements if isinstance(requirements, list) else []:
            service = (
                requirement.get("service") if isinstance(requirement, dict) else None
            )
            if service:
                services_by_app.setdefault(app_id, set()).add(service)
    for services in services_by_app.values():
        required.update(services)
    return types.AppStoreTotals(
        apps=apps.count(),
        actions=models.Definition.objects.filter(flavours__in=newest)
        .distinct()
        .count(),
        flavours=newest.count(),
        running=models.Deployment.objects.filter(
            flavour__release__app__in=ids, status=enums.PodStatus.RUNNING.value
        ).count(),
        services=[
            types.ServiceCount(service=service, apps=count)
            for service, count in sorted(
                required.items(), key=lambda item: (-item[1], item[0])
            )
        ],
    )
