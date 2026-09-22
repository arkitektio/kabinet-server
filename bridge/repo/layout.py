"""Where an Arkitekt repository keeps the files kabinet reads.

The folder used to be spelled two ways in the same file -- ``.arkitekt-next`` for the
manifest and ``.arkitekt_next`` for the deployments -- so a repo would have had to
contain both for kabinet to read both. It is ``.arkitekt`` now, and it is spelled here
once. The legacy names stay listed so that a repo still publishing them gets told to
rename rather than "this does not look like an Arkitekt repository".
"""

#: Base of the GitHub raw file host. Module-level so tests can point the fetcher and its
#: diagnosis probes at a local server instead of the internet.
RAW_BASE = "https://raw.githubusercontent.com"

CONFIG_DIR = ".arkitekt"
DEPLOYMENTS_PATH = f"{CONFIG_DIR}/deployments.yaml"
MANIFEST_PATH = f"{CONFIG_DIR}/manifest.yaml"

#: Folders kabinet read before the rename, newest spelling first.
LEGACY_CONFIG_DIRS = (".arkitekt_next", ".arkitekt-next")

#: Files that exist in essentially every repository, used only to tell "the branch is
#: reachable but has no config folder" apart from "the repo or branch is not there".
ROOT_MARKER_PATHS = ("pyproject.toml", "README.md")


def raw_url(user: str, repo: str, branch: str, path: str) -> str:
    """URL of ``path`` inside a GitHub repository, served as a raw file."""
    return f"{RAW_BASE}/{user}/{repo}/{branch}/{path}"
