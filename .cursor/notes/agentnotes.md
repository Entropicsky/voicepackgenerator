# Agent Notes for Voice Pack Generator

## Project Overview

This project generates voice packs. It consists of three main components orchestrated using Docker Compose for local development and potentially deployed to Heroku:

1.  **Frontend:** A Vite/React application served via Nginx (local port 5173).
2.  **Backend:** A Flask API (local port 5001) responsible for handling requests, managing job/script data (via PostgreSQL), and interfacing with ElevenLabs (`utils_elevenlabs.py`) and Cloudflare R2 (`utils_r2.py`).
3.  **Worker:** A Celery worker process that handles background tasks (audio generation via `tasks.py`), using Redis as a message broker and result backend.

## Key Technologies

*   Frontend: Vite, React, TypeScript, Mantine, Nginx
*   Backend: Python, Flask, Celery, SQLAlchemy, Alembic, Boto3 (for R2)
*   Broker: Redis
*   Database: PostgreSQL
*   Storage: Cloudflare R2 (S3-compatible)
*   Deployment: Docker Compose (local), Heroku (target)

## Development & Deployment Notes

*   **Local:** Runs via `docker-compose up`. Uses PostgreSQL and Redis containers. Uses a `.env` file for environment variables (API keys, R2 credentials, DB URL).
*   **Heroku:** Target deployment platform. Requires specific configuration (`heroku.yml`). Uses Heroku Redis and Heroku Postgres addons. Requires R2 environment variables set as Config Vars.
*   **Heroku Auto-Deploy:** **Active**. The Heroku app `voicepackgenerator-prod` is configured for automatic deployment from the GitHub `master` branch. Pushing to `master` triggers a deployment.
*   **R2 Integration:** **Complete**. The application uses Cloudflare R2 for storing generated audio (`.mp3`) and batch metadata (`metadata.json`) in both development and production.
    *   Uses `boto3` (via `utils_r2.py`).
    *   Requires `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` environment variables.
    *   File prefixes: `<skin_name>/<voice_folder_name>/<batch_id>/takes/<file.mp3>` and `<skin_name>/<voice_folder_name>/<batch_id>/metadata.json`.
    *   API endpoints (`/api/batches`, `/api/batch/...`) use the full R2 prefix.
    *   Audio serving (`/audio/...`) uses redirects to presigned R2 URLs.
    *   Batch downloads (`.../download`) generate zips from R2.
    *   Local filesystem storage (`utils_fs.py`, `AUDIO_ROOT`) removed.
*   **Frontend Prefix Handling:** Frontend uses `encodeURIComponent()` for `batch_prefix` in URLs.
*   **Locking Removed:** Filesystem batch locking removed. R2 metadata updates are last-write-wins.
*   **OpenAI API:** Uses the **Responses API** for features like AI text optimization (`/api/optimize-line-text`). Must refer to `.cursor/docs/responseapi.md` and **not** use the legacy Chat Completions API. Uses the **Agents SDK** for script generation (`ScriptWriterAgent`, `run_script_creation_agent` task), requiring the `OPENAI_AGENT_MODEL` environment variable (e.g., `gpt-4o`) set in `.env` and Heroku Config Vars.
*   **Database:** Uses PostgreSQL (Heroku Postgres on production, local Postgres via Docker for dev). Schema managed by Alembic (`backend/models.py`, `migrations/`). See `.cursor/notes/db.md` for schema details.

## Current Frontend Workflow

1.  **Create Voices:** Design/select voices using ElevenLabs integration.
2.  **Manage Scripts:** Import/edit existing scripts for voice recording.
3.  **Generate Recordings:** Batch generate audio takes for script lines.
4.  **Monitor Generations:** Track batch job status.
5.  **Edit Recordings:** Rank/review generated takes, potentially crop audio.

## Current Status & Issues

*   **R2 Storage:** Implemented and tested locally. Deployed via auto-deploy.
*   **PostgreSQL Migration:** Complete and deployed.
*   **Frontend:** Updated for R2 prefixes and batch context. AI Wizard text optimization feature added (`RegenerationModal.tsx`). VO Script feature UI (List, Create, Detail) implemented.
*   **Backend:** VO Script feature backend (Models, Migrations, API Endpoints, Agent Task) implemented, including category refinement and refinement prompts.
*   **Testing:** Backend tests exist in `backend/tests/` and appear comprehensive. Frontend testing status needs investigation.
*   **Authentication:** Cloudflare Access setup deferred (requires custom domain).
*   **Audio Cropping Feature:** Spec created, implementation backlogged.
*   **AI Text Optimization:** Implemented backend/frontend, needs end-to-end testing and prompt refinement.
*   **File Size Issues:** Several files significantly exceed the 500-line guideline (`VoScriptDetailView.tsx`, `vo_script_routes.py`, `api.ts`, potentially `tasks.py`), suggesting refactoring opportunities.

## Next Steps / Current Focus (As of [Current Date])

1.  **Documentation:** Update README, document new APIs, update agent notes.
2.  **VO Script Feature Polish:** Address TODOs in `VoScriptDetailView` (metadata edit, status display, audio player, etc.).
3.  **Template Manager UI:** Implement editing capabilities for VO Script Templates.
4.  **Testing:** Implement comprehensive testing (Unit, Integration, Feature) for backend & frontend, especially the VO Script feature.
5.  **Refactoring:** Prioritize refactoring large files (`VoScriptDetailView.tsx`, `vo_script_routes.py`) to improve maintainability.
6.  Test and refine the AI Wizard text optimization feature.
7.  Implement Cloudflare Access (requires custom domain setup).
8.  Address Audio Cropping feature from backlog.

## Long Term Direction

*   Evolve the application towards a multi-game SaaS product.

## Pointers

*   Project Checklist: `.cursor/notes/project_checklist.md`
*   Notebook: `.cursor/notes/notebook.md`
*   DB Schema: `.cursor/notes/db.md`
*   R2 Spec: `.cursor/docs/cloudflare_integration.md`
*   Crop Spec: `.cursor/docs/cropping_tech_spec.md`
*   AI Wizard Prompt Rules: `.cursor/docs/scripthelp.md`
*   OpenAI Responses API Doc: `.cursor/docs/responseapi.md`
*   Docker Config: `docker-compose.yml`
*   SQLAlchemy Models: `backend/models.py`
*   Alembic Migrations: `migrations/`
*   Celery Config: `backend/celery_app.py`
*   Heroku Config: `heroku.yml`

## Testing Notes & Procedures

*   **Environment:** Backend Python tests **MUST** be run inside the `backend` Docker container as dependencies are isolated there. Do not run `pytest` or `unittest` directly from the host OS unless specifically targeting host-only scripts.
*   **Command:** Use `docker exec <container_id> pytest <test_path>`.
    *   Get container ID via `docker-compose ps -q backend`.
    *   Example: `docker exec $(docker-compose ps -q backend) pytest backend/tests/test_utils_openai.py`
*   **Test Runner:** `pytest` is installed and preferred for discovery and execution.
*   **Imports in Tests:** Use absolute imports relative to the `/app` directory structure inside the container. The main backend code is the `backend` package (`/app/backend`). Therefore, within test files (`/app/backend/tests/*.py`), import application modules using `from backend import module` or `from backend.submodule import item`.
*   **Module Resolution:** If `ImportError` occurs:
    *   Verify the imported module/file actually exists (e.g., `utils_fs.py` was removed but tests still tried to import it).
    *   Double-check the import path against the actual file location (`/app/backend/...`).
*   **Mocking Assertions:** When using `mock.assert_called_once_with` (or similar), ensure the expected arguments exactly match the actual call, including arguments passed with default values from the function signature (e.g., default `temperature`).

## Recent Project Updates

### Instantiate Target Lines Feature (2024-04-30)

Added capability to dynamically create multiple directed taunt lines (or similar) with automatic generation:

1. Backend changes:
   - Created new endpoint `/vo-scripts/<script_id>/instantiate-lines` that accepts target names
   - Enhanced `get_category_lines_context` to properly handle lines with direct category_id
   - Added special handling for directed taunt lines in batch generation
   - Modified category batch generation to process newly created lines
   - Improved logging throughout the process

2. Frontend changes:
   - Added "Instantiate Target Lines" button to VoScriptDetailView
   - Created modal form for entering target names, category, and prompt template
   - Implemented automatic content generation after line creation
   - Fixed issue with template line finding
   - Added natural sorting for lines within categories

3. Excel Export Feature
   - Added "Download Excel" button to export VO scripts for review
   - Implemented backend endpoint using openpyxl to format script data with proper styling
   - Fixed filename sanitization issues
   - Structured Excel with script name in A1, character description in A2, and lines organized by category

4. Bug Fixes for Locked Lines
   - Fixed bugs where refinement operations (global and category-level) were modifying locked lines
   - Added proper lock checking in all refinement endpoints
   - Added missing is_locked field to context dictionaries
   - Modified template creation logic to automatically lock static text lines

5. Progress Visualization
   - Implemented progress bar for global refinement operations
   - Created frontend orchestration approach with sequential line processing
   - Improved feedback during lengthy operations

This feature allows users to create multiple directed taunts (or similar content) without needing to manually create each line or define every possible target in the template.

### Static Template Lines Feature (2024-04-29)

Added support for static template lines that bypass LLM generation:

1. Database changes:
   - Added `static_text` column to `vo_script_template_lines` table
   - Updated database directly with SQL since Flask-Migrate was having issues

2. Backend changes:
   - Modified script creation logic to copy static text from template lines
   - Updated batch generation logic to skip lines that already have text
   - Updated template line endpoints to handle static_text field

3. Frontend changes:
   - Added static text toggle and input to template editor
   - Added visual indicators for static lines in script detail view
   - Disabled regenerate/refine buttons for static template lines

This feature allows standard phrases (like VGS commands "Yes", "Thanks") to be defined once in the template and automatically populated in scripts without consuming LLM tokens.

### Usage

To create static template lines:
1. Open the template editor
2. When adding or editing a line, toggle "Use Static Text"
3. Enter the exact text that should appear in scripts
4. All scripts created from this template will have this text pre-populated

When a script is created from a template with static lines, those lines will:
- Be automatically populated with the static text
- Have status set to 'generated'  
- Be visually distinguished in the UI
- Be protected from regeneration/refinement 

## Recent Work

### Fixed Line Regeneration and Task Status Polling (May 2025)

Fixed an issue where line regeneration tasks were getting stuck when polling for task status:

1. **Issue Identified**:
   - Frontend was polling for task status with ID "undefined" instead of the actual task ID
   - Problem traced to snake_case vs camelCase mismatch in API responses

2. **Fix Applied**:
   - Updated API functions to correctly map response fields (task_id → taskId, job_id → jobId)
   - Made TypeScript interfaces consistent with camelCase naming convention
   - Applied the fix to all similar endpoints (regeneration, speech-to-speech, crop)

3. **API Functions Updated**:
   - `regenerateLineTakes`
   - `startSpeechToSpeech`
   - `cropTake`
   - `getTaskStatus`
   - `triggerGenerateCategoryBatch`

This fix resolved issues where regeneration tasks appeared to be running but never completed because the frontend was polling for an undefined task ID.

### Backend Modular Refactoring (May 2025)

The backend was recently refactored to improve maintainability:

1. **Task Module Structure**:
   - Created `backend/tasks/` directory as a package
   - Implemented central registry in `tasks/__init__.py`
   - Split functionality into:
     - `generation_tasks.py` (voice generation)
     - `regeneration_tasks.py` (line regeneration and speech-to-speech)
     - `audio_tasks.py` (audio cropping)
     - `script_tasks.py` (script creation and category generation)

2. **Route Blueprint Structure**:
   - Leveraged Flask's Blueprint system
   - Created specialized route modules:
     - `voice_routes.py` (voice management)
     - `generation_routes.py` (generation jobs)
     - `batch_routes.py` (batch operations)
     - `audio_routes.py` (audio serving)
     - `task_routes.py` (task status endpoint)
     - `vo_script_routes.py` (VO script management)
     - `vo_template_routes.py` (VO template management)

3. **Testing and Validation**:
   - Implemented comprehensive testing for refactored code:
     - `test_tasks_modules.py`: Validates task module imports and function signatures
     - `test_blueprint_routes.py`: Verifies blueprint registrations and route structure
     - `test_blueprint_routes_live.py`: Tests actual endpoints against the database
     - `test_refactoring_e2e.py`: End-to-end tests of the full workflow

4. **Fixes Applied**:
   - Added missing `datetime` import in `app.py`
   - Fixed blueprint URL prefix handling
   - Added proper error handling for Celery tasks called directly

## Environment Setup

### Docker Environment
- Uses Docker Compose for local development
- Services:
  - `backend`: Flask API server
  - `worker`: Celery worker
  - `frontend`: React frontend
  - `redis`: Message broker for Celery
  - `db`: PostgreSQL database

### API Keys and Environment Variables
- `ELEVENLABS_API_KEY`: For voice synthesis
- `OPENAI_API_KEY`: For AI script generation
- Cloudflare R2 credentials for audio storage

## Development Guidelines

### Code Structure
- Keep files under 500 lines for maintainability
- Follow single responsibility principle
- Each module should have a clear focus:
  - Task modules handle background processing
  - Route modules handle API endpoints
  - Utility modules provide shared functionality

### Testing
- Always run tests after making changes to the backend
- Use comprehensive tests for new features
- Prefer testing with real database when possible

## Common Development Tasks

### Running Tests
```bash
# Run all tests
docker-compose exec backend python -m unittest discover

# Run specific test file
docker-compose exec backend python -m unittest backend.tests.test_refactoring_e2e

# Run with proper Flask app context
docker-compose exec backend python -m flask test
```

### Accessing API Endpoints
```bash
# Check API status
curl http://localhost:5001/api/ping

# List voices
curl http://localhost:5001/api/voices
```

## Current State (AI Chat Collaborator)
- **UI:** Implemented as a collapsible side panel (`AppShell.Aside`) using Mantine in the `VoScriptDetailView`.
- **Backend:** Uses Celery (`run_script_collaborator_chat_task`) to run an `openai-agents` based agent (`ScriptCollaboratorAgent`).
- **Functionality:**
    - Users can send messages to the agent.
    - Agent uses tools (`get_script_context`, `propose_script_modification`, etc.) to interact with the database.
    - Agent provides text responses and structured proposals for script line modifications (`REPLACE_LINE` currently implemented).
    - Proposals are displayed as interactive cards in the UI.
    - Users can Accept, Dismiss, or Edit & Commit `REPLACE_LINE` proposals.
    - Multiple proposals are handled and displayed, sorted by script order (`suggested_order_index` then `suggested_line_key`).
    - "Accept All" button allows batch acceptance of proposals.
    - Line key (`suggested_line_key`) is displayed on proposal cards for clarity.
    - **Chat History Persistence:**
        - Backend: `ChatMessageHistory` table stores all messages.
        - Backend: Celery task loads history from DB for agent, saves new turn to DB.
        - Backend: `GET /api/vo-scripts/:id/chat/history` endpoint provides history.
        - Frontend: Loads history on panel open for current script, displays it, and chat is persistent across refreshes.
    - Agent now uses a `propose_multiple_line_modifications` tool for suggesting changes to multiple lines at once, improving performance and directness of proposals.
    - Agent instructions refined to encourage more direct tool usage for line modifications after user requests changes.
    - Agent provides textual "thinking aloud" messages before long operations.
    - Celery task provides `status_message` updates during progress, displayed in frontend.
    - Chat History Persistence: Fully implemented (DB backend, API, Frontend Load/Display, Clear History button).
- **Resilience:**
    - Frontend polling timeout (`MAX_POLLING_ATTEMPTS` increased to ~2 mins).
    - Backend agent uses default `openai` library timeout/retry settings.

## Next Steps / Focus Areas (AI Chat)
- Thoroughly test current `REPLACE_LINE` proposals (single and batch) and history persistence.
- Implement frontend UI and commit logic for `StagedCharacterDescriptionData`.
- Implement frontend handling for other proposal types (INSERT_*, NEW_LINE_*) generated by `propose_multiple_line_modifications`.
- Implement agent's use of `add_to_scratchpad` tool and corresponding frontend display.
- Enhance agent proactivity for suggesting other modification types (e.g., add new lines, not just replace).

## Pointers to Key Files
- Chat UI: `frontend/src/components/chat/ChatDrawer.tsx`
- Chat Store: `frontend/src/stores/chatStore.ts`
- Chat API Client: `frontend/src/api.ts`, `frontend/src/types.ts` (Chat types)
- Chat Backend API Routes: `backend/routes/vo_script_routes.py`
- Chat Celery Task: `backend/tasks/script_tasks.py`
- Chat Agent Definition & Tools: `backend/agents/script_collaborator_agent.py` (includes `propose_multiple_line_modifications`)
- Chat History DB Model: `backend/models.py` (`ChatMessageHistory`)
- Checklist: `.cursor/notes/project_checklist.md`
- Notebook: `.cursor/notes/notebook.md` 