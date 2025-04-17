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