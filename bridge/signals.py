from django.db.models.signals import post_save
from django.dispatch import receiver
from bridge import models, gateways, messages
from typing import Type


@receiver(post_save, sender=models.Pod)
def my_handler(
    sender: Type[models.Pod],
    instance: models.Pod = None,
    created: bool = False,
    **kwargs
) -> None:
    """Sends a message to the pod gateway when a pod is updated"""
    gateways.pod_gateway.abroadcast(
        messages.PodUpdateMessageModel(
            id=instance.id,
            created=created,
            status=instance.status,
        )
    )
