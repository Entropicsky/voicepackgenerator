# Agent Notes

## Project Overview

This project involves generating voice packs using ElevenLabs and providing a unified web interface (Flask backend, React frontend) for game designers to both initiate AI voice generation and subsequently rank the generated audio takes efficiently for potential use in games. Ranking is performed *within* each line.

Generation is asynchronous, using Celery and Redis.
Ranking relies primarily on filesystem interactions (`metadata.json`, symlinks) as defined in the tech spec.

**Development Environment:** Managed via Docker Compose.

## Key Files/Folders

- `docker-compose.yml`: Defines services (backend, worker, frontend, redis).
- `celery_app.py`: Celery application factory/instance (at root).
- `tasks.py`: Celery task definitions (at root, includes `run_generation`).
- `backend/`: Flask application source code.
  - `app.py`: Main Flask app, API endpoints (generation + ranking + audio).
  - `utils_fs.py`: Filesystem helpers for ranking.
  - `utils_elevenlabs.py`: ElevenLabs API interaction helper.
  - `Dockerfile`: Docker build instructions for backend/worker.
  - `requirements.txt`: Python dependencies.
  - `tests/`: Pytest tests (currently deferred due to environment issues).
- `frontend/`: React application source code.
  - `Dockerfile`: Docker build instructions for frontend.
  - `package.json`: Node dependencies.
  - `vite.config.ts`: Vite configuration (including proxy).
  - `src/`: React components, pages, contexts, hooks.
      - `pages/GenerationPage.tsx`: UI for starting generation.
      - `pages/BatchListPage.tsx`: UI for listing batches.
      - `pages/RankingPage.tsx`: UI container for ranking a batch.
      - `contexts/RankingContext.tsx`: State management for ranking.
      - `components/`: UI components.
- `.cursor/`: Agent notes, docs, rules, tools.
  - `docs/Unified AI Voice Generation & Ranking App v1.md`: Tech spec.
  - `notes/project_checklist.md`: Project plan.
- `.env`: Contains API keys and environment settings.
- `output/`: Root directory for generated audio files (mounted into containers).
- `input/`: (Potentially needed for CSVs if not uploaded via UI).

## User Preferences

- Follow custom instructions (planning, documentation, testing, code structure).
- Use Docker Compose for development environment.
- Use `.cursor` folder for documentation and notes.
- Ranking should be scoped per-line.
- Ranking UI should have 3 panels (Lines Nav, Takes for Line, Ranked Takes for Line).
- Communicate via Slack DM to Stewart Chisam (U03DTH4NY).

## Approach Guidance

- Refactored to use Docker Compose for simpler setup/deployment.
- Implement frontend ranking UI with 3-panel layout.
- Implement line-scoped ranking logic in `RankingContext`.
- **New Feature:** Implement line-level Speech-to-Speech (STS) generation using file upload.
- Defer fixing Pytest environment issues (e.g., `mocker` fixture) until core functionality is complete.

## Current State / Next Steps

- Core backend (generation + ranking API) implemented and manually verified.
- Basic frontend structure with routing and API wrappers implemented.
- Generation UI implemented and tested.
- Ranking UI structure implemented (3 panels), line-scoped ranking logic added.
- **Current:** Implementing line-level Speech-to-Speech feature (Phase 7b).
- Next: Final testing & refinement, address deferred testing issues.

## GitHub Repo

- https://github.com/Entropicsky/voicepackgenerator 

## Voice Design Feature (Implemented 2024-07-29)

- Added a new page `/voice-design` for creating voices using ElevenLabs Voice Design API.
- Implemented backend endpoints (`/api/voice-design/previews`, `/api/voice-design/save`) and corresponding utility functions (`utils_elevenlabs.py`).
- Frontend UI allows users to:
    - Enter voice description and preview text/settings.
    - Generate multiple batches of previews.
    - "Hold" promising previews across batches.
    - Save specific "Held" previews with a custom name via a modal.
- Integrated a `VoiceContext` to manage the global list of voices (`api.getVoices`).
- Refactored `VoiceSelector` component to use `VoiceContext`.
- Saving a new voice from the Voice Design page now triggers `refetchVoices` via the context, updating the `VoiceSelector` dynamically.
- Addressed initial layout issues with `AppShell.Main` and flexbox columns.
- Updated sidebar navigation order.

**TODO/Notes:**
- Backend testing setup still needs resolution.
- Placeholder `api.getLineTakes` function in `frontend/src/api.ts` needs to be replaced with a dedicated backend endpoint for efficiency when that's implemented.
- Consider replacing `alert()` with Mantine notifications for better UX feedback.

## Script Management Feature (Ongoing)

*   Started implementation of the Script Management feature as outlined in `.cursor/docs/script_management_spec.md`.
*   Focus is on backend DB models and API endpoints first (Phase 1).
*   Maintain backward compatibility with CSV generation path.

## Frontend Setup Resolution (April 18, 2025 Session)

**Problem:** UI changes (specifically Script Archive feature) were not reflecting in the browser, despite code changes.

**Troubleshooting:**
*   Initially suspected Docker volume mounts, build cache, dev server instability (SIGTERM errors). These were red herrings for the core UI update issue.
*   Found and fixed a parameter type bug where `GenerationForm.tsx` incorrectly called `api.listScripts` with an object instead of a boolean.
*   Isolated the frontend by running `npm run dev` locally, which *still* failed to show UI updates initially.
*   Discovered a zombie Vite process blocking port 5173, causing the new server to use 5174.
*   Even after fixing the port and clearing local Vite caches (`node_modules`, `.vite`), the local dev server remained unreliable in reflecting changes to `ManageScriptsPage.tsx` specifically.

**Resolution:**
*   Confirmed the parameter bug was fixed.
*   Confirmed the code for the archive feature exists and is correct.
*   Reverted to a **Static Build + Nginx Proxy** configuration within Docker as the stable solution.
    *   `frontend/Dockerfile` uses a multi-stage build (`npm run build` then serves `/dist` with Nginx).
    *   `frontend/nginx.conf` handles serving static files and proxying `/api` and `/audio` to the `backend` service (using runtime DNS resolution).
    *   `docker-compose.yml` maps host port 5173 to Nginx container port 80 and **does not** mount the local `./frontend` directory.

**Current Frontend Development Workflow:**
*   Make code changes locally in `./frontend`.
*   Run `docker compose build frontend` to rebuild the image with changes.
*   Run `docker compose up -d --force-recreate frontend` to restart the container.
*   Hard refresh the browser.

**Known Issues:**
*   The Vite development server (`npm run dev`) is unstable/unreliable within Docker on the development macOS machine, and also exhibited caching/file watching issues when run locally. Avoid using it for now.

## Celery Worker Task Updates (April 18, 2025 Session)

**Problem:** When adding a new parameter to a Celery task function, we encountered an error: `regenerate_line_takes() takes 8 positional arguments but 9 were given`.

**Root Cause:**
* The application architecture separates the backend API (Flask in `backend/app.py`) from the task processing (Celery in `tasks.py`).
* The API endpoint was updated to pass the new parameter, but the Celery worker container was still running the old version of the task function.
* We had only restarted the backend container but not the worker container, which is a separate service.

**Project Architecture Insights:**
* The application uses separate containers for different services:
  * `frontend` - Nginx container serving the React frontend
  * `backend` - Flask API service handling HTTP requests
  * `worker` - Celery worker processing background tasks
  * `redis` - Message broker for Celery task queue

**Resolution:**
1. Identified the correct function signature mismatch between backend API endpoint and Celery task
2. Updated the Celery task to include the new parameter
3. Copied the updated `tasks.py` file to the worker container
4. Restarted the worker service to pick up the changes

**Additional Issue Found:**
* Our task code was attempting to access a non-existent field (`generation_history`) in the Script model
* Fixed the script update logic to use a more direct approach (finding scripts by line_key)

**Deployment Workflow for Task Changes:**
* Update the task code in `tasks.py`
* Copy to worker container: `docker compose cp tasks.py worker:/app/`
* Restart worker: `docker compose restart worker`
* Alternatively, for more thorough updates: `docker compose build worker && docker compose up -d --force-recreate worker` 