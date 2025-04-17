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

- [x] Implement Flask API endpoint: `GET /api/batches`
- [x] Implement Flask API endpoint: `GET /api/batch/{batch_id}`
- [x] Implement Flask API endpoint: `PATCH /api/batch/{batch_id}/take/{filename}`
- [x] Implement Flask API endpoint: `POST /api/batch/{batch_id}/lock`
- [x] Implement Flask API endpoint: `GET /audio/<path:relpath>`
- [x] Ensure ranking endpoints handle `LOCKED` state correctly (423 response).
- [ ] **Testing:** Integration tests for ranking API (Deferred)
- [ ] **Testing:** Run backend tests (Deferred)
- [x] **Checkpoint Test:** Manually tested ranking API endpoints.

## Phase 4: Frontend - Setup & Shared Components (Milestone: Basic app structure renders via Docker)

- [x] Ensure frontend project created
- [x] Set up React Router
- [x] Define main page components
- [x] Implement API wrapper functions
- [x] Define shared TypeScript types
- [ ] Implement basic shared components (Deferred)
- [x] Verify Vite proxy
- [ ] **Testing:** Set up Vitest/React Testing Library (Deferred)
- [ ] **Testing:** Run frontend tests (Deferred)
- [x] **Checkpoint Test:** Verified basic loading & navigation.

## Phase 5: Frontend - Generation UI (Milestone: User can configure & start generation via UI)

- [x] Implement `VoiceSelector` (with V2 API, filtering/sorting)
- [x] Implement `GenerationForm`
- [x] Remove `TaskMonitor` component.
- [x] Connect components in `GenerationPage`
- [x] Implement form submission logic (calls API, navigates to Jobs page)
- [ ] **Testing:** Component tests for Generation UI (Deferred)
- [ ] **Testing:** Run frontend tests (Deferred)
- [x] **Checkpoint Test:** Verified generation submission.

## Phase 6: Frontend - Ranking UI (Milestone: User can rank takes via UI)

- [ ] Implement `JobsPage` (replaces BatchListPage, fetches /api/jobs). (Done in Phase 7)
- [x] Implement `RankingContext` (line-scoped state, fetch, update, cascade).
- [x] Implement `RankingPage` (uses context, 3-panel layout).
- [x] Implement `LineNavigation` component.
- [x] Implement `CurrentLineTakes` component.
- [x] Implement `TakeRow` component (playback, rank buttons).
- [x] Implement `CurrentLineRankedPanel` component.
- [x] Implement debounced PATCH call in `RankingContext`.
- [x] Implement "Lock Batch" button and logic.
- [x] Implement read-only state for locked batches.
- [ ] Implement `AudioPlayer` component (Deferred)
- [ ] Implement List Virtualization (Deferred)
- [ ] Implement Waveform display (Deferred)
- [ ] Implement Ranking Hotkeys (Deferred)
- [ ] **Testing:** Component tests for Ranking UI (Deferred).
- [ ] **Testing:** Integration tests for ranking flow (Deferred).
- [ ] **Testing:** Run frontend tests (Deferred)
- [x] **Checkpoint Test:** Manually tested line-scoped ranking, side panel.

## Phase 7: Job Tracking, STS & Refinement (Milestone: Core flows stable)

### Phase 7a: Job Tracking Implementation (Complete)
- [x] Backend: Add SQLAlchemy dependency.
- [x] Backend: Define `GenerationJob` model (`models.py`).
- [x] Backend: Initialize DB on app startup.
- [x] Backend: Modify `POST /api/generate` to use DB.
- [x] Backend: Modify `tasks.run_generation` to use DB.
- [x] Backend: Create `GET /api/jobs` endpoint.
- [x] Frontend: Update `types.ts`.
- [x] Frontend: Update `api.ts`.
- [x] Frontend: Implement `JobsPage.tsx`.
- [x] Frontend: Modify `GenerationPage.tsx`.
- [x] Frontend: Update `App.tsx` router/links.
- [x] Checkpoint Test: Verified job submission, DB persistence, status updates, UI display.

### Phase 7b: Speech-to-Speech (Line Level)
- [ ] Backend: Update `GenerationJob` model (Confirm fields sufficient - Done in 7a).
- [ ] Backend: Enhance `utils_elevenlabs.get_available_models` (add STS filter).
- [ ] Backend: Implement `utils_elevenlabs.run_speech_to_speech_conversion`.
- [ ] Backend: Add `GET /api/models` capability filter.
- [ ] Backend: Implement `POST /api/batch/<batch_id>/speech_to_speech` endpoint.
- [ ] Backend: Implement `tasks.run_speech_to_speech_line` Celery task.
- [ ] Frontend: Update `types.ts` (Add `SpeechToSpeechPayload`, update `ModelOption`?).
- [ ] Frontend: Update `api.ts` (Add `getModels` capability param, add `startSpeechToSpeech`).
- [ ] Frontend: Create `SpeechToSpeechModal.tsx` component (with file input).
- [ ] Frontend: Add "Speech-to-Speech..." button to `CurrentLineTakes.tsx`.
- [ ] Frontend: Integrate `SpeechToSpeechModal` into `RankingPage.tsx`.
- [ ] Checkpoint Test: Manually test STS flow (upload audio file, check job status, verify output & metadata update).

### Phase 7c: Final Testing & Refinement
- [ ] Perform comprehensive manual testing of all flows (Generation, Ranking, Line Regen, STS).
- [ ] Review and enhance logging.
- [ ] Address any bugs found.
- [ ] Refine UI/UX.
- [ ] **Testing:** Revisit backend/frontend testing issues (Optional / Future).
- [ ] **Documentation:** Update README.
- [ ] **Documentation:** Ensure code comments/docstrings are adequate.

## Phase 8: Build & Deployment Prep (Milestone: Ready for deployment)

- [ ] Create production build of frontend (`docker-compose exec frontend npm run build`).
- [ ] Adapt backend Dockerfile/entrypoint for production (use Gunicorn/Waitress instead of Flask dev server).
- [ ] Adapt frontend service for production (use Nginx or similar to serve static files).
- [ ] Finalize production logging configuration.
- [ ] Document deployment steps using Docker Compose (or alternative orchestration).
- [ ] **Checkpoint Test:** Test the production-like setup locally.
- [ ] **Self-Review:** Review code against project standards. Document any necessary future refactoring.

## Continuous Tasks

- [x] Update `.cursor/notes/agentnotes.md` and `notebook.md`.
- [x] Commit changes frequently using conventional commit messages.
- [ ] Run tests frequently via `docker-compose exec` (when tests are working).