# Project Checklist

## Housekeeping / Setup

*   [x] Review project status & notes.
*   [x] Inspect DB Schema & document in `.cursor/notes/db.md`.
*   [x] Update `.cursor` notes (`agentnotes.md`, `notebook.md`, `project_checklist.md`) with current context.
*   [ ] **TODO:** Get standard tools from `Entropicsky/mycursorrules` and place in `.cursor/tools` (User confirmation pending).
*   [ ] **TODO:** Clarify purpose of `.cursor/node_modules` folder (User confirmation pending).

## Phase 1: Restore Local Development Environment

*   [x] Analyze project structure and configuration (`docker-compose.yml`, `backend/celery_app.py`, `start.sh`).
*   [x] Identify root cause of local failure (forced Redis SSL connection in `celery_app.py`).
*   [x] Apply fix to `backend/celery_app.py` to correctly handle Redis URLs (SSL for `rediss://`, no SSL for `redis://`).
*   [x] Rebuild and restart Docker containers (`docker-compose down && docker-compose up --build -d`).
*   [x] Verify local application functionality:
    *   [x] Celery worker connects to Redis successfully (check logs).
    *   [x] Frontend loads correctly (`http://localhost:5173/voice-design`).
    *   [x] Backend API is responsive (`http://localhost:5001`). (Verified via frontend logs showing successful API calls)
    *   [x] Core functionality (e.g., submitting a task) works. (Verified via frontend logs showing task status/audio requests)
*   [x] Commit the fix to version control.

## Phase 2: Address Heroku Deployment

*   [x] Review Heroku configuration (`heroku.yml`, `start.sh`).
*   [x] Confirm required Heroku environment variables (especially `REDIS_TLS_URL`).
*   [x] Verify SSL settings in `backend/celery_app.py` are appropriate for Heroku Redis (`ssl_cert_reqs`). (Used `ssl.CERT_NONE` via dict config).
*   [x] Test deployment to Heroku.
*   [x] Debug Heroku-specific issues (Nginx config, Celery SSL connection).
*   [x] **CONFIRMED VIA AUTO-DEPLOY:** Pushes to `master` deploy automatically.

## Phase 3: Improve Robustness

*   [ ] **TODO:** Implement basic testing framework (`tests/` directory needs creation/content).
*   [ ] **TODO:** Add unit/integration tests for critical components (Celery tasks, API endpoints, R2 utils, DB models).
*   [ ] **TODO:** Add feature tests for core workflows.

## Phase 4: Migrate to PostgreSQL

*   [x] Provision Heroku Postgres addon.
*   [x] Install Postgres dependencies (`psycopg2-binary`, `alembic`, `Flask-Migrate`) in `backend/requirements.txt`.
*   [x] Add `db` service (Postgres) to `docker-compose.yml`.
*   [x] Configure `backend` and `worker` services in `docker-compose.yml` to use `db` service (`depends_on`, `DATABASE_URL`).
*   [x] Update `backend/models.py` to use `DATABASE_URL` environment variable and Postgres engine settings.
*   [x] Update `backend/models.py` to use `postgresql.JSONB` variant for JSON columns.
*   [x] Configure `Flask-Migrate` in `backend/app.py`.
*   [x] Remove SQLite initialization (`touch jobs.db`, `init_db()`) from `Dockerfile` and `Dockerfile.worker`.
*   [x] Remove `sqlite` from `apk add` in `Dockerfile` and `Dockerfile.worker`.
*   [x] Initialize Alembic (`flask db init`).
*   [x] Configure Alembic (`migrations/env.py`) to use model metadata.
*   [x] Generate initial Alembic migration (`flask db migrate`).
*   [x] Apply migration locally (`flask db upgrade`).
*   [x] Commit migration files and code changes.
*   [x] Test local environment thoroughly with Postgres.
*   [x] Add `release` phase (`flask db upgrade`) to `heroku.yml`.
*   [x] Deploy to Heroku (`git push heroku master`).
*   [x] Verify Heroku deployment (logs, release phase, functionality).
*   [x] Decommission SQLite artifacts (remove `jobs.db`, update `.gitignore`).

## Phase 5: Cloudflare R2 Storage & Access Authentication

*   [x] **USER TASK:** Setup Cloudflare R2 Bucket & API Tokens.
*   [ ] **USER TASK:** Register Custom Domain. *(Status: Deferred)*
*   [ ] **USER TASK:** Add Custom Domain to Cloudflare & Heroku, configure Cloudflare DNS (Proxied CNAME). *(Status: Deferred)*
*   [ ] **USER TASK:** Setup Cloudflare Access Application & Policies (Google Workspace Auth on Custom Domain). *(Status: Deferred)*
*   [x] Create technical specification (`.cursor/docs/cloudflare_integration.md`).
*   [x] Add `boto3` to `backend/requirements.txt`.
*   [x] Add R2 credentials/config to Heroku Config Vars & local `.env`.
*   [x] Create `backend/utils_r2.py` for R2 SDK interactions.
*   [x] Refactor `backend/tasks.py` (generation tasks) to upload files/metadata to R2.
*   [x] Refactor `backend/app.py` to use R2 prefixes, read/serve/download from R2.
*   [x] Cleanup `utils_fs.py` and local filesystem references.
*   [x] Test R2 integration locally.
*   [x] Commit Cloudflare integration changes.
*   [x] Deploy Cloudflare changes to Heroku (via auto-deploy on merge to master).
*   [x] Verify full R2 functionality on Heroku (storage, playback, download).
*   [ ] **TODO:** Implement Cloudflare Access for authentication (Requires custom domain setup).

## Phase 6: Tidy Up & Documentation

*   [x] Update frontend components (BatchesPage, RankingPage) to use R2 prefixes correctly.
*   [ ] **TODO:** Ensure all documentation (.cursor folder, README) is up-to-date (Partially done, ongoing).
*   [ ] **TODO:** Review and potentially remove unused code/dependencies.
*   [ ] **TODO:** Final testing pass (Blocked by Phase 3).
*   [ ] **TODO:** Update README with R2/DB/OpenAI env var details.

## Phase 6.5: API Client Cleanup (Post-Refactor Issues)

*   [ ] **TODO: Frontend - API Client (`api.ts`)**
    *   [x] Add missing `api.updateVoScriptTemplate` function definition & export.
    *   [x] Add missing `api.createVoicePreviews` function definition & export.
    *   [x] Add missing `api.saveVoiceFromPreview` function definition & export.
    *   [x] Add missing `api.startGeneration` function definition & export.
    *   [x] Add missing `api.listScripts` function definition & export.
    *   [x] Add missing `api.toggleScriptArchive` function definition & export.
    *   [x] Add missing `api.getJobs` function definition & export (or rename call to `listGenerationJobs`).
    *   [x] Add missing `api.listBatches` function definition & export.
    *   [x] Add missing `api.updateTakeRank` function definition & export.
    *   [ ] Add missing `api.getLineTakes` function definition & export (or confirm client-side filtering is sufficient).
    *   [ ] Add missing `api.cropTake` function definition & export.
    *   [ ] Add missing `api.getTaskStatus` function definition & export.
    *   [ ] Add missing `api.regenerateLineTakes` function definition & export.
    *   [ ] Add missing `api.startSpeechToSpeech` function definition & export.
    *   [ ] Add missing `api.getVoicePreview` function definition & export.
    *   [ ] Add missing `api.optimizeLineText` function definition & export.
    *   [ ] Add missing `api.updateScript` function definition & export (for legacy scripts).
    *   [ ] Add missing `api.listVoScriptTemplateCategories` function definition & export (maybe lower priority).
    *   [ ] Add missing `api.getVoScriptTemplateCategory` function definition & export (maybe lower priority).
    *   [ ] Add missing `api.listVoScriptTemplateLines` function definition & export (maybe lower priority).
    *   [ ] Add missing `api.getVoScriptTemplateLine` function definition & export (maybe lower priority).
*   [ ] **TODO: Testing**
    *   [ ] Verify functionality of pages/components using the above API calls after fixes.

## Phase 7: New Feature - Create Script from Scratch

*   [x] Create Technical Specification ([scriptcreator_tech_spec.md](mdc:.cursor/docs/scriptcreator_tech_spec.md)).
*   [ ] **TODO: Backend - Database**
    *   [x] Define SQLAlchemy models for `vo_script_templates`, `vo_script_template_categories`, `vo_script_template_lines`, `vo_scripts`, `vo_script_lines` in [models.py](mdc:backend/models.py).
    *   [x] Generate Alembic migration script (`flask db migrate -m "Add VO Script Creator tables"`).
    *   [x] Review and refine the generated migration script.
    *   [x] Apply migration (`flask db upgrade`).
*   [ ] **TODO: Backend - Dependencies**
    *   [x] Add `openai[agents]` to `backend/requirements.txt`.
    *   [x] Implement `OPENAI_AGENT_MODEL` environment variable handling (Read in task, passed to agent).
*   [ ] **TODO: Backend - API Endpoints ([app.py](mdc:backend/app.py), [routes/*](mdc:backend/routes))**
    *   [x] Refactor: Move existing routes to blueprint files ([vo_template_routes.py](mdc:backend/routes/vo_template_routes.py), etc.)
    *   [x] Refactor: Register blueprints in [app.py](mdc:backend/app.py)
    *   [x] Refactor: Test moved routes (GET list/POST create for templates)
    *   [x] Implement & Test `VoScriptTemplate` GET by ID, PUT, DELETE in [vo_template_routes.py](mdc:backend/routes/vo_template_routes.py)
        *   [x] Implement `GET /api/vo-script-templates/<id>`
        *   [x] Test `GET /api/vo-script-templates/<id>` (existing, non-existent)
        *   [x] Implement `PUT /api/vo-script-templates/<id>`
        *   [x] Test `PUT /api/vo-script-templates/<id>` (update, 404, 409/500)
        *   [x] Implement `DELETE /api/vo-script-templates/<id>`
        *   [x] Test `DELETE /api/vo-script-templates/<id>` (delete, 404)
    *   [x] Implement & Test `VoScriptTemplateCategory` CRUD in [vo_template_routes.py](mdc:backend/routes/vo_template_routes.py)
        *   [x] Implement GET list (or nested)
        *   [x] Test GET list
        *   [x] Implement POST (or nested)
        *   [x] Test POST (create, 409)
        *   [x] Implement GET by ID
        *   [x] Test GET by ID (existing, 404)
        *   [x] Implement PUT
        *   [x] Test PUT (update, 404, 409)
        *   [x] Implement DELETE
        *   [x] Test DELETE (delete, 404)
    *   [x] Implement & Test `VoScriptTemplateLine` CRUD in [vo_template_routes.py](mdc:backend/routes/vo_template_routes.py)
        *   [x] Implement GET list (or nested)
        *   [x] Test GET list
        *   [x] Implement POST (or nested)
        *   [x] Test POST (create, 409)
        *   [x] Implement GET by ID
        *   [x] Test GET by ID (existing, 404)
        *   [x] Implement PUT
        *   [x] Test PUT (update, 404, 409)
        *   [x] Implement DELETE
        *   [x] Test DELETE (delete, 404)
    *   [x] Implement & Test `VoScript` CRUD (New file: [routes/vo_script_routes.py](mdc:backend/routes/vo_script_routes.py))
        *   [x] Create blueprint file `vo_script_routes.py`
        *   [x] Implement `POST /api/vo-scripts`
        *   [x] Register blueprint `vo_script_bp`
        *   [x] Test `POST /api/vo-scripts`
        *   [x] Implement `GET /api/vo-scripts`
        *   [x] Test `GET /api/vo-scripts`
        *   [x] Implement `GET /api/vo-scripts/<id>`
        *   [x] Test `GET /api/vo-scripts/<id>`
        *   [x] Implement `PUT /api/vo-scripts/<id>`
        *   [x] Test `PUT /api/vo-scripts/<id>`
        *   [x] Implement `DELETE /api/vo-scripts/<id>`
        *   [x] Test `DELETE /api/vo-scripts/<id>`
    *   [ ] Implement & Test `VoScriptLine` related endpoints (in [routes/vo_script_routes.py](mdc:backend/routes/vo_script_routes.py))
        *   [ ] `GET /api/vo-scripts/<id>/lines` (Note: Already included in GET /api/vo-scripts/<id>)
        *   [x] `POST /api/vo-scripts/<id>/feedback`
        *   [x] `POST /api/vo-scripts/<id>/run-agent` (API Endpoint + Placeholder Task)
*   [ ] **TODO: Backend - Agent & Task ([agents/script_writer.py](mdc:backend/script_agents/script_writer.py), [tasks.py](mdc:backend/tasks.py))**
    *   [x] Define `ScriptWriterAgent` class skeleton ([agents/script_writer.py](mdc:backend/script_agents/script_writer.py)).
    *   [x] Define `@tool` function skeletons in ([agents/script_writer.py](mdc:backend/script_agents/script_writer.py)).
    *   [x] Implement `@tool` function `get_vo_script_details`.
    *   [x] Implement `@tool` function `get_lines_for_processing`.
    *   [x] Implement `@tool` function `update_script_line` (includes history append).
    *   [x] Define Celery task `run_script_creation_agent` in [tasks.py](mdc:backend/tasks.py).
    *   [x] Update Celery task to instantiate Agent and call `run_sync` (Basic Implementation).
    *   [x] Test agent invocation flow (API -> Task -> Agent -> Tools -> DB Update).
*   [ ] **TODO: Frontend - Routing & Pages**
    *   [ ] Implement route and page component for `/script-templates`.
    *   [x] Implement route and page component for `/vo-scripts` (`VoScriptListView`).
    *   [x] Implement route and page component for `/vo-scripts/new` (`VoScriptCreateView`).
    *   [x] Implement route and page component for `/vo-scripts/:scriptId` (`VoScriptDetailView`).
*   [ ] **TODO: Frontend - Components**
    *   [ ] Implement `TemplateManager` component (or integrate into `/script-templates` page).
    *   [x] Implement `VoScriptListView` component.
        *   [x] Fetch and display list of VO Scripts.
        *   [x] Add 'Create New' button/link.
        *   [x] Add link to detail view for each script.
        *   [x] Implement Delete button/action.
    *   [x] Implement `VoScriptCreateView` component.
        *   [x] Fetch and display `VoScriptTemplate` list in dropdown.
        *   [x] Implement form for name/description/template selection.
        *   [x] Handle form submission (call `POST /api/vo-scripts`).
        *   [x] Redirect to detail view on success.
    *   [x] Implement `VoScriptDetailView` component.
        *   [x] Fetch and display script metadata.
        *   [x] Fetch and display script lines (confirm API structure needed).
        *   [x] Group lines by category.
        *   [x] Implement 'Run Agent' button/action.
        *   [x] Implement line display (text, status).
        *   [ ] Implement metadata update functionality (optional inline edit).
        *   [x] Implement feedback mechanisms.
        *   [ ] Display generation status/progress.
*   [ ] **TODO: Testing**
    *   [ ] Write backend unit/integration tests for new models, API endpoints, agent tools, and Celery task.
    *   [ ] Write frontend tests for new `VoScript` components and pages.
*   [ ] **TODO: Documentation**
    *   [ ] Update README with setup instructions for new environment variables (`OPENAI_AGENT_MODEL`).
    *   [ ] Document the new API endpoints (e.g., in `.cursor/docs/api.md`).
*   [ ] **TODO: Future Integration**
    *   [ ] Plan strategy for integrating `vo_scripts` data with the main `scripts` table.
    *   [ ] Implement data migration/integration.

## Backlog Features

*   **Feature: Audio Cropping**
    *   [x] Create technical specification (`.cursor/docs/cropping_tech_spec.md`).
    *   [ ] **TODO:** Implement Frontend (`AudioEditModal.tsx`, `wavesurfer.js` integration, `TakeRow.tsx` changes).
    *   [x] Implement Backend (`/crop` API endpoint, `crop_audio_take` Celery task, `pydub`/`ffmpeg` integration).
    *   [ ] **TODO:** Add dependencies (`wavesurfer.js`, `pydub`, `ffmpeg`).
    *   [ ] **TODO:** Test cropping functionality thoroughly (local & Heroku).
*   **Feature: AI Text Optimization Wizard**
    *   [x] Add backend endpoint (`/api/optimize-line-text`) using OpenAI Responses API.
    *   [x] Add `openai` dependency to `backend/requirements.txt`.
    *   [x] Read `OPENAI_API_KEY` and `OPENAI_MODEL` from env vars.
    *   [x] Add frontend API call (`api.optimizeLineText`).
    *   [x] Add button and logic to `RegenerationModal.tsx`.
    *   [x] Verify Docker/Heroku compatibility.
    *   [ ] **TODO:** Test functionality end-to-end.
    *   [ ] **TODO:** Refine OpenAI prompt in `backend/app.py` based on testing if needed.

## Phase 8: Interactive VO Script Refinement

*   [x] Create Technical Specification (`.cursor/docs/interactive_refinement_spec.md`).
*   [x] **TODO: Backend - Setup & Utilities**
    *   [x] Add `openai` dependency to `backend/requirements.txt` if not already present (Confirm it includes base client, not just `[agents]`).
    *   [x] Ensure OpenAI API key (`OPENAI_API_KEY`) is configured via environment variables (`.env`, Heroku Config Vars).
    *   [x] Create `backend/utils_openai.py` (or similar) for reusable OpenAI Responses API call logic (including prompt construction helpers, error handling).
        *   [x] Define function `call_openai_responses_api(prompt: str, ...) -> str | None`.
        *   [x] Write unit tests for `call_openai_responses_api` (mocking `openai.Client().responses.create`).
    *   [x] Create `backend/utils_voscript.py` (or similar) for reusable VO Script database logic.
        *   [x] Refactor/create function `get_line_context(db: Session, line_id: int) -> dict | None`.
        *   [x] Write unit tests for `get_line_context`.
        *   [x] Refactor/create function `get_category_lines_context(db: Session, script_id: int, category_name: str) -> list[dict]`.
        *   [x] Write unit tests for `get_category_lines_context`.
        *   [x] Refactor/create function `get_script_lines_context(db: Session, script_id: int) -> list[dict]`.
        *   [x] Write unit tests for `get_script_lines_context`.
        *   [x] Refactor/create function `update_line_in_db(db: Session, line_id: int, new_text: str, new_status: str, model_name: str) -> models.VoScriptLine | None`.
        *   [x] Write unit tests for `update_line_in_db`.
*   [x] **TODO: Backend - API Endpoint: Line Refinement**
    *   [x] Define route `POST /api/vo-scripts/<int:script_id>/lines/<int:line_id>/refine` in `vo_script_routes.py`.
    *   [x] Implement request body parsing (expecting `line_prompt`).
    *   [x] Implement logic to fetch line context using `utils_voscript.get_line_context`.
    *   [ ] Implement logic to construct prompt for single-line refinement.
        *   [ ] Write unit tests for line refinement prompt construction.
    *   [x] Implement call to `utils_openai.call_openai_responses_api`.
    *   [x] Implement logic to parse OpenAI response and update DB using `utils_voscript.update_line_in_db`.
    *   [x] Implement response formatting (return updated line).
    *   [x] Write integration test for the endpoint (mocking DB utils & OpenAI util).
*   [x] **TODO: Backend - API Endpoint: Category Refinement**
    *   [x] Define route `POST /api/vo-scripts/<int:script_id>/categories/refine` in `vo_script_routes.py`.
    *   [x] Implement request body parsing (expecting `category_name`, `category_prompt`, potentially `line_prompts: dict`).
    *   [x] Implement logic to fetch context for lines in category using `utils_voscript.get_category_lines_context`.
    *   [ ] Implement logic to construct prompt(s) for category refinement.
        *   [ ] Write unit tests for category refinement prompt construction.
    *   [x] Implement call(s) to `utils_openai.call_openai_responses_api`.
    *   [x] Implement logic to parse OpenAI response(s) and update DB using `utils_voscript.update_line_in_db` for affected lines.
    *   [x] Implement response formatting (return list of updated lines).
    *   [x] Write integration test for the endpoint.
*   [x] **TODO: Backend - API Endpoint: Script Refinement**
    *   [x] Define route `POST /api/vo-scripts/<int:script_id>/refine` in `vo_script_routes.py`.
    *   [x] Implement request body parsing (expecting `global_prompt`, potentially `category_prompts: dict`, `line_prompts: dict`).
    *   [x] Implement logic to fetch context for all relevant script lines using `utils_voscript.get_script_lines_context`.
    *   [ ] Implement logic to construct prompt(s) for script refinement.
        *   [ ] Write unit tests for script refinement prompt construction.
    *   [x] Implement call(s) to `utils_openai.call_openai_responses_api`.
    *   [x] Implement logic to parse OpenAI response(s) and update DB using `utils_voscript.update_line_in_db` for affected lines.
    *   [x] Implement response formatting (return list of updated lines).
    *   [x] Write integration test for the endpoint.
*   [x] **TODO: Backend - Hierarchical Prompting**
    *   [x] Modify `utils_voscript.get_category_lines_context` to include script-level `refinement_prompt`.
    *   [x] Write/Update unit tests for `get_category_lines_context` script prompt retrieval.
    *   [x] Modify `utils_voscript.get_script_lines_context` to include category-level `refinement_prompt`.
    *   [x] Write/Update unit tests for `get_script_lines_context` category prompt retrieval.
    *   [x] Update `refine_vo_script_category` endpoint logic to fetch and use hierarchical prompts (global, category, line).
    *   [x] Write unit tests for hierarchical prompt construction in `refine_vo_script_category`.
    *   [x] Run integration tests for `refine_vo_script_category` endpoint.
    *   [x] Update `refine_vo_script` endpoint logic to fetch and use hierarchical prompts (global, category, line).
    *   [x] Write unit tests for hierarchical prompt construction in `refine_vo_script`.
    *   [x] Run integration tests for `refine_vo_script` endpoint.
*   [x] **TODO: Frontend - API Client (`frontend/src/api.ts`)**
    *   [x] Define functions to call the new `/refine` endpoints.
*   [x] **TODO: Frontend - Line Refinement UI (`VoScriptDetailView.tsx`)**
    *   [x] Add "Refine" `ActionIcon` next to each line's feedback `Textarea`.
    *   [x] Implement state (e.g., `useState` or `useReducer`) to manage loading status per line.
    *   [x] Implement `useMutation` hook (from `@tanstack/react-query`) for the line refine API call.
    *   [x] Update `onClick` handler for the new button to trigger the mutation, passing the current line prompt text.
    *   [x] Implement UI updates on mutation success (update line text, clear loading state) and error handling (show notification).
    *   [ ] Write component tests mocking the API call mutation.
*   [x] **TODO: Frontend - Category Refinement UI (`VoScriptDetailView.tsx`)**
    *   [x] Implement state to manage loading status per category.
    *   [x] Implement `useMutation` hook for the category refine API call.
    *   [x] Update `onClick` handler for the "Refine Category" button to trigger the mutation, passing the current category prompt text.
    *   [x] Implement UI updates on mutation success (update relevant lines, clear loading state) and error handling.
    *   [x] Disconnect "Refine Category" button from `runAgentMutation`.
    *   [ ] Write component tests.
*   [x] **TODO: Frontend - Script Refinement UI (`VoScriptDetailView.tsx`)**
    *   [x] Rename/Repurpose "Refine All (Feedback)" button to "Refine Script".
    *   [x] Implement state to manage global script refinement loading status.
    *   [x] Implement `useMutation` hook for the script refine API call.
    *   [x] Update `onClick` handler for the "Refine Script" button to trigger the mutation, passing the global prompt (and potentially collected category/line prompts).
    *   [x] Implement UI updates on mutation success (update relevant lines, clear loading state) and error handling.
    *   [x] Disconnect this button from `runAgentMutation`.
    *   [ ] Write component tests.
*   [x] **TODO: Backend - Cleanup**
    *   [x] Review `run_script_creation_agent` task (`tasks.py`) and `ScriptWriterAgent` (`script_writer.py`).
    *   [x] Remove or comment out code related to `'refine_category'` and `'refine_feedback'` task types if fully superseded.
    *   [x] Ensure `generate_draft` functionality remains intact.
*   [x] **TODO: Feature - Editable Character Description**
    *   [x] FE: Modify `VoScriptDetailView.tsx`: Replace `<pre>` with `<Textarea>` for character description.
    *   [x] FE: Add state management for edited description text.
    *   [x] FE: Add "Save Description" button and enable/disable logic.
    *   [x] FE: Implement `useMutation` hook calling `api.updateVoScript` for description update.
    *   [x] FE: Add loading/error/success handling for description save.
    *   [ ] Test: Manually test description editing and saving.
    *   [x] BE: Verify refinement endpoints use updated description (via context fetch - likely no change needed).
*   [x] **TODO: Feature - Line Locking**
    *   [x] BE: Add `is_locked` column (Boolean, default False) to `vo_script_lines` table model (`models.py`).
    *   [x] BE: Generate Alembic migration (`flask db migrate -m "Add is_locked to vo_script_lines"`).
    *   [x] BE: Review and apply migration (`flask db upgrade`).
    *   [x] BE: Implement `PATCH /api/vo-scripts/<script_id>/lines/<line_id>/toggle-lock` endpoint logic.
    *   [x] BE: Write integration test for the `toggle-lock` endpoint.
    *   [x] BE: Modify `refine_vo_script_category` and `refine_vo_script` endpoints to filter out locked lines before processing.
    *   [x] BE: Update integration tests for category/script refinement to verify locked lines are skipped.
    *   [x] FE: Add `toggleLock` function to `api.ts`.
    *   [x] FE: Implement lock/unlock UI and mutation in `VoScriptDetailView.tsx` (as part of Table refactor).
*   [x] **TODO: Feature - Refactored Line UI & Actions**
    *   [x] BE: Implement `PATCH /api/vo-scripts/<script_id>/lines/<line_id>/update-text` endpoint logic.
    *   [x] BE: Write integration test for the `update-text` endpoint.
    *   [x] BE: Implement `DELETE /api/vo-scripts/<script_id>/lines/<line_id>` endpoint logic.
    *   [x] BE: Write integration test for the `delete line` endpoint.
    *   [x] FE: Add `updateLineText` and `deleteVoScriptLine` functions to `api.ts`.
    *   [x] FE (`VoScriptDetailView.tsx`): Refactor line display from `<Stack>`/`<Paper>` to `<Table>`.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement editable `<Textarea>` for `generated_text` with state management.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement "Save" ActionIcon with mutation logic for `update-text`.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement "Delete" ActionIcon with confirmation and mutation logic for `delete line`.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement "Refine" ActionIcon and associated Modal.
    *   [x] FE (`VoScriptDetailView.tsx`): Connect Refine Modal submit to `refineLineMutation`.
    *   [x] FE (`VoScriptDetailView.tsx`): Add Lock/Unlock ActionIcon (connecting to mutation from Line Locking feature).
    *   [ ] Test: Write basic component tests for the new Table row / Modal interactions.
    *   [ ] Test: Manually test all actions in the new line table UI.
*   [x] **TODO: Feature - Add New Line**
    *   [x] BE: Add nullable `line_key`, `order_index`, `prompt_hint`, `category_id` (FK) columns to `vo_script_lines` table model (`models.py`).
    *   [x] BE: Make `template_line_id` nullable in `vo_script_lines` model.
    *   [x] BE: Generate Alembic migration (`flask db migrate -m "Add custom line fields to vo_script_lines"`).
    *   [x] BE: Review and apply migration (`flask db upgrade`).
    *   [x] BE: Implement `POST /api/vo-scripts/<script_id>/lines` endpoint logic (create line, find category ID by name).
    *   [x] BE: Write integration test for the `add line` endpoint.
    *   [x] FE: Add `addVoScriptLine` function to `api.ts`.
    *   [x] FE (`VoScriptDetailView.tsx`): Add "Add Line" button per category.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement Add Line Modal component with form.
    *   [x] FE (`VoScriptDetailView.tsx`): Implement state and mutation logic for adding a line.
    *   [x] FE (`VoScriptDetailView.tsx`): Update UI/cache on successful line addition.
    *   [ ] Test: Write basic component tests for Add Line Modal.
    *   [ ] Test: Manually test adding new lines.
*   [ ] **TODO: Feature - View/Revert Line History**
    *   [ ] FE (`VoScriptDetailView.tsx`): Add "View History" ActionIcon (`IconHistory`) to line actions group in the table.
    *   [ ] FE (`VoScriptDetailView.tsx`): Add state management for History Modal visibility and selected line data (`lineToViewHistory`).
    *   [ ] FE (`VoScriptDetailView.tsx`): Implement `handleOpenHistoryModal` function.
    *   [ ] FE (`VoScriptDetailView.tsx`): Create History Modal component structure.
    *   [ ] FE (`VoScriptDetailView.tsx`): Display history entries (timestamp, type, text) within the modal.
    *   [ ] FE (`VoScriptDetailView.tsx`): Add "Revert to this version" button for each history entry.
    *   [ ] FE (`VoScriptDetailView.tsx`): Connect "Revert" button `onClick` to call `handleSaveLineText` with the historical text.
    *   [ ] FE (`VoScriptDetailView.tsx`): Ensure modal closes on successful revert.
    *   [ ] Test: Write basic component tests for History Modal.
    *   [ ] Test: Manually test viewing history and reverting.
*   [ ] **TODO: Testing - End-to-End**
    *   [ ] Manually test line refinement flow with OpenAI API.
    *   [ ] Manually test category refinement flow with OpenAI API.
    *   [ ] Manually test script refinement flow with OpenAI API.
    *   [ ] Test edge cases (empty prompts, API errors, lines that shouldn't change).
    *   [ ] Test hierarchical prompt application.
*   [ ] **TODO: Documentation**
    *   [ ] Update `.cursor/notes/agentnotes.md` with the new architecture details.
    *   [ ] Update API documentation (if any exists) for new endpoints.

## Phase Z: Static Template Lines Feature

*   [x] Create Technical Specification (`.cursor/notes/static_template_lines_spec.md`).
*   [x] **TODO: Backend - Database Changes**
    *   [x] Add `static_text` column (Text, nullable) to `vo_script_template_lines` table model in `models.py`.
    *   [x] Generate Alembic migration (`flask db migrate -m "Add static_text to vo_script_template_lines"`).
    *   [x] Review and apply migration (`flask db upgrade`).
*   [x] **TODO: Backend - Create/Update Logic**
    *   [x] Modify `POST /api/vo-script-template-lines` endpoint in `vo_template_routes.py` to handle static_text field.
    *   [x] Modify `PUT /api/vo-script-template-lines/<line_id>` endpoint to handle static_text updates.
    *   [x] Update `create_vo_script` endpoint in `vo_script_routes.py` to copy static_text to generated_text for new lines.
    *   [x] Update `

## Phase 9: Modular Backend Refactoring Validation

### Code Review Checklist

* [x] **Review all refactored files for missing imports**
    * [x] Check `app.py` for missing imports (e.g., `datetime`)
    * [x] Check all `routes/*.py` files for proper imports
    * [x] Check all `tasks/*.py` files for proper imports
    * [x] Verify all imports are used (no unused imports)

* [x] **Check for circular import issues**
    * [x] Review import structure in `routes/*.py` files
    * [x] Review import structure in `tasks/*.py` files 
    * [x] Verify that imports from `tasks` in `routes` (and vice versa) don't create circular dependencies

* [x] **Verify consistent function signatures**
    * [x] Compare function signatures in new modules against original `tasks.py`
    * [x] Check parameter names, types, and default values
    * [x] Verify that no function parameters were missed during refactoring

* [x] **Test blueprint registration**
    * [x] Verify that all blueprints are properly registered in `app.py`
    * [x] Check URL prefixes match expected values
    * [x] Ensure route decorators are properly applied

* [x] **Verify error handling**
    * [x] Check for proper error handling in route functions
    * [x] Verify that error responses use consistent formats (via `make_api_response`)
    * [x] Test error cases to ensure they return appropriate status codes

### Testing Checklist

* [x] **Create unit tests for task modules**
    * [x] Test module imports to verify no import errors
    * [x] Test that task functions have expected signatures
    * [x] Verify task registry is properly populated

* [x] **Create tests for route blueprints**
    * [x] Verify blueprint registration
    * [x] Test URL prefixes
    * [x] Test route handler functions

* [x] **Implement end-to-end testing**
    * [x] Create test for full workflow using actual database
    * [x] Test script creation/generation workflow
    * [x] Test audio manipulation functions
    * [x] Test voice generation and regeneration

* [x] **Fix issues found during testing**
    * [x] Fix missing `datetime` import in `app.py`
    * [x] Fix test issue with blueprint URL prefixes
    * [x] Fix direct task call issue with Celery context

### Documentation and Finalization

* [x] **Update documentation**
    * [x] Document the new module structure in agent notes
    * [x] Update project checklist with completed tasks
    * [x] Document testing procedures for future reference

* [x] **Validation**
    * [x] Verify that all endpoints work as expected
    * [x] Test critical endpoints manually
    * [x] Ensure all tests pass

### Bug Fixes

* [x] **Fix for regeneration task status polling**
    * [x] Identified issue with snake_case vs camelCase naming mismatch when returning task IDs from backend
    * [x] Updated API functions (`regenerateLineTakes`, `startSpeechToSpeech`, `cropTake`, `getTaskStatus`, `triggerGenerateCategoryBatch`) to correctly map response fields
    * [x] Made TypeScript interfaces consistent with camelCase naming convention (`JobSubmissionResponse`, `GenerationStartResponse`, `TaskStatus`, `CropTakeResponse`)
    * [x] Restart containers to ensure all changes took effect
    * [x] Verified that regeneration functionality now works correctly