# 🏗️ Architecture — Audio Event Routing Simulator (AERS)

## 1) System Overview

AERS simulates and visualizes how audio events traverse modular routing graphs (sources → processors → mixers → outputs).  
It is composed of a **Core Engine**, a **Module Runtime (DSP plug-ins)**, a **Realtime Telemetry Service**, and a **Web UI Dashboard**.

+---------------------------+ ws/grpc +----------------------+
| Core Engine (Python) | <-------------------------> | UI Dashboard (Web) |
| - GraphEngine | metrics, graph, meters | - Graph view |
| - EventScheduler | | - VU meters |
| - BufferRouter | | - Module controls |
+------------+--------------+ +----------+-----------+
| ^
plugin API (ctypes/py) |
v |
+------------+--------------+ control plane (REST) |
| Module Runtime | <----------------------------------------+
| - Built-in DSP (gain..) |
| - External DSP (C++/Py) |
+------------+--------------+
|
| persisted configs / state
v
+------------+--------------+
| Storage & Config (SQLite, |
| YAML/JSON sessions) |
+---------------------------+

markdown
Copy code

---

## 2) Components

### 2.1 Core Engine
- **GraphEngine**  
  - Loads a routing DAG from YAML/JSON, validates it against JSON-Schema, builds an in-memory graph.
  - Node types: `Source`, `Processor`, `Mixer`, `Bus`, `Output`.
- **EventScheduler**  
  - Time-stamped event timeline generator (synthetic or replay). Supports sample-accurate scheduling (@ 48 kHz).
- **BufferRouter**  
  - Pull-based propagation: downstream nodes request buffers; engine pulls from upstream to satisfy demand.
  - Fixed block sizes (e.g., 256/512 frames), with configurable hop sizes.
- **TelemetryCollector**  
  - Emits per-node metrics (RMS/peak, CPU time, queue depth, latency) over WebSocket.

### 2.2 Module Runtime
- **Built-in DSP**: `Gain`, `BiquadEQ`, `Delay`, `Mixer`, `Limiter`.
- **External DSP**: C++ or Python modules loaded dynamically.
  - Interface via `ctypes` or `cffi` for C++; abstract base class for Python.
  - Sandboxed loading (manifest allowlist + hash verification).

### 2.3 Realtime Telemetry Service
- **FastAPI** app hosting:  
  - **WebSocket** `/ws/telemetry` → meters, graph mutations, status.  
  - **REST** `/api` → control plane for loading configs, starting/stopping runs, module parameters.

### 2.4 UI Dashboard (React/Next.js)
- Graph visualization (DAG), node inspector, parameter panels, live VU meters, latency bars.
- Connects to WebSocket for telemetry; uses REST for control.

### 2.5 Storage & Config
- **SQLite** for session state (runs, metrics snapshots, module presets).
- **YAML/JSON** for routing graphs and module manifests.
- **File layout**
  - `configs/graph/*.yaml` — routing graphs
  - `configs/modules/*.json` — module manifests (signed)
  - `data/` — optional audio assets for event replay

---

## 3) Data & Control Flows

### 3.1 Audio Buffer Flow (pull-based)

[Output Node] --pull--> [Upstream Processor] --pull--> ... --pull--> [Source]
| ^
+--render(blockSize, t)---------------------------------------+

markdown
Copy code

- **Rationale:** Pull model helps bound latency and CPU, and avoids upstream over-production.

### 3.2 Telemetry Flow

Core Engine Telemetry WS UI Dashboard
| | |
|-- metrics JSON ------->| |
| |==> broadcast =========>| (meters, CPU, graph deltas)
|<-- control msgs -------|<====== REST ========== | (start/stop, params)

yaml
Copy code

- Engine pushes periodic telemetry (e.g., every 50–100 ms).  
- UI sends parameter changes via REST, which Core applies atomically between audio blocks.

---

## 4) API Surfaces

### 4.1 WebSocket (Telemetry)

- **URL:** `ws://localhost:8080/ws/telemetry`
- **Message format (server → client):**
```json
{
  "ts": 1731379200.120,
  "type": "frame",
  "graph_id": "session-001",
  "meters": {
    "node/dialogue_gain": { "rms": -18.2, "peak": -3.1 },
    "node/master_limiter": { "rms": -12.0, "peak": -0.1 }
  },
  "latency": { "overall_ms": 7.8, "by_node_ms": {"dialogue_gain": 0.2, "master_limiter": 0.6} },
  "cpu": { "by_node_pct": {"dialogue_gain": 0.6, "master_limiter": 1.8} }
}
Message format (client → server; optional control via WS):

json
Copy code
{
  "type": "setParam",
  "node": "dialogue_gain",
  "param": "gain_db",
  "value": -3.0
}
Note: Primary control plane is REST; WS control is optional and can be disabled.

4.2 REST (Control Plane)
POST /api/session/load — load a routing graph.

json
Copy code
{
  "graph_config_path": "configs/graph/stage_mix.yaml"
}
POST /api/session/start — start simulation.

json
Copy code
{ "block_size": 512, "sample_rate": 48000, "realtime": true }
POST /api/session/stop

PATCH /api/nodes/{node_id}/params

json
Copy code
{ "gain_db": -6.0 }
GET /api/nodes → list nodes & params

GET /api/health

5) Configuration Schemas
5.1 Graph Config (YAML)
yaml
Copy code
graph_id: stage_mix
sample_rate: 48000
block_size: 512

nodes:
  - id: src_dialogue
    type: source
    source:
      kind: sine # or "file"
      freq_hz: 440
      level_db: -18
      # if kind=file: path: data/dialogue.wav, loop: true

  - id: fx_dialogue_gain
    type: processor
    module: builtin/gain
    params: { gain_db: -3.0 }

  - id: fx_dialogue_eq
    type: processor
    module: builtin/biquad_eq
    params:
      bands:
        - { type: "hp", freq_hz: 80, q: 0.707 }
        - { type: "peak", freq_hz: 3500, q: 1.0, gain_db: 2.5 }

  - id: bus_dialogue
    type: mixer
    inputs: []

  - id: out_main
    type: output
    sink: null # future: "jack", "portaudio", "wav:file=data/out.wav"

edges:
  - { from: src_dialogue,     to: fx_dialogue_gain }
  - { from: fx_dialogue_gain, to: fx_dialogue_eq   }
  - { from: fx_dialogue_eq,   to: bus_dialogue     }
  - { from: bus_dialogue,     to: out_main        }
5.2 Module Manifest (signed JSON)
json
Copy code
{
  "name": "ext/plate_reverb",
  "version": "0.1.0",
  "entry": "libplate.so",
  "lang": "cpp",
  "params": {
    "mix": {"type": "float", "min": 0.0, "max": 1.0, "default": 0.2},
    "decay_s": {"type": "float", "min": 0.1, "max": 10.0, "default": 2.2}
  },
  "hash": "sha256:2f5e...f1a",
  "signature": "base64-der-sig..."
}
6) Module Interface Contracts
6.1 Python DSP Base Class
python
Copy code
class DspModule:
    def __init__(self, sample_rate: int, block_size: int, **params): ...
    def process(self, inputs: list[np.ndarray]) -> np.ndarray: ...
    def set_param(self, name: str, value): ...
    def get_meters(self) -> dict: ...  # e.g., {"rms": -18.2, "peak": -1.0}
6.2 C ABI (C++ plug-ins via ctypes)
c
Copy code
// allocate / init with sample_rate, block_size, returns handle
void* dsp_create(int sample_rate, int block_size);
// process N input channels of len=block_size, returns interleaved float* out
float* dsp_process(void* handle, const float** inputs, int num_inputs);
// set param by name
int dsp_set_param(void* handle, const char* key, float value);
// meters to provided struct
int dsp_get_meters(void* handle, float* rms, float* peak);
// free resources
void dsp_destroy(void* handle);
7) Sequence Diagrams
7.1 Session Start
sql
Copy code
UI             REST API               Core Engine            Telemetry WS
| POST /load     |                         |                      |
|--------------->| validate schema         |                      |
|                |------------------------>| build GraphEngine    |
|                |<------------------------| ok                   |
| POST /start    |                         |                      |
|--------------->|                         | start scheduler      |
|                |                         | open WS broadcaster  |
|                |                         | emit first metrics --+---->
7.2 Realtime Param Change
bash
Copy code
UI               REST API            Core Engine
| PATCH /nodes/{id}/params            |
|------------------------------------>|
|                                     | stage change (thread-safe)
|                                     | swap in next audio block boundary
| <------------------------------ 200 |
8) Performance & Tuning
Targets

Graph render cycle: ≤ 10 ms (@ 48 kHz, 512-sample blocks)

End-to-end internal latency (graph): ≤ 20 ms

UI refresh: 10–20 Hz telemetry frames

Tuning Levers

Choose block size 256/512 to balance CPU vs latency.

Use NumPy/PyTorch vectorization for DSP kernels.

Optional C++ for hot DSPs (EQ, limiter).

Pre-allocate buffers; avoid per-block allocations.

9) Security Model
Config validation with JSON-Schema (deny unknown fields; explicit node/module allowlists).

Module manifests must include hash and signature; verify before loading.

Restricted module search path (no network fetch at runtime).

Exec isolation: Python modules run in restricted import context; C++ via controlled ABI.

API auth (optional): token-based auth for REST if exposed beyond localhost.

10) Observability
Metrics: per-node CPU ms, RMS/peak, queue depth, xruns, block processing time.

Logs: structured JSON logs (engine state changes, module loads, warnings).

Debug modes: deterministic seed, offline render (non-realtime), trace per-block timings.

Snapshots: periodic writes to SQLite for post-run analysis.

11) Testing Strategy
Unit tests: graph construction, cycle detection, buffer math, DSP correctness.

Golden tests: known input → expected output RMS/peak within tolerance.

Latency tests: measure end-to-end blocks across sample rates & sizes.

Property-based: fuzz graph topology & parameter ranges.

CI: static type check (mypy), lint (ruff), unit tests, schema validation.

12) Deployment
Local dev: docker-compose up for API + UI; engine runs in same container or separate service.

Profiles: dev (hot reload, verbose), prod (frozen deps, optimized DSP).

Artifacts: versioned Docker images, SBOM, vulnerability scans.

13) Roadmap (Architecture-Relevant)
A-01: JACK / PortAudio sink for realtime system audio output.

A-02: gRPC streaming bus for multi-host graph splits.

A-03: On-graph recording nodes (write stems, pre/post-FX).

A-04: MIDI/OSC control node types.

A-05: Preset system & templated subgraphs (e.g., 5.1 mix).

