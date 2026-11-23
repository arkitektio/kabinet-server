# Catalogs

A catalog is a curated list of repositories a hub reads: arkitekt.live's default list, a
community list, a lab's own. It is one static file at a URL. Kabinet lists its entries to every
organization of the hub, and an organization imports the ones it wants. Nothing in a catalog is
tracked, scanned or installed until an organization imports it, and a release imported from it
is still approved (`approveRelease`) before anything of it is deployed. Being listed is how an
app is found, not a reason to trust it.

## Which catalogs a hub reads

The config names them (`ensure_catalogs`, CONFIG.md). Unset, a hub reads arkitekt.live's list,
`https://arkitekt.live/catalogs/default.json`: the apps the Arkitekt team publishes, kept in
`public/catalogs/` of arkitektio/arkitektio.github.io, whose build checks every catalog there
(`pnpm check:catalogs`). `ensure_catalogs: []` reads none.

```yaml
ensure_catalogs:
  - https://arkitekt.live/catalogs/default.json
  - https://lab.example.org/arkitekt/catalog.yaml
catalog_ttl: 3600
```

The `ensurecatalogs` setup job makes the hub's catalogs exactly these: a URL with no row gets
one, and a row whose URL is no longer named is deleted with its entries (what organizations
imported from it stays theirs). It touches the database only, so a hub without internet sets up
the same. The catalogs are the hub's, not an organization's.

## Reading

`catalogs` (and `catalog(id:)`) reads every catalog first that was last tried more than
`catalog_ttl` seconds ago; `refreshCatalog` reads one now. A read:

- sends the ETag of the last read (`If-None-Match`), so an unchanged file costs a 304;
- upserts the entries by `key` (an entry keeps its ID across reads) and deletes the ones the
  file no longer lists, in one transaction;
- leaves the entries of the last good read when the file cannot be read or is not a catalog,
  and records why in `Catalog.error`. The whole file is refused: one bad entry fails the read.

Only one request (or replica) reads a stale catalog; the others answer from the rows.
`catalogEntries` answers from the rows only, with filters `search`, `kind`, `tags` and
`catalog`.

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

`importCatalogEntry(input: {id, channels})` imports the entry's repository into the requesting
organization, exactly as `importRepo` (oci; `channels` defaults to the entry's) or
`createGithubRepo` (github) would. Importing again reads the repository again. An entry's
`ociRepo` / `githubRepo` is the repository the requesting organization imported from it, if any.
