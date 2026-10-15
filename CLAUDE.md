# kabinet

Notes for whoever changes this service, person or agent.

## Migrations and jobs

A container of this image only serves. An installer (konstruktor) prepares the database with
`arkitekt-service run migrate` once per build — before the first start, and in an update before
anything is recreated — and runs everything else as a job the image offers by name
(`konstruktor job run kabinet <job>`). Nothing is migrated, seeded or repaired at start.

**Read the rules before changing a model, a management command or `kabinet_server/contract.py`:**
<https://github.com/arkitektio/arkitekt-service/blob/main/docs/migrations-and-jobs.md>. The ones that are broken most easily:

- A model change and its migration are one commit.
- Within a major, a migration leaves a schema the previous release still runs on: a failed
  update, and a rollback, start the old build on the migrated database. What cannot do that
  is a `feat!:`.
- A `manage.py` command an operator should be able to run on a hub is declared in `jobs=` in
  `kabinet_server/contract.py`; one nobody runs is deleted. Any job is safe to run again.
- What `setup=` names runs for every build, after the migrations: it changes nothing the
  second time and needs nothing but the database and the config.
- Existing data is rewritten by a data migration when that needs only the database (it runs
  once, with the service stopped), and by a re-runnable job in `setup=` when it needs the
  service's code or its storage. There is no upgrade step, and nothing is keyed to a version.

What this service declares:

- Setup, in order: `ensureadmin`, `ensurerepos`, `restore_descriptors`, `restore_bloks`.
  `restore_descriptors` stores the descriptors of every flavour, release, definition, deployment
  and pod that misses a declared key (rows from before a key existed); `--all` describes every
  row again after a describer changed what a key means. `restore_bloks` stores what a flavour's
  bloks draw (`Flavour.blok_renders`, parsed from their BSX) and which blok draws each action
  (`Flavour.action_logos`) for flavours imported before either existed; `--all` renders every
  flavour again after the parser changed.
- Other jobs: none.
- Not jobs, on purpose: `printschema` regenerates the committed `schema.graphql`: a developer's tool, run in a checkout.

`tests/test_prepared.py` holds the contract to this: migrations committed, every job a command
of this service, the setup run twice. In `deployments/next` the service runs
`arkitekt-service standalone --debug`, which migrates and then serves: restart its container
to apply a new migration.

## Descriptors

Every descriptor is stored (`stored_descriptors`, recomputed on every save by
`arkitekt_service`), so a port's `requires` is the `requires` argument of a list filter, one
indexed query. The describers are in `kabinet_server/descriptors.py` and read the row, or a row
it points to: a deployment's and a pod's `@kabinet/backend_kind` is its backend's, so
`declareBackend` restores them (`service.restore`) when the kind changes. A bulk write
(`update()`, `bulk_update`) of a field a descriptor reads restores the rows too; the embedding
healer's `bulk_update` writes only embedding columns, which no descriptor reads.

The other direction, an object's descriptors asked of a definition's ports (`demands` with
`descriptors`, what the install menu sends), reads each port's `requires` / `provides` off the
`args` / `returns` JSON: `bridge/managers.py` compiles them in SQL to the JSONPath rekuest
compiles at write time (`facade/descriptors.py`), so the two answer alike. Change one, change both.

A flavour's hardware descriptors (`gpu`, `arch`, `min_ram_mb`, `min_vram_mb`) read its
`required` selectors only: a preference is no minimum. `@kabinet/gpu` is `none` without a
required accelerator and `multiple` when more than one vendor's is required (no single
vendor's backend runs it). `@kabinet/flavour_name` is `Flavour.name` (vanilla, cuda);
`Flavour.flavour` holds the image's digest.
