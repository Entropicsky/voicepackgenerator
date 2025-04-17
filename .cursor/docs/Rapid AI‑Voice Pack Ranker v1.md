# Rapid AI‑Voice Pack Ranker v1  **0\. Definitions used in this document**

| Term | Meaning |
| ----- | ----- |
| **ROOT** | Absolute path to the voice‑asset tree. In development this is `./output`. It is injected into the Flask app via env var `AUDIO_ROOT`. |
| **skin**, **voice**, **batch** | Pure directory names already produced by the existing generation script. |
| **take‑file** | An MP3 stored under `<batch>/takes/…`. E.g. `Intro_1_take_3.mp3`. |
| **rank** | Integer **1 – 5** or `null` (un‑ranked). |
| **symlink** | A POSIX soft link pointing from `<batch>/ranked/<rank‑folder>/…` to the original take file. |
| **LOCKED sentinel** | Empty file named `LOCKED` in the batch root that freezes further edits. |

---

## **1\. Directory‑tree contract (v1)**

```
<ROOT>/<SkinName>/<VoiceName‑VoiceID>/<BatchID>/
│
├── takes/                #   **ALWAYS real MP3s; never symlinks**
│   └── Intro_1_take_3.mp3
│
├── ranked/               #   **ONLY symlinks**, one extra level per rank
│   ├── 01/
│   │   └── Intro_1_take_3.mp3 -> ../../takes/Intro_1_take_3.mp3
│   ├── 02/
│   ├── 03/
│   ├── 04/
│   └── 05/
│
├── metadata.json         #   authoritative truth, see §2
└── (optional) LOCKED     #   presence = batch read‑only
```

**NEVER rename or move the source MP3s.** All user actions affect only  
 `metadata.json` and the symlink tree.

---

## **2\. `metadata.json` schema (v1)**

```
{
  "batch_id": "20250417-000837",
  "ranked_at_utc": null,           // filled when batch locked
  "takes": [
    {
      "file": "Intro_1_take_3.mp3",
      "line": "Intro_1",
      "rank": null,                // 1‑5 or null
      "ranked_at": null            // ISO‑8601 UTC, set when rank != null
    },
    ...
  ]
}
```

*The existing generation script already creates `file` and `line`.*  
 *New code only appends `rank` and `ranked_at`, plus top‑level `ranked_at_utc` when the batch is locked.*

---

## **3\. Back‑end (Flask \+ SQLAlchemy not required)**

### **3.1 Folder layout**

```
backend/
│   app.py
│   tasks.py           # Celery worker stub; generation hook, optional
│   utils_fs.py
│   requirements.txt   # see §8
└── ...
```

### **3.2 Environment variables required**

```
AUDIO_ROOT=./output
FLASK_ENV=development
SECRET_KEY=any‑string  # used only for Flask sessions
```

### **3.3 HTTP API – exact contract**

| Verb | Path | Body / Query | Response | Side‑effects |
| ----- | ----- | ----- | ----- | ----- |
| GET | `/api/batches` | none | JSON list of `{skin, voice, batch_id}` found under **ROOT**. | none |
| GET | `/api/batch/<batch_id>` | none | Entire `metadata.json` (200) or `404`. | none |
| PATCH | `/api/batch/<batch_id>/take/<filename>` | `{"rank": 3}` | `200 {ok:true}` on success; `400` if invalid rank; `423` if locked. | • Updates in‑memory JSON then writes back to disk • Re‑creates symlink tree for the affected batch atomically. |
| POST | `/api/batch/<batch_id>/lock` | none | `200 {locked:true}` | • Writes `LOCKED` file • Fills `ranked_at_utc` in JSON |
| POST | `/api/generate` | JSON payload identical to current config file. | `202 {task_id:"…"}` | *Optional*: enqueues Celery job that runs existing generator. |

### **3.4 Audio streaming**

Route `/audio/<path:relpath>` uses `send_file` **with** `conditional=True` so the browser can issue Range requests (scrubbing).  
 `relpath` begins after **ROOT**. Example:  
 `/audio/JingWeiDragonHeart/JingWeiDragonHeart-1-…/20250417-000837/takes/Intro_1_take_3.mp3`

### **3.5 File‑system helpers (`utils_fs.py`)**

```py
def load_metadata(batch_dir) -> dict: ...
def save_metadata(batch_dir, data) -> None: ...
def rebuild_symlinks(batch_dir) -> None:  # clears ranked/, recreates tree
def is_locked(batch_dir) -> bool: ...
```

All PATCH/POST endpoints *must* use these helpers; never duplicate code.

---

## **4\. Front‑end (React \+ TypeScript)**

### **4.1 Folder layout**

```
frontend/
│   vite.config.ts
│   index.html
└── src/
    │   main.tsx
    ├── api.ts         # fetch wrappers
    ├── pages/
    │    └── Batch.tsx
    └── components/
         ├── LineList.tsx
         ├── TakeRow.tsx
         ├── RankSlots.tsx
         └── AudioPlayer.tsx
```

### **4.2 State model (React context)**

```
interface Take { file: string; rank: number|null; line: string; }
interface BatchCtx {
  batchId: string;
  takesByLine: Record<string, Take[]>;
  updateRank(takeFile: string, newRank: number|null): void;
}
```

### **4.3 Major components & UX behaviour**

| Component | Library helpers | Must do |
| ----- | ----- | ----- |
| **LineList** | `react-window` | Virtualised list; arrow‑keys navigate; shows count of takes still un‑ranked. |
| **TakeRow** | vanilla | Play/pause button → `AudioPlayer`; shows waveform via `wavesurfer.js`. |
| **RankSlots** | `react-beautiful-dnd` | Six horizontal “slots”: 01‑05 \+ “Other”. Dragging a row into a slot updates rank logic below. Also numeric hotkeys 1‑5. |
| **AudioPlayer** | Web Audio API | Pre‑decode file, cache ±2 siblings. |

#### **Rank‑update logic (client side)**

```
If user drops T into slot N:
    • Find (if any) take currently at rank N → bump to N+1
    • Cascade downward until a slot frees or N == 5
    • Any take pushed past 5 → rank = null
    • Call context.updateRank(file, new_rank)
```

`updateRank()` debounces (300 ms) and then sends a PATCH call.

### **4.4 Service‑worker (Vite PWA plugin)**

* Cache strategy: “stale‑while‑revalidate” for **/audio/** responses,  
   maximum of **50 files** or **80 MB**, whichever comes first.

---

## **5\. Batch locking UX**

* Lock button in Batch header.

* Confirmation modal: “Locking finalises the batch and prevents further edits.”

* After success, UI switches to read‑only; RankSlots disabled; big “LOCKED” badge at top.

---

## **6\. Async generation (optional but scaffold now)**

* `tasks.py` defines Celery app and `generate_batch(config_json)` that calls the existing generator script via `subprocess.run`.

* `/api/generate` enqueues and immediately returns task\_id.

* Front‑end polls `/api/generate/<task_id>/status` (simple Flask route reading Redis result) to show progress. **Do not** implement fancy progress parsing—just `pending / started / finished`.

---

## **7\. Unit tests (PyTest)**

* `tests/test_symlink_builder.py` – feed fake metadata, assert ranked/ tree correct.

* `tests/test_rank_patch_endpoint.py` – POST, then load JSON to confirm `rank` fields and symlinks updated.

* `tests/test_locked_batch.py` – ensure PATCH returns **423 Locked**.

---

## **8\. Exact dependency versions**

```
# backend/requirements.txt
Flask==3.0.0
flask-cors==4.0.0
Celery==5.3.1            # optional
redis==5.0.3             # if Celery used
python-dotenv==1.0.1

# frontend/package.json (extract)
{
  "dependencies": {
    "react": "18.3.0",
    "react-dom": "18.3.0",
    "react-window": "1.8.7",
    "react-beautiful-dnd": "13.1.1",
    "wavesurfer.js": "7.8.4"
  },
  "devDependencies": {
    "vite": "5.0.0",
    "@vitejs/plugin-react": "4.0.0",
    "typescript": "5.4.0"
  }
}
```

---

## **9\. Build & run script (Makefile excerpt)**

```
.PHONY: backend frontend dev

backend:
	pip install -r backend/requirements.txt

frontend:
	cd frontend && npm install

dev: backend frontend
	# Run Flask API
	AUDIO_ROOT=$(PWD)/output FLASK_APP=backend/app.py flask run &
	# Run React dev server
	cd frontend && npm run dev
```

---

## **10\. Minimal “getting‑started” commands for the developer**

```
git clone <repo>
make dev
# open http://localhost:3000  (React)
# Flask API proxied at /api and /audio
```

---

### **Deliverable check‑list**

1. **Flask app** fulfilling the exact endpoints in §3.3.

2. **React SPA** with components & behaviour in §4.

3. **Symlink \+ metadata logic** per §2 & §3.5.

4. **Unit tests** §7 all pass: `pytest -q`.

5. **README.md** summarising the Makefile commands and env vars.

No feature not named here should be coded; any ambiguity defaults to the behaviour stated above.

---

**This is the entire, self‑contained tech spec.**

