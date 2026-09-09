from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from bridge import models, channel_signals, channels
from typing import Type
from django.conf import settings
from authentikate.models import Organization
import re


def _broadcast_pod(signal: channel_signals.PodSignal, organization_id: object, pod_id: object) -> None:
    """Publish a pod signal to the pod's own group and its organization's group.

    Deferred to commit. These fire from ``post_save``/``post_delete``, which run *before*
    the surrounding transaction commits -- so a broadcast could announce a pod that a
    rolled-back transaction never created, and a subscriber had no way to find out.
    """

    def send() -> None:
        channels.pod_channel.broadcast(
            signal,
            groups=[channels.pod_group(pod_id), channels.org_group(organization_id)],
        )

    transaction.on_commit(send)


@receiver(post_save, sender=models.Pod)
def publish_pod_change(sender: Type[models.Pod], instance: models.Pod = None, created: bool = False, **kwargs) -> None:
    """Announce a pod creation or update to its subscribers."""
    signal = channel_signals.PodSignal(create=instance.id) if created else channel_signals.PodSignal(update=instance.id)
    _broadcast_pod(signal, instance.backend.organization_id, instance.id)


@receiver(post_delete, sender=models.Pod)
def publish_pod_del(sender: Type[models.Pod], instance: models.Pod = None, **kwargs) -> None:
    """Announce a pod deletion to its subscribers."""
    _broadcast_pod(
        channel_signals.PodSignal(delete=instance.id),
        instance.backend.organization_id,
        instance.id,
    )


def _iter_default_repo_identifiers() -> list[str]:
    identifiers: list[str] = []

    ensured_repos = getattr(settings, "ENSURED_REPOS", [])
    if isinstance(ensured_repos, list):
        identifiers.extend([repo for repo in ensured_repos if isinstance(repo, str) and repo])

    default_repos = getattr(settings, "DEFAULT_REPOS", [])
    if isinstance(default_repos, list):
        identifiers.extend([repo for repo in default_repos if isinstance(repo, str) and repo])
    elif isinstance(default_repos, dict):
        identifiers.extend([repo for repo in default_repos.values() if isinstance(repo, str) and repo])

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(identifiers))


def _parse_repo_identifier(identifier: str) -> tuple[str, str, str]:
    url_pattern = r"https:\/\/github\.com\/([^\/]+)\/([^\/]+)(?:\/tree\/([^\/]+))?"
    match = re.match(url_pattern, identifier)

    if match:
        user, repo, branch = match.groups()
        return user, repo, branch or "main"

    if "/" not in identifier:
        raise ValueError(f"Invalid GitHub identifier '{identifier}'")

    user, repo_with_branch = identifier.split("/", 1)
    if ":" in repo_with_branch:
        repo, branch = repo_with_branch.split(":", 1)
    else:
        repo, branch = repo_with_branch, "main"

    return user, repo, branch


@receiver(post_save, sender=Organization)
def ensure_default_repos_for_organization(
    sender: Type[Organization],
    instance: Organization | None = None,
    created: bool = False,
    **kwargs,
) -> None:
    if not created or instance is None:
        return

    for identifier in _iter_default_repo_identifiers():
        try:
            user, repo, branch = _parse_repo_identifier(identifier)
            models.GithubRepo.objects.get_or_create(
                user=user,
                repo=repo,
                branch=branch,
                organization=instance,
                defaults={"name": f"{user}/{repo}:{branch}"},
            )
        except Exception:
            # Keep organization creation resilient even when a repo identifier is malformed.
            continue
