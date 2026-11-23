"""Where an Arkitekt repository keeps the files kabinet reads.

The folder used to be spelled two ways in the same file -- ``.arkitekt-next`` for the
manifest and ``.arkitekt_next`` for the deployments -- so a repo would have had to
contain both for kabinet to read both. It is ``.arkitekt`` now, and it is spelled here
once. The legacy names stay listed so that a repo still publishing them gets told to
rename rather than "this does not look like an Arkitekt repository".
"""

import re

#: Base of the GitHub raw file host. Module-level so tests can point the fetcher and its
#: diagnosis probes at a local server instead of the internet.
RAW_BASE = "https://raw.githubusercontent.com"

CONFIG_DIR = ".arkitekt"
DEPLOYMENTS_PATH = f"{CONFIG_DIR}/deployments.yaml"
MANIFEST_PATH = f"{CONFIG_DIR}/manifest.yaml"
#: The bloks a repository publishes on its own, apart from any app: a blok repository.
BLOKS_PATH = f"{CONFIG_DIR}/bloks.yaml"

#: Folders kabinet read before the rename, newest spelling first.
LEGACY_CONFIG_DIRS = (".arkitekt_next", ".arkitekt-next")

#: Files that exist in essentially every repository, used only to tell "the branch is
#: reachable but has no config folder" apart from "the repo or branch is not there".
ROOT_MARKER_PATHS = ("pyproject.toml", "README.md")


def raw_url(user: str, repo: str, branch: str, path: str) -> str:
    """URL of ``path`` inside a GitHub repository, served as a raw file."""
    return f"{RAW_BASE}/{user}/{repo}/{branch}/{path}"


def parse_github_identifier(identifier: str) -> tuple[str, str, str]:
    """``(owner, repo, branch)`` of a github.com URL (with or without ``/tree/<branch>``),
    ``owner/repo`` or ``owner/repo:branch``. The branch defaults to ``main``."""
    match = re.match(
        r"https:\/\/github\.com\/([^\/]+)\/([^\/]+)(?:\/tree\/([^\/]+))?", identifier
    )
    if match:
        user, repo, branch = match.groups()
        return user, repo, branch or "main"
    if "/" not in identifier:
        raise ValueError(
            f"'{identifier}' is not a GitHub identifier. Expected a github.com URL, 'user/repo', or 'user/repo:branch'."
        )
    user, repo_with_branch = identifier.split("/", 1)
    repo, _, branch = repo_with_branch.partition(":")
    if not user or not repo:
        raise ValueError(f"'{identifier}' names no owner or no repository.")
    return user, repo, branch or "main"
