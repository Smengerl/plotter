# GUI Implementation Plan — Plotter Pipeline Manager

**Reference**: `specifications.md`  
**Date**: 2026-05-11  
**Branch**: grbl

Each step is self-contained and ends with a verification prompt that checks all requirements
before proceeding to the next step.

---

## Step 1 — Project Scaffold & Server Entry Point

**What**: Create the file structure, `server.py` (FastAPI app factory + Uvicorn entry point),
and `config.py` (ServerConfig).  
No business logic yet — just wiring and a working `/` → `index.html` route.

**Prompt**:

```
Create the following files for the Plotter Pipeline Manager GUI:

1. `pipeline/gui/server.py`
   - FastAPI app factory function `create_app(cfg: ServerConfig) -> FastAPI`
   - CLI entry point via `if __name__ == "__main__"` using argparse (also registered as `pipeline-server` entry point in pyproject.toml)
   - CLI arguments (all optional, see specifications § 5.5):
       --input-dir   (default: input/)
       --tools-dir   (default: pipeline/configs/)
       --output-dir  (default: output/)
       --host        (default: 127.0.0.1)
       --port        (default: 8000)
       --log-level   (default: info)
   - Creates input-dir, tools-dir, output-dir if they do not exist (log warning)
   - Serves static files from `pipeline/gui/static/` at `/static`
   - Serves `pipeline/gui/static/index.html` at `/`
   - Registers all routers from `pipeline/gui/routers/` (stubs for now)
   - Starts Uvicorn with the given host/port/log-level

2. `pipeline/gui/config.py`
   - `ServerConfig` dataclass with fields matching all CLI arguments
   - All fields have defaults matching the CLI defaults

3. ~~`pipeline/scripts/run_server.sh`~~ — replaced by the `pipeline-server` entry point

4. `pipeline/gui/static/index.html`  — minimal placeholder only:
   `<h1>Plotter Pipeline Manager</h1>`

5. `pipeline/gui/static/app.js`     — empty placeholder
6. `pipeline/gui/static/style.css`  — empty placeholder

7. All `pipeline/gui/routers/` router files as empty stubs (just `router = APIRouter()`):
   `images.py`, `pipelines.py`, `output_images.py`, `jobs.py`, `events.py`, `plotter.py`

After creating the files, verify:
- [ ] `python pipeline/gui/server.py --help` lists all 6 CLI arguments with correct defaults
- [ ] `.venv/bin/pipeline-server --help` produces the same output
- [ ] `python pipeline/gui/server.py` starts without error; `GET /` returns 200
- [ ] All 6 router stub files exist under `pipeline/gui/routers/`
- [ ] No import of `pipeline/gui/` from any core module (check with grep)
```

---

## Step 2 — Filesystem Layer (`filesystem.py`)

**What**: In-memory cache of `input/`, `tools/`, `output/`.  
Pipeline metadata (`name`, `description`) is loaded via `PipelineRunner.from_yaml()`.

**Prompt**:

```
Implement `pipeline/gui/filesystem.py` according to specifications § 5.1 and § 5.2.

Requirements:
- Module-level in-memory cache (a dict) as single runtime source of truth
- On `init_cache(cfg: ServerConfig)` at server startup: full os.scandir() of all three dirs
- Cache structure:
    {
      "input_images":   list[dict]  # {name, path, width, height, size_bytes, format}
      "output_images":  list[dict]  # {name, path, source_image, pipeline_stem}
      "pipelines":      list[dict]  # see below
    }
- Pipeline entries are populated by calling `PipelineRunner.from_yaml(path)` for each
  YAML file found in tools-dir:
    {
      "stem":        str,          # filename without extension
      "path":        Path,
      "name":        str,          # from YAML `name` field; fallback: stem
      "description": str | None,   # from YAML `description` field
      "valid":       bool,         # False if from_yaml() raised an exception
      "error":       str | None,   # exception message if valid=False
    }
- `invalidate(section: Literal["input_images", "output_images", "pipelines"])`:
  rescans only the affected directory, updates the cache entry for that section
- Pure query functions (no side effects, read from cache):
    get_input_images() -> list[dict]
    get_output_images() -> list[dict]
    get_pipelines() -> list[dict]
    get_pipeline_by_stem(stem: str) -> dict | None
    get_output_images_for_input(image_name: str) -> list[dict]

After implementing, verify:
- [ ] `init_cache()` populates all three sections without error (even on empty dirs)
- [ ] A malformed YAML in tools-dir results in valid=False, error set, not an exception
- [ ] Pipeline entry `name` falls back to stem when YAML has no `name` field
- [ ] Pipeline entry `description` is None when YAML has no `description` field
- [ ] `invalidate("pipelines")` re-reads only tools-dir, not input or output
- [ ] All query functions return copies (mutations by caller do not affect the cache)
- [ ] No FastAPI imports anywhere in filesystem.py
```

---

## Step 3 — Log Handler (`log_handler.py`)

**What**: A `logging.Handler` subclass that captures pipeline log records and pushes
structured `{level, msg}` dicts into an `asyncio.Queue`.

**Prompt**:

```
Implement `pipeline/gui/log_handler.py` according to specifications § 5.2.

Requirements:
- Class `QueueLogHandler(logging.Handler)`:
    - Constructor accepts an `asyncio.Queue` and the running event loop
    - `emit(record)` formats the record to `{level: str, msg: str}` and puts it
      into the queue using `loop.call_soon_threadsafe(queue.put_nowait, item)`
      (the handler runs in the pipeline worker thread, not the event loop)
    - Level string is one of: DEBUG | INFO | WARNING | ERROR | CRITICAL
- Helper function `attach_to_pipeline_logger(queue, loop) -> QueueLogHandler`:
    - Creates a `QueueLogHandler`
    - Attaches it to the root logger (or `pipeline.*` logger hierarchy)
    - Returns the handler so the caller can remove it after the job ends
- Helper function `detach(handler: QueueLogHandler)`:
    - Removes the handler from whichever logger it was attached to

After implementing, verify:
- [ ] A log message emitted from a worker thread appears in the queue within the
      event loop (write a small inline test: thread logs, queue is drained)
- [ ] `level` field is always an uppercase string, not an int
- [ ] `detach()` removes the handler cleanly; subsequent log messages do not appear
- [ ] No FastAPI imports in log_handler.py
```

---

## Step 4 — Job Manager (`job_manager.py`)

**What**: Single-worker asyncio lock, `run_in_executor` dispatch, cancel event,
progress callback → queue, in-memory job state.

**Prompt**:

```
Implement `pipeline/gui/job_manager.py` according to specifications § 4.3 and § 5.2.

Requirements:
- Module-level state (not a class):
    _lock: asyncio.Lock          # enforces single-worker constraint
    _cancel_event: threading.Event
    _current_job: dict | None    # see schema below
    _log_queue: asyncio.Queue    # shared with QueueLogHandler and SSE endpoint
    _loop: asyncio.AbstractEventLoop | None

- Current job schema:
    {
      "image_name":          str,
      "pipeline_stem":       str,
      "pipeline_name":       str,       # from PipelineRunner.name
      "pipeline_description": str|None, # from PipelineRunner.description
      "status":              "running"|"done"|"error",
      "error_reason":        str|None,
      "step_current":        int,       # last reported step index (0 = not started)
      "step_total":          int,       # total steps reported by runner
      "step_label":          str,       # last reported step label
    }

- `init(loop: asyncio.AbstractEventLoop)`: stores loop reference, initialises queue

- `get_current_job() -> dict | None`: returns a copy of _current_job

- `get_log_queue() -> asyncio.Queue`: returns the shared queue for the SSE endpoint

- `async run_job(image_name, pipeline_path, input_path, output_path) -> None`:
    - Acquires _lock; raises RuntimeError if already running (should not happen; API
      layer checks first via get_current_job())
    - Resets _cancel_event
    - Sets _current_job to a fresh dict with status="running"
    - Builds the runner via `PipelineRunner.from_yaml(pipeline_path, on_progress=_on_progress)`
    - Stores pipeline_name and pipeline_description from runner.name / runner.description
    - Attaches QueueLogHandler to the pipeline logger
    - Dispatches `runner.run(ctx)` via `loop.run_in_executor(None, runner.run, ctx)`
    - After completion:
        - Detaches log handler
        - If _cancel_event is set OR an exception occurred:
            - Deletes output image if it exists
            - Sets status="error", error_reason=str(exc) or "Cancelled by user"
        - Otherwise: status="done"
    - Releases _lock
    - Emits a "refresh" notification (see step 5 for the notify helper)

- `def _on_progress(step_index: int, total_steps: int, label: str) -> None`:
    - Updates _current_job["step_current"], ["step_total"], ["step_label"]
    - Pushes `{"type": "progress", "step": i, "total": n, "label": label}`
      into _log_queue via loop.call_soon_threadsafe

- `def request_cancel() -> bool`:
    - Sets _cancel_event; returns True if a job was running, False otherwise

After implementing, verify:
- [ ] Two concurrent `run_job` calls: the second raises RuntimeError immediately
- [ ] `_on_progress` callback updates _current_job fields and enqueues a progress item
- [ ] After a successful job: status="done", output image exists, log handler removed
- [ ] After cancel: status="error", output image deleted, error_reason="Cancelled by user"
- [ ] After exception in runner.run: status="error", error_reason=str(exc)
- [ ] No FastAPI imports in job_manager.py
```

---

## Step 5 — SSE & Notify Helper (`routers/events.py`)

**What**: The multiplexed `/api/events` SSE endpoint emitting `refresh`, `log`,
and `progress` events from the shared queue.

**Prompt**:

```
Implement `pipeline/gui/routers/events.py` and a module-level notify helper
according to specifications § 4.6 and § 5.2.

1. `pipeline/gui/notify.py` — thin notify helper:
   - `def emit_refresh()`: puts `{"type": "refresh"}` into the job_manager log queue
     via `loop.call_soon_threadsafe` so it is safe to call from any thread
   - Used by job_manager at job completion, and by mutating API endpoints

2. `pipeline/gui/routers/events.py`:
   - `GET /api/events` — SSE endpoint (text/event-stream, no caching headers)
   - Drains `job_manager.get_log_queue()` indefinitely using `asyncio.Queue.get()`
     with a 15-second timeout to send keepalive comments (`: keepalive\n\n`)
   - Each item from the queue is dispatched by its `"type"` field:
       type="refresh"  → `event: refresh\ndata: {"type":"refresh"}\n\n`
       type="log"      → `event: log\ndata: {"level":…,"msg":…}\n\n`
       type="progress" → `event: progress\ndata: {"step":…,"total":…,"label":…}\n\n`
   - If the SSE connection drops (GeneratorExit / disconnect), exits cleanly
   - Fallback polling: specifications note that if SSE drops the frontend falls back
     to polling every 5 seconds — the endpoint itself needs no special logic for this

After implementing, verify:
- [ ] `GET /api/events` responds with Content-Type: text/event-stream
- [ ] A `emit_refresh()` call results in an `event: refresh` line appearing in the stream
- [ ] A progress dict pushed to the queue results in an `event: progress` line
- [ ] A log dict pushed to the queue results in an `event: log` line
- [ ] Keepalive comment is sent after 15 seconds of queue inactivity
- [ ] Disconnecting the client does not raise an unhandled exception on the server
```

---

## Step 6 — Pipelines API (`routers/pipelines.py`)

**What**: `GET /api/pipelines` — returns all pipeline metadata from the filesystem cache.

**Prompt**:

```
Implement `pipeline/gui/routers/pipelines.py` according to specifications § 4.2 and § 6.

Endpoint: `GET /api/pipelines`
Response schema (list of objects):
  [
    {
      "stem":        string,        // filename without extension
      "name":        string,        // from YAML `name`; fallback: stem
      "description": string | null, // from YAML `description`
      "valid":       boolean,       // false = YAML could not be parsed
      "error":       string | null  // parse error message if valid=false
    },
    ...
  ]

Requirements:
- Served from the in-memory cache (filesystem.get_pipelines()); no filesystem scan per request
- Returns 200 with an empty list if no pipelines are found (not 404)
- Invalid YAML pipelines are included in the list with valid=false and an error message,
  so the frontend can display an "invalid" badge with a tooltip

After implementing, verify:
- [ ] GET /api/pipelines returns 200 with Content-Type: application/json
- [ ] A valid pipeline YAML returns name and description correctly
- [ ] A malformed YAML appears in the list with valid=false and error set
- [ ] A pipeline with no `name` field returns stem as its name
- [ ] A pipeline with no `description` field returns null for description
- [ ] Response is served from cache (filesystem is not re-scanned on each request)
```

---

## Step 7 — Input Images API (`routers/images.py`)

**What**: List, thumbnail, full view, download, upload, and delete for source images.

**Prompt**:

```
Implement `pipeline/gui/routers/images.py` according to specifications § 4.1, § 4.5, and § 6.

Endpoints:
  GET  /api/input_images
  GET  /api/input_images/{name}/thumbnail
  GET  /api/input_images/{name}/full
  GET  /api/input_images/{name}/download
  POST /api/input_images/upload
  DELETE /api/input_images/{name}

`GET /api/input_images` response schema (list):
  [
    {
      "name":          string,   // filename with extension
      "width":         int,
      "height":        int,
      "size_bytes":    int,
      "format":        string,   // e.g. "JPEG", "PNG"
      "status":        "new" | "done" | "error" | "running",
      "done_count":    int,      // number of successful pipeline outputs
      "error_reason":  string | null  // only relevant if status="error"
    },
    ...
  ]

Status derivation (priority: running > error > done-count > new):
  - "running": image_name matches current running job
  - "error":   all pipelines that have been run ended in error, none successful
  - "done":    at least one pipeline successful (done_count > 0)
  - "new":     no pipeline has ever produced an output for this image

Thumbnail: JPEG, max 256 px on the longest side, in-memory (no caching)
Full/Download: serve file with appropriate Content-Disposition header

Upload (POST /api/input_images/upload):
  - Accepts multipart/form-data with one or more files
  - Accepted MIME types: image/jpeg, image/png, image/tiff
  - Silently overwrites existing files with the same name
  - On overwrite: deletes all output images matching `<stem>__*.png` from output-dir
  - Calls filesystem.invalidate("input_images") and filesystem.invalidate("output_images")
  - Calls notify.emit_refresh()
  - Returns 200 with list of uploaded filenames

Delete (DELETE /api/input_images/{name}):
  - Deletes source image from input-dir
  - Deletes all output images matching `<stem>__*` from output-dir
  - Calls filesystem.invalidate() for both sections
  - Calls notify.emit_refresh()
  - Returns 204

After implementing, verify:
- [ ] GET /api/input_images returns correct status for new/done/running/error images
- [ ] Status priority: running > error > done > new
- [ ] Thumbnail endpoint returns JPEG with max 256 px dimension
- [ ] Upload overwrites existing file and clears its output images
- [ ] Upload rejects non-image MIME types with 422
- [ ] Delete removes source image and all matching output images
- [ ] All mutating endpoints call notify.emit_refresh()
- [ ] All endpoints return JSON errors {"error": "..."} with appropriate status codes
```

---

## Step 8 — Output Images API (`routers/output_images.py`)

**What**: List, serve, thumbnail, and download for output artifacts.

**Prompt**:

```
Implement `pipeline/gui/routers/output_images.py` according to specifications § 4.2 and § 6.

Endpoints:
  GET /api/output_images
  GET /api/output_images/{name}
  GET /api/output_images/{name}/thumbnail
  GET /api/output_images/{name}/download

`GET /api/output_images` response schema (list):
  [
    {
      "name":          string,   // filename with extension
      "source_image":  string,   // source image name derived from filename convention
      "pipeline_stem": string,   // pipeline stem derived from filename convention
    },
    ...
  ]

Filename convention: `<image_stem>__<pipeline_stem>.png`
  → source_image = "<image_stem>.<original_extension>"
  → pipeline_stem = "<pipeline_stem>"

GET /api/output_images/{name}:   serve inline (Content-Disposition: inline)
GET /api/output_images/{name}/thumbnail: JPEG, max 256 px (in-memory, no caching)
GET /api/output_images/{name}/download: serve as attachment (Content-Disposition: attachment)

After implementing, verify:
- [ ] GET /api/output_images correctly parses source_image and pipeline_stem from filename
- [ ] Thumbnail returns JPEG max 256 px
- [ ] Inline endpoint sets Content-Disposition: inline
- [ ] Download endpoint sets Content-Disposition: attachment
- [ ] 404 returned for unknown output image names
```

---

## Step 9 — Jobs API (`routers/jobs.py`)

**What**: Start, cancel, and status endpoints for the single worker slot.

**Prompt**:

```
Implement `pipeline/gui/routers/jobs.py` according to specifications § 4.3 and § 6.

Endpoints:
  POST   /api/jobs
  DELETE /api/jobs/current
  GET    /api/jobs/current

POST /api/jobs request body:
  { "image_name": string, "pipeline_stem": string }

POST /api/jobs behaviour:
  - 409 if a job is already running (check job_manager.get_current_job())
  - 404 if image_name not found in filesystem cache
  - 404 if pipeline_stem not found in filesystem cache
  - 422 if the pipeline is marked valid=false
  - Resolves input_path from filesystem cache
  - Derives output_path as: output_dir / f"{image_stem}__{pipeline_stem}.png"
  - Schedules `asyncio.create_task(job_manager.run_job(...))` and returns 202 immediately
  - Response body: current job dict

DELETE /api/jobs/current:
  - Calls job_manager.request_cancel()
  - Returns 204 if a job was running; 404 otherwise

GET /api/jobs/current:
  - Returns current job dict or 204 if no job has been run yet
  - Response schema:
    {
      "image_name":           string,
      "pipeline_stem":        string,
      "pipeline_name":        string,
      "pipeline_description": string | null,
      "status":               "running" | "done" | "error",
      "error_reason":         string | null,
      "step_current":         int,
      "step_total":           int,
      "step_label":           string
    }

After implementing, verify:
- [ ] POST /api/jobs returns 409 when a job is already running
- [ ] POST /api/jobs returns 404 for unknown image or pipeline
- [ ] POST /api/jobs returns 422 for invalid (malformed YAML) pipeline
- [ ] POST /api/jobs returns 202 and job dict; job runs in background
- [ ] GET /api/jobs/current reflects step_current/step_total/step_label in real time
- [ ] DELETE /api/jobs/current returns 204 while running; 404 if nothing is running
- [ ] pipeline_name and pipeline_description are populated from PipelineRunner metadata
```

---

## Step 10 — Plotter API (`routers/plotter.py`)

**What**: `POST /api/plotter/send` — dispatches the plotter pipeline for a given output image.

**Prompt**:

```
Implement `pipeline/gui/routers/plotter.py` according to specifications § 4.4 and § 6.

Endpoint: POST /api/plotter/send
Request body: { "output_image_name": string }

Behaviour:
  - 409 if a job is already running
  - 404 if output_image_name not found in filesystem cache
  - Resolves the plotter pipeline: the first pipeline in filesystem.get_pipelines()
    whose stem equals "plotter" or "send_to_plotter" or "plotter_pipeline"
    (configurable via ServerConfig.plotter_pipeline_stem, default: "plotter")
  - 422 if no plotter pipeline is configured
  - Sets input for the job as the output image path (the stylised artifact)
  - Schedules job_manager.run_job(...) and returns 202

Add `plotter_pipeline_stem: str = "plotter"` to ServerConfig.

After implementing, verify:
- [ ] POST /api/plotter/send returns 409 when a job is already running
- [ ] POST /api/plotter/send returns 404 for unknown output image name
- [ ] POST /api/plotter/send returns 422 when no plotter pipeline is configured
- [ ] POST /api/plotter/send returns 202 and dispatches job_manager.run_job
- [ ] plotter_pipeline_stem is read from ServerConfig
```

---

## Step 11 — Frontend: CSS & Design Tokens (`static/style.css`)

**What**: All CSS — design tokens, reset, grid layout, components.

**Prompt**:

```
Implement `pipeline/gui/static/style.css` according to specifications § 5.4.

Requirements:
- CSS custom properties on :root (exact values from spec):
    --color-bg:         #1a1a1a
    --color-surface:    #242424
    --color-border:     #333333
    --color-accent:     #e8a020
    --color-text:       #e0e0e0
    --color-text-muted: #888888
    --color-success:    #4caf50
    --color-error:      #e53935
    --color-warning:    #fb8c00
    --radius:           6px
    --font-mono:        'JetBrains Mono', 'Fira Mono', monospace
    --font-ui:          system-ui, sans-serif
    --shadow:           0 2px 8px rgba(0,0,0,0.4)
- Dark theme by default; body background uses --color-bg
- CSS Grid thumbnail grid with auto-fill columns (min 180px)
- Status badge component: coloured dot + label, colours mapped to:
    new → --color-accent (blue not in spec; use accent or a dedicated --color-new: #1e88e5)
    done → --color-success
    error → --color-error
    running → --color-warning
- Log panel: fixed at bottom; two states (collapsed = header only, expanded = header + log area)
- Log line colours: DEBUG=--color-text-muted, INFO=--color-text, WARNING=--color-warning,
  ERROR/CRITICAL=--color-error
- Responsive: grid adapts; no horizontal scroll on mobile viewport

After implementing, verify:
- [ ] All 13 design tokens from the spec are present on :root with exact values
- [ ] Status badge dot colours match the spec table
- [ ] Log panel is visually fixed at the bottom
- [ ] Thumbnail grid uses CSS Grid with auto-fill
- [ ] No framework classes (no Bootstrap, no Tailwind utility classes)
```

---

## Step 12 — Frontend: SPA Core (`static/app.js`)

**What**: Central state object, `setState()`, `render()`, SSE client, and all view rendering.

**Prompt**:

```
Implement `pipeline/gui/static/app.js` according to specifications § 5.3 and the full
functional requirements (§ 4.1 – § 4.5).

Central state object (exact shape from spec):
  let state = {
      images:        [],       // from GET /api/input_images
      outputImages:  [],       // from GET /api/output_images
      pipelines:     [],       // from GET /api/pipelines
      currentJob:    null,     // from GET /api/jobs/current
      logs:          [],       // max 500 lines
      view:          'library',
      selectedImage: null,
  };

setState(patch): merges patch, calls render(state). Never mutate state directly.

render(state): single entry point for all DOM updates; idempotent.
  - view='library'  → render thumbnail grid (§ 4.1)
  - view='detail'   → render image detail with pipeline list (§ 4.2)

Image Library View (§ 4.1):
  - CSS Grid thumbnail grid, sorted alphabetically
  - Each card: thumbnail (GET /api/input_images/{name}/thumbnail), filename stem,
    status badge (new/done/error/running) with correct colours
  - Status badge priority: running > error > done count > new
  - Done badge shows "{n} done" count
  - Click card → setState({view:'detail', selectedImage: name})
  - Upload button: drag-and-drop zone + file picker, POST /api/input_images/upload,
    accepts jpeg/png/tiff, progress bar per file

Image Detail View (§ 4.2):
  - Left: full-resolution preview (constrained), filename, width×height, size, format
  - Right: pipeline list — for each pipeline from state.pipelines:
      - Name (pipeline.name) as title
      - Description (pipeline.description) as subtitle if present
      - Status badge (derived from state.outputImages + state.currentJob)
      - If done: output thumbnail, hover shows path, click opens lightbox, Download button
      - If not_run or error: Run button (disabled if any job is running)
      - If error: error reason below badge
  - Back button → setState({view:'library', selectedImage: null})
  - Delete button: confirmation prompt "Delete image and all N pipeline results?",
    DELETE /api/input_images/{name}

Log Panel (§ 4.3) — always rendered, fixed at bottom:
  Collapsed (default after completion): header only
    - Status icon: ⟳ Running | ✓ Done | ✗ Error
    - source image name | pipeline name
    - Cancel button (only if status=running)
    - Expand button
  Expanded: header + log area
    - Log lines colour-coded by level
    - Max 500 lines (drop from top)
    - Auto-scroll to bottom while running; stop if user scrolls up
  Hidden if state.currentJob is null.

SSE client:
  - Connect to GET /api/events on page load
  - event:refresh  → fetch /api/input_images, /api/output_images, /api/jobs/current,
                     then setState(...)
  - event:log      → setState({logs: [...state.logs.slice(-499), newLine]})
  - event:progress → update state.currentJob step fields inline, re-render log panel header
  - On disconnect: fall back to setInterval polling every 5 seconds

Lightbox overlay:
  - Full-resolution output image centred on dark overlay
  - Click overlay or press Escape to close

After implementing, verify:
- [ ] Image library renders a grid sorted alphabetically
- [ ] Status badges show correct colour and label for all 4 states (new/done/error/running)
- [ ] Running status badge appears while a job is active
- [ ] Clicking a card opens detail view; back button returns to library
- [ ] Pipeline list shows name and description from pipeline.name / pipeline.description
- [ ] Run button triggers POST /api/jobs; is disabled while a job is running
- [ ] Log panel appears fixed at bottom when a job exists; hidden otherwise
- [ ] Log panel header shows pipeline name from currentJob.pipeline_name
- [ ] Step progress shows "Step n/m: label" updated via progress SSE events
- [ ] Log lines are colour-coded by level
- [ ] Auto-scroll stops when user scrolls up; resumes when job completes
- [ ] Cancel button calls DELETE /api/jobs/current
- [ ] Upload drag-and-drop works; progress bar shown per file
- [ ] Delete confirmation shows count of pipeline results
- [ ] Lightbox opens on output thumbnail click; closes on overlay click or Escape
- [ ] SSE fallback polling activates on disconnect
- [ ] state is never mutated directly (only via setState)
- [ ] render(state) is idempotent (calling twice produces the same DOM)
```

---

## Step 13 — Integration & Smoke Test

**What**: Wire everything together in `server.py`, call `filesystem.init_cache()` and
`job_manager.init()` on startup, register all routers, and do an end-to-end manual test.

**Prompt**:

```
Wire all components together in `pipeline/gui/server.py` and perform an end-to-end
smoke test.

server.py startup sequence:
  1. Parse CLI args → ServerConfig
  2. Create input-dir, tools-dir, output-dir if missing (log warning each)
  3. Call filesystem.init_cache(cfg)
  4. Call job_manager.init(asyncio.get_event_loop())
  5. Create FastAPI app, register all 6 routers with appropriate prefixes
  6. Mount /static, serve index.html at /
  7. Start Uvicorn

Smoke test checklist (run manually with a real YAML pipeline config):
  - [ ] Server starts without error: `.venv/bin/pipeline-server`
  - [ ] GET /api/pipelines returns at least one pipeline with correct name/description
  - [ ] GET /api/input_images returns all images in input/
  - [ ] GET /api/output_images returns all artifacts in output/
  - [ ] GET /api/input_images/{name}/thumbnail returns a JPEG ≤ 256 px
  - [ ] POST /api/jobs starts a real pipeline job; GET /api/jobs/current shows running
  - [ ] SSE /api/events stream receives log, progress, and refresh events during the job
  - [ ] After job completion: GET /api/output_images lists the new artifact
  - [ ] DELETE /api/jobs/current cancels a running job; output image is deleted
  - [ ] POST /api/input_images/upload adds an image; GET /api/input_images reflects it
  - [ ] DELETE /api/input_images/{name} removes image and all its output artifacts
  - [ ] Browser: library view renders thumbnails with correct status badges
  - [ ] Browser: detail view shows pipeline name, description, and Run button
  - [ ] Browser: log panel shows pipeline name and Step n/m: label during execution
  - [ ] Browser: progress updates in real time as steps complete
  - [ ] Browser: SSE reconnect / polling fallback works after killing and restarting server
```

---

## Final Completeness Check

**Prompt**:

```
Perform a full completeness review of the Plotter Pipeline Manager GUI against
`pipeline/gui/specifications.md`. For each requirement, confirm it is implemented
or explicitly note what is missing.

Check the following areas in order:

§ 4.1 Image Library View
  - [ ] Thumbnail grid with CSS Grid auto-fill
  - [ ] Correct status badge for all 4 states with correct priority
  - [ ] Done badge shows "{n} done" count
  - [ ] Alphabetical sort
  - [ ] Upload button with drag-and-drop, file picker, progress bar
  - [ ] JPEG/PNG/TIFF accepted; other types rejected

§ 4.2 Image Detail View
  - [ ] Left column: preview, filename, width×height, size, format
  - [ ] Right column: pipeline.name as title, pipeline.description as subtitle
  - [ ] Status badge per pipeline
  - [ ] Done state: output thumbnail, hover path, lightbox, Download button
  - [ ] Not run/error state: Run button (disabled while any job running)
  - [ ] Error state: error reason shown
  - [ ] Back button
  - [ ] Delete button with confirmation showing artifact count

§ 4.3 Job Execution
  - [ ] Single worker slot (asyncio.Lock)
  - [ ] Silent overwrite of previous artifact on re-run
  - [ ] Log panel fixed at bottom with two states (collapsed/expanded)
  - [ ] Collapsed: status icon, source image name, pipeline name, cancel, expand
  - [ ] Expanded: header + scrollable log area (500-line cap, drop from top)
  - [ ] Log line colour-coding (DEBUG/INFO/WARNING/ERROR/CRITICAL)
  - [ ] Auto-scroll while running; stops on manual scroll up
  - [ ] Cancel: sets threading.Event; deletes output image; status → error
  - [ ] Log panel persists after completion; never auto-dismissed
  - [ ] Step progress: "Step n/m: label" in panel header, updated via SSE progress events
  - [ ] Pipeline name and description displayed in log panel

§ 4.4 Send to Plotter
  - [ ] Send to Plotter button on done artifact
  - [ ] POST /api/plotter/send dispatches plotter pipeline
  - [ ] Subject to single-worker constraint
  - [ ] Error shown in log panel if plotter pipeline fails

§ 4.5 Image Upload & Deletion
  - [ ] Overwrite: deletes all output images for that source image
  - [ ] Upload progress bar per file
  - [ ] Delete: confirmation prompt with artifact count
  - [ ] Delete: removes source + all matching output images
  - [ ] Grid refreshes after upload/delete

§ 4.6 SSE Events
  - [ ] Single /api/events stream with event: field for type discrimination
  - [ ] refresh event triggers full data re-fetch
  - [ ] log event appended directly to log panel (no re-fetch)
  - [ ] progress event updates step display directly (no re-fetch)
  - [ ] Keepalive comment every 15 s
  - [ ] Frontend fallback polling every 5 s on disconnect

§ 5.1 Architecture
  - [ ] Backend: FastAPI + Uvicorn
  - [ ] API layer (routers/) contains no business logic
  - [ ] Core layer (job_manager, filesystem, log_handler) contains no FastAPI imports
  - [ ] Frontend: plain HTML + CSS + vanilla JS, no build toolchain
  - [ ] Pipeline executed in thread via run_in_executor
  - [ ] PipelineRunner.from_yaml() used for instantiation
  - [ ] on_progress callback wired to SSE progress events
  - [ ] No upward dependency: gui/ never imported by core pipeline modules

§ 5.2 Concurrency
  - [ ] asyncio.Lock enforces single worker
  - [ ] QueueLogHandler uses loop.call_soon_threadsafe
  - [ ] Cache mutations only inside event loop
  - [ ] Shutdown: server waits max 10 s for worker thread
  - [ ] Thumbnails generated on-the-fly (no caching)

§ 5.3 Frontend State Model
  - [ ] Single state object with exact shape from spec
  - [ ] setState() is only mutation entry point
  - [ ] render(state) is idempotent

§ 5.4 Styling
  - [ ] All 13 design tokens present with exact values
  - [ ] Dark theme by default
  - [ ] Responsive grid

§ 5.5 Configuration
  - [ ] All 6 CLI arguments with correct defaults
  - [ ] `pipeline-server` entry point registered in `pyproject.toml` and callable via `.venv/bin/pipeline-server`
  - [ ] Pipeline discovery: scans tools-dir for *.yaml / *.yml

§ 5.6 Error Handling
  - [ ] Missing dirs created on startup with warning
  - [ ] Malformed YAML shown as invalid badge with tooltip
  - [ ] Pipeline runtime errors caught and shown in log panel
  - [ ] All HTTP errors return {"error": "..."} JSON

§ 6 REST API
  - [ ] All 17 endpoints from the API table are implemented
  - [ ] Correct HTTP methods and paths
  - [ ] Correct status codes (200/202/204/404/409/422)

§ 7 File Structure
  - [ ] All files from the directory tree in § 7 exist
  - [ ] No extra files outside the specified structure

For any item marked missing: provide the exact file and function/line that needs to
be added or changed.
```
