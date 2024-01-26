from kante.gateway import build_gateway
from bridge.messages import PodUpdateMessageModel

pod_gateway = build_gateway("pod_gateway", PodUpdateMessageModel)
