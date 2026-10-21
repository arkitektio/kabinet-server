# Blok repositories

A GitHub repository kabinet tracks can publish bloks on their own, apart from any app: panels
(`HTML`) and scenes (`SCENE`) anyone in the organization can install. It lists them in
`.arkitekt/bloks.yaml` on the tracked branch. A repository may publish app images
(`.arkitekt/deployments.yaml`), bloks, or both; either file is enough to track it.

```yaml
spec_version: 1
bloks:
  - key: layer-picker                # unique in the repository: the blok's identity across scans
    name: Layer picker               # the name it is installed under
    description: Pick the visible layers
    context: HTML                    # HTML (a panel) or SCENE
    source: bloks/layer_picker.bsx   # its BSX, a path from the repository's root …
    # bsx: |                         # … or written inline: exactly one of the two
    #   <Panel>…</Panel>
    demo_state: {}                   # what it is drawn against when shown on its own
    dependencies: []                 # the agents it draws from (rekuest_core AgentDependencyInput)
    for_model: null                  # 'sha256:…' of a model it decorates (HTML only)
    for_node: null
```

- A key is lowercase letters, digits, `.`, `_` and `-`. Logos are not published this way: they
  belong to an app.
- `source` is read from `raw.githubusercontent.com` in the same scan, up to 512 KiB. A path
  outside the repository, or one that is not there, fails the scan with the blok's key named.
- A blok whose BSX does not parse is still written, with its `parseError`: one broken blok does
  not fail the scan.

## What a scan does

`createGithubRepo`, `scanRepo` and `rescanRepos` read both files (`bridge/repo/fetch.py`,
`aget_repo_contents`) and write a `RepoBlok` per blok (`bridge/repo/db.py`, `apply_bloks`):
upserted by `(repo, key)`, rendered with the parser flavour bloks use (`bridge/repo/bloks.py`),
and deleted when the file no longer lists it. A repository without a bloks file has none.

## Installing

Nothing of a `RepoBlok` runs in kabinet. A client installs one by sending its `installInput` to
rekuest's `createBlok` as it is: a `CreateBlokInput` with the BSX, and with

- `origin`: `github:<owner>/<repo>:<branch>#<key>`, the same whenever the repository is tracked
  again. rekuest finds an installed blok again by it, so installing again updates the same blok
  (its materializations stay), and never replaces a blok made by hand under the same name.
- `originHash`: the blok's `installHash` when it was installed, a hash of everything installing
  writes (name, description, BSX, demo state, dependencies, target). When the `RepoBlok`'s
  `installHash` differs from the installed copy's `originHash`, the repository has an update.
  `hash` covers only what the blok draws and keys its preview.

`restore_bloks --all` renders every `RepoBlok` again after the parser changed.
