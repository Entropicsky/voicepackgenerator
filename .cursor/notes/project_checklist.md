# Project Checklist - Unified AI Voice Generation & Ranking App v1 (Dockerized)

## Phase 0: Docker Setup & Foundation (Milestone: `docker-compose up` runs successfully)

- [x] Create `backend/Dockerfile`
- [x] Create `frontend/Dockerfile`
- [x] Create `docker-compose.yml` at project root
- [x] Update `.env` file with correct Redis hostname (`redis://redis:6379/0`)
- [x] Simplify `Makefile` (remove dev, adjust install/test targets)
- [x] **Testing:** Build initial frontend project structure using Vite
- [x] Create minimal placeholder files:
    - [x] `backend/app.py`
    - [x] `backend/celery_app.py`
    - [x] `tasks.py` (Moved to root)
- [x] **Checkpoint Test:** Run `docker-compose up --build`. Services start. Basic connectivity verified.

## Phase 1: Backend - Core Utils & Config (Milestone: Core helpers testable via Docker)

- [ ] Implement Flask/Celery configuration loading (`backend/config.py`) (Deferred)
- [x] Implement basic Flask app structure (`backend/app.py`)
- [x] Implement Celery app factory/instance (`celery_app.py` at root)
- [x] Implement Filesystem Helpers (`backend/utils_fs.py`)
- [x] Implement ElevenLabs API Helper (`backend/utils_elevenlabs.py`)
- [ ] **Testing:** Write unit tests for `utils_fs.py` (mocking `os`). (Deferred - Pytest issues)
- [ ] **Testing:** Write unit tests for `utils_elevenlabs.py` (mocking `requests`). (Deferred - Pytest issues)
- [ ] **Testing:** Run tests inside container: `docker-compose exec backend pytest` (Deferred - Pytest issues)

## Phase 2: Backend - Generation API & Task (Milestone: Generation triggers & monitors via Docker)

- [x] Define Celery generation task (`tasks.py:run_generation` at root)
    - [x] Refactor logic from original `generate_tts.py`
    - [x] Accept dynamic config
    - [x] Call `utils_elevenlabs.py`
    - [x] Implement file saving to `/app/output/takes/` structure inside container
    - [x] Implement final `metadata.json` generation (matching spec §3)
    - [x] Implement task state updates (`self.update_state`)
    - [x] Add detailed logging within the task
- [x] Implement Flask API endpoint: `GET /api/voices`
- [x] Implement Flask API endpoint: `POST /api/generate` (enqueues task)
- [x] Implement Flask API endpoint: `GET /api/generate/{task_id}/status` (queries Redis)
- [ ] **Testing:** Write unit tests for `tasks.py:run_generation` (mocking utils, filesystem, Celery state). (Deferred - Pytest issues)
- [ ] **Testing:** Write integration tests for generation API endpoints (`test_api_generation.py`, mock Celery/ElevenLabs). (Deferred - Pytest issues)
- [ ] **Testing:** Run tests inside container: `docker-compose exec backend pytest` (Deferred - Pytest issues)
- [x] **Checkpoint Test:** Manually trigger generation via API call. Verified task runs, status polled, output files/metadata created correctly.

## Phase 3: Backend - Ranking API (Milestone: Ranking works via API in Docker)

- [x] Implement Flask API endpoint: `GET /api/batches` (using `utils_fs.find_batches`)
- [x] Implement Flask API endpoint: `GET /api/batch/{batch_id}` (using `utils_fs.load_metadata`)
- [x] Implement Flask API endpoint: `PATCH /api/batch/{batch_id}/take/{filename}` (using `utils_fs`)
- [x] Implement Flask API endpoint: `POST /api/batch/{batch_id}/lock` (using `utils_fs`)
- [x] Implement Flask API endpoint: `GET /audio/<path:relpath>` (using `send_file`)
- [x] Ensure ranking endpoints handle `LOCKED` state correctly (423 response).
- [ ] **Testing:** Write integration tests for ranking API endpoints (`test_api_ranking.py`, using `pyfakefs` or mocking `utils_fs`). (Deferred - Pytest issues)
- [ ] **Testing:** Run tests inside container: `docker-compose exec backend pytest` (Deferred - Pytest issues)
- [x] **Checkpoint Test:** Manually test ranking API endpoints (curl to `http://localhost:5000`) using pre-prepared batch data in `./output`. Verified metadata updates and symlink creation/deletion. Verified locking. Verified audio streaming.

## Phase 4: Frontend - Setup & Shared Components (Milestone: Basic app structure renders via Docker)

- [x] Ensure frontend project created in Phase 0 is correctly configured (Vite, TS, React).
- [x] Set up React Router (`frontend/src/App.tsx`)
- [x] Define main page components (`GenerationPage`, `BatchListPage`, `RankingPage`)
- [x] Implement API wrapper functions (`frontend/src/api.ts`)
- [x] Define shared TypeScript types (`frontend/src/types.ts`)
- [ ] Implement basic shared components (`Button`, `Modal`, etc.) # Deferred
- [x] Verify Vite proxy to Flask backend works (`frontend/vite.config.ts`)
- [ ] **Testing:** Set up Vitest/React Testing Library. (Deferred)
- [ ] **Testing:** Run tests inside container: `docker-compose exec frontend npm run test` (Deferred)
- [x] **Checkpoint Test:** Run `docker-compose up`, navigate between placeholder pages (`http://localhost:5173`). Verified basic loading.

## Phase 5: Frontend - Generation UI (Milestone: User can configure & start generation via UI)

- [x] Implement `VoiceSelector` component (fetches voices from API).
- [x] Implement `GenerationForm` component (inputs, validation, CSV upload).
- [x] Implement `TaskMonitor` component (polling status API using `usePolling` hook).
- [x] Connect components in `GenerationPage.tsx`.
- [x] Implement logic to call `POST /api/generate` on form submission.
- [x] Display task status updates in `TaskMonitor`.
- [ ] **Testing:** Write component tests for `VoiceSelector`, `GenerationForm`, `TaskMonitor` (mocking API calls). (Deferred)
- [ ] **Testing:** Run tests inside container: `docker-compose exec frontend npm run test` (Deferred)
- [x] **Checkpoint Test:** Used the UI to configure and start a generation job. Monitored its progress. Verified task completes successfully and output folder created.

## Phase 6: Frontend - Ranking UI (Milestone: User can rank takes via UI)

- [ ] Implement `BatchListPage` (fetches and displays batches).
- [ ] Implement `RankingContext` (`frontend/src/contexts/`).
- [ ] Implement `RankingPage` (fetches batch data, sets up context).
- [ ] Implement `LineList` component (virtualized).
- [ ] Implement `TakeRow` component (playback button, waveform).
- [ ] Implement `AudioPlayer` component (Web Audio API).
- [ ] Implement `RankSlots` component (DnD, hotkeys, rank update logic).
- [ ] Implement debounced PATCH call in `RankingContext.updateRank`.
- [ ] Implement "Lock Batch" button and confirmation modal.
- [ ] Implement read-only state for locked batches.
- [ ] **Testing:** Write component tests for ranking components (mocking context/API). (Deferred)
- [ ] **Testing:** Write integration tests for the ranking page flow. (Deferred)
- [ ] **Testing:** Run tests inside container: `docker-compose exec frontend npm run test` (Deferred)
- [ ] **Checkpoint Test:** Navigate from batch list to a completed batch (`http://localhost:5173`). Rank several takes. Verify UI updates, `metadata.json` changes, and `ranked/` symlinks are correct in `./output`. Lock the batch and verify UI becomes read-only.