# kabinet-server

The app catalog of an [Arkitekt](https://arkitekt.live) hub: which containerized apps a hub
can install, in which versions and variants, and what is deployed and running where. Kabinet
keeps the record and serves it. It does not start containers: a deployer app registers
itself as a backend, places the pods and reports them back. It is registered as
`live.arkitekt.kabinet` and has a python client,
[`kabinet`](https://github.com/arkitektio/kabinet).

## Concepts

| Concept | What it is |
| --- | --- |
| Repo | A source of apps and their versioned releases, e.g. a GitHub repository. Scanning a repo finds and updates its apps. |
| App | A piece of software that implements some functionality. Think "Napari", "Fiji", "Stardist". |
| Release | One version of an app, numbered by [Semantic Versioning](https://semver.org/). Think "Stardist 0.1.0". |
| Flavour | One variant of a release: the same functionality, built differently. Think "Stardist 0.1.0 with CUDA" and "Stardist 0.1.0 on the CPU". A flavour has a Docker image. |
| Definition | An action a flavour implements, as rekuest will see it once the flavour runs. |
| Selector | A hardware or capability requirement a flavour has of a backend (CUDA, RAM, labels). Kabinet stores and serves selectors; the deployer evaluates them. See [docs/selectors.md](docs/selectors.md). |
| Backend | A deployer app that can run containers, and the Resources (machines) it declares. |
| Release approval | A user's standing approval to run one release, backed by a lok mandate and pinned to the release's digest. A release re-published under the same version makes the approval stale. |
| Deployment | The intent to run a flavour on a backend, with the approval it was made under. |
| Pod | A running instance of a deployment, kept up to date by its backend. A pod always belongs to a deployment. |

Everything belongs to an organization, and every read and write is scoped to the caller's.

## API

GraphQL is served at `/graphql` (HTTP and WebSocket), with the SDL at `/schema`.

| Operations | What they do |
| --- | --- |
| `createGithubRepo`, `scanRepo`, `rescanRepos` | Add a repo and read its apps, releases and flavours. |
| `approveRelease`, `revokeApproval` | Grant and withdraw the approval a deployment needs. |
| `declareBackend`, `declareResource`, `deleteBackend` | What a deployer says about itself. |
| `createDeployment`, `updateDeployment` | Record the intent to run a flavour, and its progress. |
| `createPod`, `updatePod`, `deletePod`, `dumpLogs` | What a backend reports about its containers. |
| `pod`, `pods` (subscriptions) | Live pod changes. |

## The schema is a contract

[`schema.graphql`](schema.graphql) is the rendered SDL, committed to this repo.
`tests/test_print_schema.py` fails when it and the live schema disagree, so every schema
change arrives as a reviewable diff of that one file rather than only as a behaviour
change. Regenerate it with:

```sh
python manage.py printschema
```

One copy lives downstream and it is not generated from this repo, so a schema change is
not finished until it is refreshed:

- `packages/kabinet` — the generated Python client. Its documents under `graphql/` are
  what actually pins the fields this service may not remove.

There used to be a second, at `deployments/next/configs/schemas/kabinet_v1.graphql`,
bind-mounted into the rekuest container. It drifted for roughly ten months (it still had
`order:` where the server had long since renamed the argument to `ordering:`, and a
`podForAgent(instanceId:)` that no longer exists) because nothing regenerated it and
nothing compared it — and nothing read it either, so it has been deleted along with the
mount rather than kept in step.

## Hub integration

Declared in [`kabinet_server/contract.py`](kabinet_server/contract.py):

- **Scopes**: `kabinet_add_repo`, `kabinet_deploy`, `kabinet_read`, `read`, `write`.
- **Roles**: `admin`, `deployer`, `user`, `viewer`.
- **Needs**: rekuest 6 or newer, an instance key, `media` storage, tokens issued by lok.

Kabinet is known to the hub's rekuest in two separate ways:

- as a **service** (`_rekuest/service`): it hosts structures such as `@kabinet/app`,
  `@kabinet/release`, `@kabinet/flavour`, `@kabinet/deployment` and `@kabinet/pod`
  ([`kabinet_server/service.py`](kabinet_server/service.py));
- as a **hook agent** (`_rekuest/hook`): the actions it offers are in
  [`kabinet_server/hook_agent.py`](kabinet_server/hook_agent.py).

Actions are only offered. Nothing in this service loops or schedules; whether and when one
runs is the organization's own automation in rekuest.

## Running

The image is `jhnnsrs/kabinet`. It has no default command, and starting it takes two steps:

```sh
arkitekt-service run migrate   # wait for the database, migrate, ensure the configured repos
arkitekt-service serve                          # serve on :80 (daphne), and nothing else
```

`arkitekt-service debug` does both in one go with Django's autoreloading server, for development.

It needs Postgres with pgvector ([`jhnnsrs/daten`](https://github.com/arkitektio/daten-server)),
Redis and an S3 store (RustFS), and it reaches GitHub to scan repos.

## Configuration

The service reads `config.yaml`, or the file named by `ARKITEKT_CONFIG_FILE`; any value can
be overridden by an environment variable (`POSTGRES__HOST`). `python manage.py
validate_settings` prints the configuration as the service reads it, with secrets redacted.

See [CONFIG.md](CONFIG.md) for every value.

## Development

```sh
uv sync
uv run pytest
```

The suite runs against a real stack, brought up by [dokker](https://github.com/jhnnsrs/dokker)
from `tests/integration/docker-compose.yaml`: Postgres (`jhnnsrs/daten:next`, override with
`DATEN_IMAGE`), RustFS with its buckets created by `jhnnsrs/init:next`, and Redis, on ports
Docker picks. It needs a running Docker daemon.

## Releases

Releases are tags: a push to `main` cuts a stable version, a push to `next` a release
candidate. Each one publishes `jhnnsrs/kabinet` under its version (`X.Y.Z`, `X.Y`, `X`), plus
`latest` from `main` and `next` from `next`. The `version` in `pyproject.toml` is a
placeholder. Release notes are on
[GitHub Releases](https://github.com/arkitektio/kabinet-server/releases); `CHANGELOG.md` is
frozen.
