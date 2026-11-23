# Catalogs

A catalog is a curated list of repositories an organization reads: arkitekt.live's default
list, a community list, a lab's own. It is one static file at a URL. An organization browses
its catalogs' entries and imports the ones it wants. Nothing in a catalog is tracked, scanned or
installed until the organization imports it, and a release imported from it is still approved
(`approveRelease`) before anything of it is deployed. Being listed is how an app is found, not
a reason to trust it.

## Which catalogs an organization reads

Two kinds, both the organization's own rows:

- **The config's** (`ensure_catalogs`, CONFIG.md; `ensured` on the catalog). Unset, every
  organization reads arkitekt.live's list, `https://arkitekt.live/catalogs/default.json`: the
  apps the Arkitekt team publishes, kept in `public/catalogs/` of arkitektio/arkitektio.github.io,
  whose build checks every catalog there (`pnpm check:catalogs`). `ensure_catalogs: []` names
  none. An organization gets them when it lists its catalogs (`catalogs`): a named URL it lacks
  is added, one it added itself becomes the config's, and a config catalog no longer named is
  removed. It cannot remove one (`deleteCatalog` refuses); only the operator can, here.
- **Its own**: `createCatalog(input: {url})` reads the file and adds it, refusing a URL that is
  not a readable catalog; `deleteCatalog` removes it with its entries. What was imported from a
  removed catalog stays imported.

```yaml
ensure_catalogs:
  - https://arkitekt.live/catalogs/default.json
  - https://lab.example.org/arkitekt/catalog.yaml
catalog_ttl: 3600
```

No setup job is involved: a hub without internet sets up the same, and its catalogs record the
failed read.

## Reading

`catalogs` (and `catalog(id:)`) reads every catalog of the organization first that was last
tried more than `catalog_ttl` seconds ago; `refreshCatalog` reads one now. A read:

- sends the ETag of the last read (`If-None-Match`), so an unchanged file costs a 304;
- matches the entries by `key` (an entry keeps its ID across reads), creating, changing and
  deleting them row by row with the catalog locked, so each change is signalled to the
  organization (`@kabinet/catalogentry`) and an unchanged entry is not;
- leaves the entries of the last good read when the file cannot be read or is not a catalog,
  and records why in `Catalog.error`. The whole file is refused: one bad entry fails the read.

Only one request (or replica) reads a stale catalog; the others answer from the rows. Two
organizations reading the same URL each read it. `catalogEntries` answers from the rows only,
with filters `search`, `kind`, `tags` and `catalog`: a client lists `catalogs` first.

## The file

JSON or YAML, at most 2 MiB. Keys this version does not know are ignored.

```json
{
  "spec_version": 1,
  "name": "Arkitekt",
  "description": "The apps the Arkitekt team maintains",
  "entries": [
    {
      "key": "ome",
      "kind": "oci",
      "reference": "ghcr.io/arkitektio/ome",
      "channels": ["main"],
      "name": "OME",
      "description": "Read and convert OME files",
      "tags": ["io", "microscopy"],
      "logo": "https://arkitekt.live/logos/ome.png",
      "homepage": "https://github.com/arkitektio/ome",
      "maintainer": "arkitektio"
    },
    {
      "key": "renderer",
      "kind": "github",
      "reference": "jhnnsrs/renderer:main",
      "name": "Renderer",
      "description": "Panels and scenes for volumes"
    }
  ]
}
```

| Key | Required | Meaning |
| --- | --- | --- |
| `spec_version` | yes | `1`. |
| `name` | yes | The catalog's name. |
| `description` | no | What the catalog is. |
| `entries[].key` | yes | Unique in the file; the entry's identity across reads. Lowercase letters, digits, `.`, `_`, `-`. |
| `entries[].kind` | yes | `oci`: an OCI repository carrying an app's releases, imported as `importRepo` does. `github`: a GitHub repository with `.arkitekt/deployments.yaml` and/or `.arkitekt/bloks.yaml`, tracked as `createGithubRepo` does. |
| `entries[].reference` | yes | `oci`: `registry/repository`, no tag, no digest. `github`: `owner/repo`, `owner/repo:branch` or a github.com URL; the branch defaults to `main`. Stored the one way an import writes it. |
| `entries[].channels` | no | `oci` only: the channels an import follows besides the releases. |
| `entries[].name` | yes | Shown to whoever browses the catalog. |
| `entries[].description`, `tags`, `logo`, `homepage`, `maintainer` | no | Shown likewise; `logo` and `homepage` are http(s) URLs. |

## Importing

`importCatalogEntry(input: {id, channels})` imports the entry's repository into the
organization, exactly as `importRepo` (oci; `channels` defaults to the entry's) or
`createGithubRepo` (github) would. Importing again reads the repository again. An entry's
`ociRepo` / `githubRepo` is the repository the requesting organization imported from it, if any.
