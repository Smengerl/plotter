# WebGUI Specifications — Plotter Pipeline Manager

**Version**: 1.2  
**Date**: 2026-05-11  
**Status**: Draft

---

## 1. Overview

The WebGUI is a browser-based front-end for managing image stylisation and pen plotter jobs.  
It exposes the existing CLI pipeline (`pipeline/core/main.py` + `PipelineRunner`) through a FastAPI backend and a Single Page Application (SPA) frontend, without modifying the core pipeline logic.

**Processing model:**  
Regular pipelines always produce a **stylised image** as their output (PNG/JPEG).  
Sending a result to the plotter is a separate, dedicated pipeline that takes a stylised image, converts it to SVG, generates GCode, and streams it to the GRBL controller — all in one pipeline run.

---

## 2. Glossary

| Term | Definition |
|---|---|
| **Image** | A raw source image stored in the `input/` folder |
| **Pipeline** | A YAML config file in the `tools/` folder that defines a sequence of processing steps |
| **Job** | A single execution of one Pipeline on one Image |
| **Output image** | A stylised **image** (PNG/JPEG) in the `output/` folder, produced by a regular pipeline job |
| **Plotter pipeline** | A dedicated pipeline that takes an output image, converts it to SVG, generates GCode, and sends it to the GRBL controller — all in one run. Does not produce a file on disk. |

---

## 3. Folder Conventions

| Role | Default path (relative to project root) | Configurable |
|---|---|---|
| Source images | `input/` | Yes (server config) |
| Pipeline configs | `tools/` | Yes (server config) |
| Output artifacts | `output/` | Yes (server config) |

Output image filenames follow the convention:  
`<image_stem>__<pipeline_stem>.png` (e.g. `portrait__standard_pipeline.png`)  
All output images are PNG/JPEG. GCode is an intermediate that exists only during the plotter pipeline run and is never stored persistently.  
The filename convention allows unambiguous reverse-mapping from output image to source image and pipeline without a database.

---

## 4. Functional Requirements

### 4.1 Image Library View (Home)

- Display all images found in `input/` as a **thumbnail grid**.
- Each thumbnail shows:
  - The image filename (stem only, truncated if long)
  - A **status badge** combining a coloured dot and a short text label:

| Condition | Dot colour | Label |
|---|---|---|
| No pipeline has ever run on this image | Blue | `New` |
| At least one pipeline successful, none currently running | Green | `{n} done` (count of successful pipelines) |
| All pipelines that have been run ended in error, none successful | Red | `Error` |
| A pipeline is currently running on this image | Yellow | `Running` |

  Priority when multiple states apply: `Running` > `Error` > green count > `New`.

- Thumbnails are sorted alphabetically by filename.
- Clicking a thumbnail opens the **Image Detail View** (§ 4.2).
- A clearly labelled **Upload** button allows adding new images to `input/` (§ 4.5).

### 4.2 Image Detail View

Activated by selecting a thumbnail. Shows a two-column layout:

**Left column — source image:**

- Full-resolution preview (constrained to viewport)
- Filename and basic EXIF-like metadata (width × height, file size, format)

**Right column — pipeline list:**

- For each pipeline config found in `tools/`, the entry is populated from the YAML fields loaded via `PipelineRunner.from_yaml()`:
  - **`name`** field from the YAML (falls back to the filename stem if absent)
  - **`description`** field from the YAML, rendered as a short subtitle below the name (omitted if not set)
  - **Status badge**: one of `not run` | `running` | `done` | `error` (§ 4.3)
  - If `done`: thumbnail of the output image from `output/`; hovering shows the full file path
    - Clicking the thumbnail opens a **Lightbox overlay** with the full-resolution output image
    - A **Download** button next to the thumbnail triggers a file download of the output image
  - If `not run` or `error`: a **Run** button to start (or re-run) the job (§ 4.3)
  - If `error`: the error reason is shown below the badge; the Run button is still available
- A back/close button returns to the Image Library View.

### 4.3 Job Execution

**Pipeline status model** — each pipeline/image combination has exactly one of these states:

| State | Description |
|---|---|
| `not run` | Pipeline has never been applied to this image |
| `running` | Pipeline is currently executing against this image |
| `done` | Pipeline completed successfully; artifact is available |
| `error` | Pipeline failed (technical error) or was cancelled by the user |

**Running a job:**

- Exactly **one job runs at a time** (single global worker slot).
- Starting a job on an image where a previous artifact already exists **silently overwrites** that artifact (no versioning).
- Re-running a pipeline whose status is `error` is always permitted via the Run button.
- While a job is running, a **status panel** is shown (globally visible, e.g. fixed at the bottom):
  - Source image thumbnail and image name
  - Active pipeline **`name`** (from YAML) as the panel title
  - Active pipeline **`description`** (from YAML) as a subtitle below the name (omitted if not set)
  - **Current step progress**: `Step n/m: <step label>` — updated in real time via the `on_progress` callback of `PipelineRunner`; the step label is `step.label` if set in the YAML, otherwise the step class name
  - Real-time log output streamed from the child process (via SSE)
  - A **hard-cancel button** (§ below)
  - All other Run buttons are disabled during execution

**Completion:**

- On success: status → `done`; output image thumbnail appears without page reload; log panel header updates to show `✓ Done`.
- On error or cancel: status → `error`; output image removed; log panel header updates to show `✗ Error` with a short reason.
- The log panel persists until the **next job is started** — it is never auto-dismissed and does not disappear on page navigation within the SPA.

**Log panel layout** (fixed at the bottom of the page, always visible while a result exists):

The panel has two states toggled by the user via a collapse/expand button:

- **Collapsed** (default after completion): only the header bar is visible, containing:
  - Status icon + label: `⟳ Running` | `✓ Done` | `✗ Error`
  - Source image name
  - Pipeline name
  - Cancel button (only while `Running`)
  - Expand button

- **Expanded**: header bar + scrollable log output area below it, showing all captured log lines since the job started. Log lines are colour-coded by severity:

| Level | Colour |
|---|---|
| `DEBUG` | muted grey (`--color-text-muted`) |
| `INFO` | default text (`--color-text`) |
| `WARNING` | orange (`--color-warning`) |
| `ERROR` / `CRITICAL` | red (`--color-error`) |

- The log area is capped at **500 lines**; older lines are dropped from the top when the limit is exceeded.
- The log area auto-scrolls to the bottom while `Running`; stops auto-scrolling if the user manually scrolls up.

**Hard cancel:**

- The user may press **Cancel** at any time during execution.
- Cancel sets a `threading.Event`; the job manager waits for the thread to finish its current inference step naturally (Python threads cannot be forcibly killed), then marks the job as `error` and deletes the output image if one was written.
- The result is identical to a technical error: status → `error`, output image removed, user can re-run immediately.

### 4.4 Send to Plotter

- Each `done` artifact image has a dedicated **Send to Plotter** button.
- Clicking it triggers the **plotter pipeline** — a dedicated YAML config that performs the full conversion chain internally:
  1. Takes the stylised artifact image as input
  2. Vectorises it to SVG (intermediate, not saved)
  3. Generates GCode from the SVG (intermediate, not saved)
  4. Streams the GCode to the GRBL controller via serial
- No persistent GCode or SVG file is written to `output/`; the plotter pipeline leaves no artifact on disk.
- The plotter job is subject to the same single-worker constraint as regular pipeline jobs (§ 4.3).
- If the plotter pipeline fails (e.g. serial port not found), the error is visible in the log panel like any other pipeline error.

### 4.5 Image Upload & Deletion

**Upload:**

- A drag-and-drop upload zone (also clickable for file picker) accepts JPEG, PNG, and TIFF files.
- Multiple files can be uploaded in one action.
- If a file with the same name already exists in `input/`, it is **silently overwritten**. All output images in `output/` that were produced from this input image are deleted, effectively resetting all pipeline statuses for that image to `not run`.
- Upload progress is shown per file (progress bar).
- After upload the thumbnail grid refreshes automatically.

**Delete:**

- Each input image has a **Delete** button (e.g. a trash icon on the thumbnail or in the detail view).
- Deleting an input image removes the source file from `input/` **and** all associated output images from `output/` (identified via the `<image_stem>__*` filename convention).
- A confirmation prompt is shown before deletion: *"Delete image and all N pipeline results?"*
- After deletion the thumbnail grid refreshes automatically; if the detail view was open for that image, it closes and returns to the library view.

### 4.6 Automatic UI Refresh

- The backend exposes a **single multiplexed SSE stream** at `/api/events`.  
  Events are distinguished via the SSE `event:` field:

  ```text
  event: refresh
  data: {"type": "refresh"}

  event: log
  data: {"level": "INFO", "msg": "Processing step 3/5…"}

  event: progress
  data: {"step": 3, "total": 5, "label": "Vectorizing"}
  ```

  `refresh` events are emitted whenever anything relevant changes (new input image, new output image, job state change, deletion). `log` events carry real-time log lines from the running job. `progress` events are emitted by the `on_progress` callback of `PipelineRunner` after each completed step and update the `Step n/m: <label>` display in the status panel without triggering a full data re-fetch.

- On receiving a `refresh` event, the frontend re-fetches all data it currently needs (`/api/input_images`, `/api/output_images`, `/api/jobs/current`) and re-renders the affected views. No full page reload occurs.
- `log` events are appended directly to the log panel without triggering a full data re-fetch.
- If the SSE connection drops, the frontend falls back to polling every 5 seconds.

---

## 5. Non-Functional Requirements

### 5.1 Architecture

- **Backend**: FastAPI (Python), served by Uvicorn.
- **Backend split — two clear layers inside `pipeline/gui/`**:
  - **API layer** (`routers/`): FastAPI route handlers only. Thin — validates input, calls the core layer, formats HTTP responses. No business logic.
  - **Core layer** (`job_manager.py`, `filesystem.py`, `log_handler.py`): all domain logic — job lifecycle, filesystem queries, log capture. No FastAPI imports.
- **RESTful interface**: all endpoints follow REST conventions (resources as nouns, HTTP verbs for actions, JSON bodies, standard status codes).
- **Frontend**: Single Page Application — plain HTML + CSS + vanilla JavaScript (no build toolchain required). Served as static files by FastAPI.
- **Pipeline execution in a background thread**: Each job is executed in a **`threading.Thread`** (via `loop.run_in_executor()`) rather than a subprocess. This ensures the pipeline is automatically terminated when the server process exits — no orphaned child processes. The pipeline is instantiated via **`PipelineRunner.from_yaml(config_path, on_progress=...)`**; the `on_progress` callback receives `(step_index, total_steps, label)` and pushes a structured `progress` event into the `asyncio.Queue` alongside log lines. The SSE endpoint in `routers/events.py` forwards these events to the frontend. `PipelineRunner.run()` is called directly in the thread; the FastAPI event loop stays responsive. Hard-cancel is implemented by setting a `threading.Event` that the job manager checks; since `PipelineRunner` has no cooperative cancel hook, the thread is abandoned on cancel (Python cannot forcibly kill a thread) and the output image is deleted if present.
- **No database**: State is derived from the filesystem (filenames in `input/`, `output/`, `tools/`) and maintained in a module-level **in-memory cache** inside `filesystem.py` for fast reads. The cache is the single source of truth at runtime; the filesystem is the source of truth on startup and after every mutating operation. No SQLite, no JSON state file.
- **Layer rule**: The GUI server lives in `pipeline/gui/` and calls `pipeline/core/main.py` as a subprocess. It must never be imported by `pipeline/core/main.py` or any core module (no upward dependency).

### 5.2 Concurrency

- The single worker slot is enforced by an `asyncio.Lock` in `job_manager.py`.
- The pipeline thread is dispatched via `loop.run_in_executor()`; log lines are captured by a custom `logging.Handler` that pushes structured records `{level, msg}` into an `asyncio.Queue`. The SSE endpoint in `routers/events.py` consumes this queue and emits both `log` and `refresh` event types over the single `/api/events` stream.
- **In-memory state cache** (`filesystem.py`):
  - On server startup, `filesystem.py` performs a full `os.scandir()` of `input/`, `output/`, and `tools/` to populate a module-level dict.
  - All subsequent read requests (e.g. `GET /api/input_images`) are served from this cache — no repeated directory scans.
  - Any mutating operation (upload, delete, job completion) calls `cache.invalidate()`, rescans only the affected directory, then emits a `refresh` SSE event.
  - Transient job state (`running` / `error` with reason string) is stored in the cache and never written to disk. On restart, any image present in `output/` is considered `done`; images with no corresponding file show `not run`.
  - Cache writes happen exclusively inside the `asyncio` event loop. Because FastAPI handles all requests on the event loop, no concurrent mutation of the cache is possible without holding the worker `asyncio.Lock`. No additional locking around the cache dict is required.
- **Server shutdown**: because the pipeline runs in a thread within the server process, it is automatically terminated when the server exits. No orphaned processes possible. On shutdown, the server waits **at most 10 seconds** for the worker thread to finish cleanly; after that timeout the process exits regardless.
- **Hard cancel**: `job_manager.cancel()` sets a `threading.Event`. The job manager checks this event after the thread completes; the output image is deleted if it was written. Since Python threads cannot be forcibly killed, the running step finishes naturally before cancellation takes effect — the job is then marked `error` and the output image removed.
- **Thumbnail generation**: generated on-the-fly on every request — no caching (in-memory or on-disk). Keeps the server simple and avoids stale thumbnails after output image overwrites.

### 5.3 Frontend State Model

The SPA uses a **single reactive state object** as its sole source of truth. All UI rendering is driven by this object; no state is read back from the DOM.

```javascript
// Central state — never mutated directly; always via setState()
let state = {
    images:        [],      // list of input image descriptors
    outputImages:  [],      // list of output image descriptors
    pipelines:     [],      // list of available pipeline configs
    currentJob:    null,    // running/last-completed job or null
    logs:          [],      // log lines for the current job (max 500)
    view:          'library',  // 'library' | 'detail'
    selectedImage: null,    // image name string or null
};

/**
 * Merge patch into state and trigger a full re-render.
 * @param {Partial<typeof state>} patch
 */
function setState(patch) {
    state = { ...state, ...patch };
    render(state);
}
```

- `render(state)` is the single entry point for all DOM updates. It is idempotent and may be called at any time.
- SSE `refresh` events trigger a data re-fetch (`/api/input_images`, `/api/output_images`, `/api/jobs/current`) followed by `setState(...)`.
- SSE `log` events call `setState({ logs: [...state.logs.slice(-499), newLine] })` directly — no HTTP round-trip.
- User interactions (button clicks, navigation) call `setState(...)` to update `view` / `selectedImage` and trigger re-render.
- The log area enforces a **500-line cap** inside `setState`: lines beyond the cap are dropped from the top.

### 5.4 Styling

- CSS only — no CSS framework (no Bootstrap, no Tailwind).
- Central design tokens defined as CSS custom properties on `:root`:

```css
:root {
  --color-bg:         #1a1a1a;
  --color-surface:    #242424;
  --color-border:     #333333;
  --color-accent:     #e8a020;   /* plotter orange */
  --color-text:       #e0e0e0;
  --color-text-muted: #888888;
  --color-success:    #4caf50;
  --color-error:      #e53935;
  --color-warning:    #fb8c00;
  --radius:           6px;
  --font-mono:        'JetBrains Mono', 'Fira Mono', monospace;
  --font-ui:          system-ui, sans-serif;
  --shadow:           0 2px 8px rgba(0,0,0,0.4);
}
```

- Dark theme by default; no light/dark toggle required in v1.
- Responsive layout: thumbnail grid uses CSS Grid with `auto-fill` columns.

### 5.5 Configuration

The GUI server (`server.py`) starts Uvicorn internally and accepts optional CLI arguments. All arguments have defaults so the server can be launched without any flags.

| CLI argument | Default | Description |
|---|---|---|
| `--input-dir` | `input/` | Source image folder |
| `--tools-dir` | `pipeline/configs/` | Folder scanned for pipeline YAML configs |
| `--output-dir` | `output/` | Output image folder |
| `--host` | `127.0.0.1` | Uvicorn bind address |
| `--port` | `8000` | Uvicorn port |
| `--log-level` | `info` | Uvicorn log level |

Pipeline discovery: at startup (and on each `/api/pipelines` request) the server scans `--tools-dir` for all `*.yaml` / `*.yml` files and exposes them as available pipelines. No hardcoded pipeline list exists.

The `pipeline-server` entry point starts the server from within the project's `.venv` without any extra arguments:

```sh
# Start with defaults
.venv/bin/pipeline-server

# Optional overrides
.venv/bin/pipeline-server --port 9000 --log-level debug
```

### 5.6 Error Handling

- If `input/`, `tools/`, or `output/` directories do not exist at startup, the server logs a warning and creates them.
- If a YAML config in `tools/` is malformed, it is listed with an `invalid` badge and a tooltip showing the parse error; it cannot be run.
- Pipeline runtime errors are caught, logged, and reported in the live log panel.
- HTTP errors return JSON `{"error": "<message>"}` with appropriate status codes.

---

## 6. REST API Sketch

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/input_images` | List all source images with output image counts (served from cache) |
| `GET` | `/api/input_images/{name}/thumbnail` | Serve source image thumbnail (JPEG, max 256 px) |
| `GET` | `/api/input_images/{name}/full` | Serve full source image inline (`Content-Disposition: inline`) |
| `GET` | `/api/input_images/{name}/download` | Download source image as file (`Content-Disposition: attachment`) |
| `POST` | `/api/input_images/upload` | Upload one or more images to `input/`; overwrites duplicates and clears their output images |
| `DELETE` | `/api/input_images/{name}` | Delete source image and all associated output images |
| `GET` | `/api/pipelines` | List all pipeline configs with metadata (served from cache) |
| `GET` | `/api/output_images` | List all output images with source/pipeline mapping (served from cache) |
| `GET` | `/api/output_images/{name}` | Serve an output image file inline (`Content-Disposition: inline`) |
| `GET` | `/api/output_images/{name}/thumbnail` | Serve output image thumbnail (JPEG, max 256 px) |
| `GET` | `/api/output_images/{name}/download` | Download output image as file (`Content-Disposition: attachment`) |
| `POST` | `/api/jobs` | Start a new job `{image, pipeline}` |
| `DELETE` | `/api/jobs/current` | Hard-kill the running job |
| `GET` | `/api/jobs/current` | Status of the current job (served from in-memory job state) |
| `GET` | `/api/events` | **Multiplexed SSE stream**: `event: refresh` for state changes, `event: log` for job log lines |
| `POST` | `/api/plotter/send` | Start plotter pipeline for a given output image |
| `GET` | `/` | Serve SPA `index.html` |
| `GET` | `/static/{path}` | Serve static assets |

---

## 7. File Structure

```text
pipeline/
  gui/server.py           ← entry point (also callable via `pipeline-server` entry point)
  gui/
    specifications.md       ← this document
    server.py               ← FastAPI app factory + Uvicorn entry point; parses CLI args
    config.py               ← ServerConfig dataclass + env loading
    job_manager.py          ← single-worker asyncio.Lock, run_in_executor dispatch, cancel threading.Event, log asyncio.Queue
    log_handler.py          ← logging.Handler subclass: captures records, formats to {level, msg}, pushes to Queue
    filesystem.py           ← in-memory cache + pure functions: list images, list pipelines, resolve artifacts; rescans on mutation
    routers/
      images.py             ← GET /api/input_images, GET /api/input_images/{name}/*, POST /api/input_images/upload
      pipelines.py          ← GET /api/pipelines
      output_images.py      ← GET /api/output_images, GET /api/output_images/{name}/*
      jobs.py               ← POST /api/jobs, DELETE /api/jobs/current, GET /api/jobs/current
      events.py             ← GET /api/events — multiplexed SSE: consumes log Queue + emits refresh notifications
      plotter.py            ← POST /api/plotter/send
    static/
      index.html            ← SPA entry point
      app.js                ← SPA logic: central state object, setState(), render(), SSE client
      style.css             ← all styles + CSS design tokens
```

---

## 8. Out of Scope (v1)

- User authentication / access control
- Multi-user / multi-worker parallelism
- Persistent job history (database)
- Light theme
- Mobile-native optimisation (responsive is sufficient)
- Editing pipeline YAML files through the GUI
- Drag-and-drop job reordering / queuing

---

## 9. Resolved Design Decisions

All open questions from earlier drafts are resolved:

| # | Topic | Decision |
|---|---|---|
| 1 | **Plotter connection status** | No status indicator in v1. If the plotter pipeline fails (e.g. serial port not found), the error appears in the log panel like any other pipeline failure. `GET /api/plotter/status` is not implemented and not listed in the API. |
| 2 | **Artifact overwrite on re-run** | Silent overwrite — no versioning. The previous output image is replaced in-place. The in-memory cache entry for that image is updated immediately and a `refresh` SSE event is emitted. |
| 3 | **Thumbnail generation** | On-the-fly per request, no caching. Accepted tradeoff: potential slowness for very large image libraries is acceptable in v1. |
| 4 | **Cancel semantics** | A `threading.Event` is set; the running pipeline step finishes naturally (threads cannot be killed). Once the thread exits, the job is marked `error` and the output image is deleted if present. Cancel latency equals the duration of the current pipeline step. |
| 5 | **Cache consistency on concurrent requests** | The in-memory cache in `filesystem.py` is mutated only inside the `asyncio` event loop. Because FastAPI is single-threaded on the event loop, no concurrent cache mutation is possible without holding the worker `asyncio.Lock`. No separate lock around the cache dict is required. |
