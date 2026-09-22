import datetime

import strawberry
from bridge import managers
from bridge import inputs
from bridge import models
from bridge import scoping
import strawberry_django
from kante.types import Info
from django.db.models import Q, QuerySet
from rekuest_core import enums as rkenums

from embeddings import search
from embeddings.search import hybrid_search


@strawberry_django.order_type(models.Definition, description="Order for action definitions.")
class DefinitionOrder:
    """Order for action definitions."""

    defined_at: strawberry.auto
    name: strawberry.auto
    kind: strawberry.auto


@strawberry_django.filter_type(models.GithubRepo, description="Filter for tracked GitHub repositories.")
class GithubRepoFilter:
    """Filter for tracked GitHub repositories."""

    @strawberry_django.filter_field(description="Keep only repositories whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Search by name: a case-insensitive substring, or semantic similarity of the query to the repository's name. Substring matches rank first, then by similarity; an explicit `ordering` replaces that ranking.")
    def search(self, info: Info, queryset: QuerySet, value: str, prefix: str) -> tuple[QuerySet, Q]:
        return hybrid_search(queryset, prefix, value, Q(**{f"{prefix}name__icontains": value}))

    @strawberry_django.filter_field(description="Case-insensitive match on the GitHub repository name.")
    def repo(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}repo__icontains": value})

    @strawberry_django.filter_field(description="Case-insensitive match on the GitHub owner.")
    def user(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}user__icontains": value})

    @strawberry_django.filter_field(description="Case-insensitive match on the branch name.")
    def branch(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}branch__icontains": value})


@strawberry_django.filter_type(models.Definition, description="Filter for action definitions.")
class DefinitionFilter:
    """Filter for action definitions."""

    @strawberry_django.filter_field(description="Keep only definitions whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Search by text: a case-insensitive substring of the name or the description, or semantic similarity of the query to both. Substring matches rank first, then by similarity; an explicit `ordering` replaces that ranking.")
    def search(self, info: Info, queryset: QuerySet, value: str, prefix: str) -> tuple[QuerySet, Q]:
        """Annotate the distance and OR the semantic predicate onto the substring one.

        The substring leg covers the description as well as the name. A definition is found
        by what it says it does far more often than by what it is called, and the semantic
        leg -- which embeds both fields -- already behaved that way, so a query whose exact
        words appeared in a description used to be answered *only* by the fuzzy half.
        """
        lexical = Q(**{f"{prefix}name__icontains": value}) | Q(**{f"{prefix}description__icontains": value})
        return hybrid_search(queryset, prefix, value, lexical)

    @strawberry_django.filter_field(description="Order by closeness in meaning to the given definition, nearest first, keeping only definitions that can be compared to it (the same grouping as `Definition.similar`). Nothing is cut off at a fixed neighbourhood size, so this composes with the other filters and with pagination; an explicit `ordering` replaces the ranking. Empty when the given definition cannot be found in this organization, or has not been indexed for similarity yet. Combined with `search` it ranks that search\'s matches by closeness instead -- the two rankings do not stack.")
    def similar_to(self, info: Info, queryset: QuerySet, value: strawberry.ID, prefix: str) -> tuple[QuerySet, Q]:
        """Restrict to the neighbourhood of one definition, found through the same helper the field uses."""
        if prefix:
            # Nested through another type, the annotation and the slice cannot be expressed
            # as a predicate on this queryset; fall back to no restriction rather than
            # silently scoping the wrong rows.
            return queryset, Q()

        # Through `for_org`, not `Definition.objects`: reading the anchor's vector out of
        # another organization's row would make this filter an oracle for what that row
        # means, even though the rows it returns stay correctly scoped.
        anchor = scoping.for_org(models.Definition, info).filter(pk=value).values_list("embedding", flat=True).first()
        return search.neighbourhood(queryset, anchor, exclude_pk=value)

    @strawberry_django.filter_field(description="Keep only definitions of these kinds (function, generator, ...).")
    def kinds(self, value: list[rkenums.ActionKind], prefix: str) -> Q:
        return Q(**{f"{prefix}kind__in": [kind.value for kind in value]})

    @strawberry_django.filter_field(description="Keep only definitions with one of these data scopes.")
    def scopes(self, value: list[rkenums.ActionScope], prefix: str) -> Q:
        return Q(**{f"{prefix}scope__in": [scope.value for scope in value]})

    @strawberry_django.filter_field(description="Keep only pure definitions (their result can be cached), or only impure ones.")
    def pure(self, value: bool, prefix: str) -> Q:
        return Q(**{f"{prefix}pure": value})

    @strawberry_django.filter_field(description="Keep only idempotent definitions, or only non-idempotent ones.")
    def idempotent(self, value: bool, prefix: str) -> Q:
        return Q(**{f"{prefix}idempotent": value})

    @strawberry_django.filter_field(description="Keep only definitions in these collections.")
    def collections(self, queryset: QuerySet, value: list[strawberry.ID], prefix: str) -> tuple[QuerySet, Q]:
        # A join over a to-many relation repeats a row once per match, so a definition in
        # two of the listed collections would be returned twice -- and counted twice by
        # pagination.
        return queryset.distinct(), Q(**{f"{prefix}collections__id__in": value})

    @strawberry_django.filter_field(description="Keep only definitions implementing these protocols.")
    def protocols(self, queryset: QuerySet, value: list[strawberry.ID], prefix: str) -> tuple[QuerySet, Q]:
        # A join over a to-many relation repeats a row once per match, so a definition in
        # two of the listed collections would be returned twice -- and counted twice by
        # pagination.
        return queryset.distinct(), Q(**{f"{prefix}protocols__id__in": value})

    @strawberry_django.filter_field(description="Keep only definitions provided by these flavours.")
    def flavours(self, queryset: QuerySet, value: list[strawberry.ID], prefix: str) -> tuple[QuerySet, Q]:
        # A join over a to-many relation repeats a row once per match, so a definition in
        # two of the listed collections would be returned twice -- and counted twice by
        # pagination.
        return queryset.distinct(), Q(**{f"{prefix}flavours__id__in": value})

    @strawberry_django.filter_field(description="Keep only definitions provided by these apps.")
    def apps(self, queryset: QuerySet, value: list[strawberry.ID], prefix: str) -> tuple[QuerySet, Q]:
        # A join over a to-many relation repeats a row once per match, so a definition in
        # two of the listed collections would be returned twice -- and counted twice by
        # pagination.
        return queryset.distinct(), Q(**{f"{prefix}flavours__release__app__id__in": value})

    @strawberry_django.filter_field(description="Keep only definitions that declare all of these interfaces.")
    def interfaces(self, value: list[str], prefix: str) -> Q:
        # `interfaces` is a JSONB list, so `__contains` is containment of a list, not
        # membership of a scalar: one term per interface, ANDed.
        query = Q()
        for interface in value:
            query &= Q(**{f"{prefix}interfaces__contains": [interface]})
        return query

    @strawberry_django.filter_field(description="Keep only definitions that are tests for these definitions.")
    def is_test_for(self, queryset: QuerySet, value: list[strawberry.ID], prefix: str) -> tuple[QuerySet, Q]:
        # A join over a to-many relation repeats a row once per match, so a definition in
        # two of the listed collections would be returned twice -- and counted twice by
        # pagination.
        return queryset.distinct(), Q(**{f"{prefix}is_test_for__id__in": value})

    @strawberry_django.filter_field(description="Keep only definitions that have at least one test, or only those that have none.")
    def has_tests(self, queryset: QuerySet, value: bool, prefix: str) -> tuple[QuerySet, Q]:
        return queryset.distinct(), Q(**{f"{prefix}tests__isnull": not value})

    @strawberry_django.filter_field(description="Keep only definitions first defined at or after this moment.")
    def defined_after(self, value: datetime.datetime, prefix: str) -> Q:
        return Q(**{f"{prefix}defined_at__gte": value})

    @strawberry_django.filter_field(description="Keep only definitions first defined at or before this moment.")
    def defined_before(self, value: datetime.datetime, prefix: str) -> Q:
        return Q(**{f"{prefix}defined_at__lte": value})

    @strawberry_django.filter_field(
        description="Keep only definitions whose ports satisfy all of the given demands.",
    )
    def demands(self, value: list[inputs.PortDemandInput], prefix: str) -> Q:
        filtered_ids = None

        for ports_demand in value:
            new_ids = managers.get_action_ids_by_demands(
                ports_demand.matches,
                type=ports_demand.kind.value,
                force_length=ports_demand.force_length,
                force_non_nullable_length=ports_demand.force_non_nullable_length,
                force_structure_length=ports_demand.force_structure_length,
                model="bridge_definition",
            )

            if filtered_ids is None:
                filtered_ids = set(new_ids)
            else:
                filtered_ids = filtered_ids.intersection(new_ids)

        if filtered_ids is None:
            return Q()

        return Q(**{f"{prefix}id__in": filtered_ids})


@strawberry_django.order_type(models.Flavour)
class FlavourOrder:
    """Order for Flavours"""

    @strawberry_django.order_field
    def released_at(
        self,
        info: Info,
        queryset: QuerySet,
        value: strawberry_django.Ordering,  # `auto` can be used instead
        prefix: str,
    ) -> tuple[QuerySet, list[str]] | list[str]:
        ordering = value.resolve(f"{prefix}release__released_at")
        return queryset, [ordering]


@strawberry_django.filter_type(models.Flavour, description="Filter for flavours.")
class FlavourFilter:
    """Filter for flavours."""

    @strawberry_django.filter_field(description="Keep only flavours whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Search by name: a case-insensitive substring, or semantic similarity of the query to the flavour's name and the app it was built from. Substring matches rank first, then by similarity; an explicit `ordering` replaces that ranking.")
    def search(self, info: Info, queryset: QuerySet, value: str, prefix: str) -> tuple[QuerySet, Q]:
        return hybrid_search(queryset, prefix, value, Q(**{f"{prefix}name__icontains": value}))

    @strawberry_django.filter_field(description="Keep only flavours that provide one of the given definitions.")
    def has_definitions(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}definitions__in": value})


@strawberry_django.filter_type(models.Resource, description="Filter for resources.")
class ResourceFilter:
    @strawberry_django.filter_field(description="Keep only resources whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the resource name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Backend, description="Filter for backends.")
class BackendFilter:
    @strawberry_django.filter_field(description="Keep only backends whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the backend name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Pod, description="Filter for pods.")
class PodFilter:
    @strawberry_django.filter_field(description="Keep only pods whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Match pods by the name of their backend.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}backend__name": value})

    @strawberry_django.filter_field(description="Keep only pods running on the given backend.")
    def backend(self, value: strawberry.ID, prefix: str) -> Q:
        return Q(**{f"{prefix}backend__id": value})


@strawberry_django.filter_type(models.Deployment, description="Filter for deployments.")
class DeploymentFilter:
    @strawberry_django.filter_field(description="Keep only deployments whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the deployment name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Release, description="Filter for app releases.")
class ReleaseFilter:
    @strawberry_django.filter_field(description="Keep only releases whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the release version.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}version__icontains": value})

    @strawberry_django.filter_field(description="Keep only the releases of this app.")
    def app(self, value: strawberry.ID, prefix: str) -> Q:
        # A release belongs to exactly one app, so this is a to-one join: no duplicate
        # rows and no `distinct()` needed, unlike the many-to-many facets on definitions.
        return Q(**{f"{prefix}app__id": value})

    @strawberry_django.filter_field(description="Keep only the releases of these apps.")
    def apps(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}app__id__in": value})

    @strawberry_django.filter_field(description="Keep only releases whose app identifier contains this text, case-insensitively.")
    def identifier(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}app__identifier__icontains": value})


@strawberry_django.filter_type(models.App, description="Filter for apps.")
class AppFilter:
    @strawberry_django.filter_field(description="Keep only apps whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Search by identifier: a case-insensitive substring, or semantic similarity of the query to it. Substring matches rank first, then by similarity; an explicit `ordering` replaces that ranking.")
    def search(self, info: Info, queryset: QuerySet, value: str, prefix: str) -> tuple[QuerySet, Q]:
        return hybrid_search(queryset, prefix, value, Q(**{f"{prefix}identifier__icontains": value}))


@strawberry_django.filter_type(models.DockerImage, description="Filter for Docker images.")
class DockerImageFilter:
    @strawberry_django.filter_field(description="Keep only images whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the image reference.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}image_string__icontains": value})


@strawberry_django.filter_type(models.Collection, description="Filter for collections.")
class CollectionFilter:
    @strawberry_django.filter_field(description="Keep only collections whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the collection name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.Protocol, description="Filter for protocols.")
class ProtocolFilter:
    @strawberry_django.filter_field(description="Keep only protocols whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the protocol name.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}name__icontains": value})


@strawberry_django.filter_type(models.LogDump, description="Filter for log dumps.")
class LogDumpFilter:
    @strawberry_django.filter_field(description="Keep only log dumps whose ID is in this list.")
    def ids(self, value: list[strawberry.ID], prefix: str) -> Q:
        return Q(**{f"{prefix}id__in": value})

    @strawberry_django.filter_field(description="Case-insensitive search on the captured log text.")
    def search(self, value: str, prefix: str) -> Q:
        return Q(**{f"{prefix}logs__icontains": value})


# ---------------------------------------------------------------------------
# Orders — one per model so every list query can be sorted.
# ---------------------------------------------------------------------------


@strawberry_django.order_type(models.GithubRepo)
class GithubRepoOrder:
    id: strawberry.auto
    name: strawberry.auto
    added_at: strawberry.auto
    updated_at: strawberry.auto


@strawberry_django.order_type(models.App)
class AppOrder:
    id: strawberry.auto
    identifier: strawberry.auto


@strawberry_django.order_type(models.Release)
class ReleaseOrder:
    id: strawberry.auto
    version: strawberry.auto
    released_at: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.DockerImage)
class DockerImageOrder:
    id: strawberry.auto
    image_string: strawberry.auto
    build_at: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Collection)
class CollectionOrder:
    id: strawberry.auto
    name: strawberry.auto
    defined_at: strawberry.auto


@strawberry_django.order_type(models.Protocol)
class ProtocolOrder:
    id: strawberry.auto
    name: strawberry.auto


@strawberry_django.order_type(models.LogDump)
class LogDumpOrder:
    id: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Backend)
class BackendOrder:
    id: strawberry.auto
    name: strawberry.auto
    last_heartbeat: strawberry.auto


@strawberry_django.order_type(models.Resource)
class ResourceOrder:
    id: strawberry.auto
    name: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Pod)
class PodOrder:
    id: strawberry.auto
    status: strawberry.auto
    created_at: strawberry.auto


@strawberry_django.order_type(models.Deployment)
class DeploymentOrder:
    id: strawberry.auto
    local_id: strawberry.auto
    created_at: strawberry.auto
