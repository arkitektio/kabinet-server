# Kabinet-Server

## Develompent

Kabinet is a GraphQL API that allows you to retrieve and save containers
Arkitekt App). It is designed to be
used with Arkitekt Apps that are running in these containers, but can be used for any containerized application 

This is a highly developmental service, that aims to replace Port in the Arkitekt Next Deployment. It is not yet ready for production.

## The schema is a contract

[`schema.graphql`](schema.graphql) is the rendered SDL, committed to this repo.
`tests/test_print_schema.py` fails when it and the live schema disagree, so every schema
change arrives as a reviewable diff of that one file rather than only as a behaviour
change. Regenerate it with:

```bash
python manage.py printschema
```

Two copies live downstream and neither is generated from this repo, so a schema change is
not finished until both are refreshed:

- `packages/kabinet` — the generated Python client. Its documents under `graphql/` are
  what actually pins the fields this service may not remove.
- `deployments/next/configs/schemas/kabinet_v1.graphql` — mounted into the rekuest
  container. This drifted for roughly ten months (it still had `order:` where the server
  had long since renamed the argument to `ordering:`, and a `podForAgent(instanceId:)`
  that no longer exists) because nothing regenerated it and nothing compared it.

## Usage

Most likely you will use a client library to interact with Kabinet, but you can also use the GraphQL API directly.
THe API is build along the following concepts:

Repo: Repos are a collection of Versioned Releases of Apps that may exist in multiple versions. Repos provide ways
of finding and maintaining (updating) Apps.

App: An App is Piece of Software that implements a certain functionality. Think: "Napari", "Fiji", "Stardist"

Release: A Release is a specific version of an App. Releases represent the functionality of an App at a certain point
in time. Arkitekt Apps are always released with a version number that follows the [Semantic Versioning](https://semver.org/) standard.
Think: "Napari 0.4.10", "Fiji 1.53c", "Stardist 0.1.0"

Flavour: A Flavour is a specific configuration of an App. Flavours are used to provide different configurations of Apps, where the
core functionality is the same, but the configuration is different. Think: "Napari 0.4.10 on Python 3.8", "Fiji 1.53c with OpenJDK 11", 
"Stardist 0.1.0 with CUDA 10.2" or "Stardist 0.1.0 on the CPU"

Deployment: A Deployment is the "Intent" to run a certain Release of an App (e.g. "Napari 0.4.10"), with specific access rights and identified by
a user. Thinks: "Napari 0.4.10 on Python 3.8 authorized as John Doe and able to access all his files", on a specific backend.

Pod: A Pod is a running instance of a Deployment. Pods are the actual running containers that provide the functionality of an App. They
are the only model that is actively maintained by the Backend. Pods are identified by a container specific ID and are always associated with a Deployment.


Selector: A Selector declares a hardware or capability requirement a Flavour has of a backend (CUDA compute capability, RAM, labels matching a Resource's qualifiers, ...). Kabinet stores and serves selectors; the deployer that places Pods evaluates them. See [docs/selectors.md](docs/selectors.md) for the full vocabulary and its Kubernetes/Compose mapping.
