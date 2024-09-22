from bridge import types, models
import strawberry


def pod(id: strawberry.ID) -> types.Pod:
    """Return a dask cluster by id"""
    return models.Pod.objects.get(id=id)



def pod_for_agent(client_id: strawberry.ID, instance_id: strawberry.ID) -> types.Pod | None:
    """Return a pod for a given agent"""

    try:
        return models.Pod.objects.get(client_id=client_id) 
    except models.Pod.DoesNotExist:
        return None


