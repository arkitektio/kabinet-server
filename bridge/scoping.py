"""Organization scoping helpers for single-object access, and for a guest, their collaborations.

List fields are tenant-scoped through ``build_prescoped_queryset`` on the
GraphQL types (see :mod:`bridge.types`); everything that fetches a single row
by ID (mutations, single-item queries, subscriptions) must go through
:func:`for_org`, :func:`get_for_org` or :func:`aget_for_org` instead of
``Model.objects`` so one organization cannot read or mutate another
organization's rows.

Both also hold a guest of the organization, at a root field, to what is in their collaborations
(``arkitekt_service.collaborations``); below a root field the collaboration gate does.
"""

from functools import cache

from arkitekt_service.collaborations.guests import object_scope
from django.core.exceptions import FieldDoesNotExist
from django.db import models as django_models
from kante.types import Info

# Models that have no organization anywhere in their non-nullable FK graph.
# Access to these is knowingly unscoped until they grow an organization (or a
# required FK to an organization-scoped model). Keep this list short and
# visible — it is the tenancy escape hatch. Currently every model is scoped.
UNSCOPED_MODELS: frozenset[str] = frozenset()

# `LogDump` reaches its organization through `pod__backend__organization` and `Flavour`
# through `release__app__organization`, so a depth of 3 was exactly saturated: one more
# level of indirection anywhere and the walk would return None, which `for_org` reports
# as a hard error and `build_prescoped_queryset` used to turn into `filter(**{None: ...})`.
# Kept generous so adding a model is not silently a tenancy decision.
_MAX_PATH_DEPTH = 5


def _find_org_path(model: type[django_models.Model], depth: int) -> str | None:
    try:
        field = model._meta.get_field("organization")
        if field.is_relation:
            return "organization"
    except FieldDoesNotExist:
        pass

    if depth == 0:
        return None

    # Only follow required FKs: a nullable path would silently hide rows
    # whose FK is NULL instead of scoping them.
    for field in model._meta.get_fields():
        if not isinstance(field, django_models.ForeignKey) or field.null:
            continue
        if field.related_model is model:
            continue
        sub_path = _find_org_path(field.related_model, depth - 1)
        if sub_path:
            return f"{field.name}__{sub_path}"

    return None


@cache
def organization_path(model: type[django_models.Model]) -> str | None:
    """Return the ORM lookup path from ``model`` to its organization, if any."""
    return _find_org_path(model, _MAX_PATH_DEPTH)


def for_org(model: type[django_models.Model], info: Info) -> django_models.QuerySet:
    """Return ``model``'s queryset limited to the request's organization (a guest: to their collaborations)."""
    path = organization_path(model)
    if path is None:
        if model.__name__ not in UNSCOPED_MODELS:
            raise LookupError(
                f"{model.__name__} has no path to an organization and is not "
                "registered in bridge.scoping.UNSCOPED_MODELS"
            )
        return object_scope(model.objects.all(), info=info)
    return object_scope(
        model.objects.filter(**{path: info.context.request.organization}), info=info
    )


def get_for_org(
    model: type[django_models.Model], info: Info, **kwargs: object
) -> django_models.Model:
    """``Model.objects.get`` limited to the request's organization."""
    return for_org(model, info).get(**kwargs)


async def aget_for_org(
    model: type[django_models.Model], info: Info, **kwargs: object
) -> django_models.Model:
    """Async ``Model.objects.aget`` limited to the request's organization."""
    return await for_org(model, info).aget(**kwargs)
