from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from bridge import channel_signals, channels, models


def _broadcast_pod(
    signal: channel_signals.PodSignal, organization_id: object, pod_id: object
) -> None:
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
def publish_pod_change(
    sender: type[models.Pod],
    instance: models.Pod,
    created: bool = False,
    **kwargs: object,
) -> None:
    """Announce a pod creation or update to its subscribers."""
    signal = (
        channel_signals.PodSignal(create=instance.id)
        if created
        else channel_signals.PodSignal(update=instance.id)
    )
    _broadcast_pod(signal, instance.backend.organization_id, instance.id)


@receiver(post_save, sender=models.LogDump)
def publish_log_dump(
    sender: type[models.LogDump],
    instance: models.LogDump,
    created: bool = False,
    **kwargs: object,
) -> None:
    """A new log dump changes its pod's `latestLogDump`: announce it as an update of the pod.

    Without it a client waiting for the logs it asked for could only poll the pod.
    """
    if not created:
        return
    pod = (
        models.Pod.objects.select_related("backend")
        .only("id", "backend__organization_id")
        .get(id=instance.pod_id)
    )
    _broadcast_pod(
        channel_signals.PodSignal(update=pod.id), pod.backend.organization_id, pod.id
    )


@receiver(post_delete, sender=models.Pod)
def publish_pod_del(
    sender: type[models.Pod], instance: models.Pod, **kwargs: object
) -> None:
    """Announce a pod deletion to its subscribers."""
    _broadcast_pod(
        channel_signals.PodSignal(delete=instance.id),
        instance.backend.organization_id,
        instance.id,
    )
