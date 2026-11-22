from typing import cast

from kante.types import Info

from bridge import types


def me(info: Info) -> types.User:
    """Return the currently logged in user.

    Parameters
    ----------
    info : Info
        The GraphQL resolver info.


    """
    return cast(types.User, info.context.request.user)
