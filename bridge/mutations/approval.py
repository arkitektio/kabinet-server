from asgiref.sync import sync_to_async
from authentikate.strawberry.directives import has_org_role
from graphql import GraphQLError
from kante.types import Info

from bridge import approvals, inputs, models, types
from bridge.scoping import for_org


def _approve(info: Info, parsed: inputs.ApproveReleaseInputModel) -> models.ReleaseApproval:
    release = for_org(models.Release, info).select_related("app").get(id=parsed.release)
    if approvals.release_digest(release) != parsed.digest:
        # The approver reviewed a different release than the one stored now.
        raise GraphQLError("The release changed since you reviewed it; review it again.")
    backends = list(for_org(models.Backend, info).filter(id__in=parsed.backends)) if parsed.backends else []
    if parsed.backends and len(backends) != len(set(parsed.backends)):
        raise GraphQLError("Unknown backend.")
    return approvals.create_approval(
        release=release,
        approver=info.context.request.user,
        organization=info.context.request.organization,
        mandate_id=parsed.mandate,
        agent=parsed.agent,
        backends=backends,
    )


async def approve_release(info: Info, input: inputs.ApproveReleaseInput) -> types.ReleaseApproval:
    """Record a standing approval of a release, backed by a lok mandate you created.

    Anyone in the organization may approve: the deployed release will act as *them*.
    """
    return await sync_to_async(_approve)(info, input.to_pydantic())


def _revoke(info: Info, parsed: inputs.RevokeApprovalInputModel) -> models.ReleaseApproval:
    approval = for_org(models.ReleaseApproval, info).get(id=parsed.id)
    if approval.approver_id != info.context.request.user.id and not has_org_role(info, "admin"):
        raise GraphQLError("Only the approver or an organization admin may revoke this approval.")
    return approvals.revoke(approval)


async def revoke_approval(info: Info, input: inputs.RevokeApprovalInput) -> types.ReleaseApproval:
    """Withdraw an approval: no new deployments. Revoke the lok mandate too to stop running pods."""
    return await sync_to_async(_revoke)(info, input.to_pydantic())
