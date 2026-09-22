# Selectors

A **selector** declares a hardware or capability requirement a backend must
satisfy to run a flavour of an app. Selectors are how one release ships a CUDA
build and a CPU build, and how the right one ends up on the right machine.

Selectors follow the shape of the placement vocabularies people already know:

| Kabinet concept | Kubernetes analog | Docker Compose analog |
|---|---|---|
| `required: true` (default) | `requiredDuringSchedulingIgnoredDuringExecution` | a reservation that must be satisfiable |
| `required: false` + `weight` | `preferredDuringScheduling...` + `weight` | — |
| `label` selector ↔ resource `qualifiers` | `nodeSelector` / node labels | — |
| `cuda` selector (`count`) | `resources.limits."nvidia.com/gpu"` | `deploy.resources.reservations.devices` (`count`, `capabilities: [["gpu"]]`) |
| `cpu.arch` | `kubernetes.io/arch` node label | `platform:` (`amd64`, `arm64`) |

**Kabinet stores and serves selectors; it does not evaluate them.** There is
deliberately no server-side matching endpoint: evaluation happens in the
*deployer* that places pods, because only the deployer can see the actual
hardware. The contract:

- a deployer **MUST NOT** place a flavour on a backend that fails one of its
  `required` selectors — if it cannot even determine the answer for a kind it
  does not understand, it must refuse rather than guess;
- a deployer **SHOULD** rank candidates by the summed `weight` of satisfied
  non-required selectors.

## Not a selector: services

A service dependency (mikro, rekuest, …) is a **Requirement**
(`InspectionInput.requirements` / the manifest's `requirements`), never a
selector. Requirements are composed by the deployment (fakts hands the app its
service endpoints); selectors only constrain *hardware placement*. There used
to be a vestigial `ServiceSelector` type — it was removed.

## The kinds

Every selector carries `kind`, `required` (default `true`) and `weight`
(default `1`) plus its own fields. All quantities use fixed units noted below —
no unit-suffixed strings.

### `cpu`
| field | meaning |
|---|---|
| `minCount` | minimum number of CPU cores |
| `frequency` | minimum CPU frequency, in MHz |
| `arch` | CPU architecture of the image (`amd64`, `arm64`, … — docker platform values) |

### `ram`
| field | meaning |
|---|---|
| `min` | minimum system memory, in MB |

(System memory lives here, not on `cpu` — a migration moved old `cpu.memory`
values into sibling `ram` selectors.)

### `cuda`
| field | meaning |
|---|---|
| `computeCapability` | minimum CUDA compute capability (e.g. `"8.6"`) — NVIDIA's standard placement key |
| `cudaVersion` | minimum CUDA driver/runtime version |
| `memory` | minimum GPU memory (VRAM), in MB |
| `count` | number of GPUs (a Docker device-reservation count; unset lets the deployer decide — the docker deployer requests all available) |
| `cudaCores` | deprecated — prefer `computeCapability` + `memory` |

### `rocm`
| field | meaning |
|---|---|
| `apiVersion` | minimum ROCm API version |
| `apiThing` | additional ROCm capability qualifier |

### `oneapi`
| field | meaning |
|---|---|
| `oneapiVersion` | minimum oneAPI version |

### `label`
| field | meaning |
|---|---|
| `key` | qualifier key the backend resource must carry (required) |
| `value` | value the qualifier must have; `null` means the key merely has to exist (k8s `Exists`) |

`label` is the general-purpose escape hatch: deployers publish what they know
about their hardware as `Resource.qualifiers` (`{key, value}` pairs), and a
label selector matches against them — the two halves of a Kubernetes
`nodeSelector`.

## Authoring

In a flavour's config (`.arkitekt/flavours/<name>/config.yaml`, or a
repo's `kabinet.yml` app image):

```yaml
selectors:
  - kind: cuda
    computeCapability: "8.6"
    memory: 8000
  - kind: ram
    min: 16000
  - kind: label
    key: microscope
    value: lightsheet
    required: false
    weight: 10
```

Via the CLI: `arkitekt-next plugin selector add <flavour> --kind cuda
--compute-capability 8.6 --vram 8000` (see the CLI docs for all flags).

On the wire, `SelectorInput` is a merged discriminated union (`@unionElementOf`
/ kante `merged_input`): one flat input whose per-kind member types generated
clients rebuild into a tagged union. The member models, the stored JSON on
`Flavour.selectors`, and the `Flavour.selectors` output types are all the same
pydantic models (`bridge/repo/selectors.py`) — input, storage and output
cannot drift.
