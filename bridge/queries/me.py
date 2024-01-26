from bridge import types
from kante.types import Info
from typing import cast


def me(info: Info) -> types.User:
    """Return the currently logged in user.

    Parameters
    ----------
    info : Info
        The GraphQL resolver info.


    """
    return cast(types.User, info.context.request.user)
