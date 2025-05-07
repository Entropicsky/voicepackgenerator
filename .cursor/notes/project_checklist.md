# Project Checklist: AI Script Collaborator Chat

**Overall Status:** Phase 5 (Frontend Interaction Logic) & Chat History Persistence complete. Basic chat flow operational and robust. Ready for more advanced interaction patterns or deployment prep.

**Phase 1: Backend Foundation (DONE)**
- [X] Task 1: Define `ScriptNote` model & migration (`backend/models.py`) - DONE
- [X] Task 2: Define `ScriptCollaboratorAgent` (`backend/agents/script_collaborator_agent.py`) - DONE
- [X] Task 3: Define Celery task `run_script_collaborator_chat_task` (`backend/tasks/script_tasks.py`) - DONE (Includes DB history loading & saving)
- [X] Task 4: Basic Logging Setup (`backend/app.py`, task logger) - DONE
- [X] Task 5: Add `ChatMessageHistory` model & migration - DONE

**Phase 2: Agent Tools (DONE)**
- [X] Task 1: Implement `get_script_context` tool - DONE (Enhanced with template context)
- [X] Task 2: Implement `propose_script_modification` tool - DONE
- [X] Task 3: Implement `get_line_details` tool - DONE (Enhanced with context)
- [X] Task 4: Implement `add_to_scratchpad` tool - DONE
- [X] Task 5: Seed test data for tools (`seed_chat_test_data.py`) - DONE

**Phase 3: API Endpoints (DONE)**
- [X] Task 1: Implement `POST /api/vo-scripts/<script_id>/chat` endpoint (`backend/routes/vo_script_routes.py`) - DONE (Now uses DB history)
- [X] Task 2: Verify `GET /api/task/<task_id>/status` endpoint (`backend/routes/task_routes.py`) - DONE
- [X] Task 3: Implement `GET /api/vo-scripts/<script_id>/chat/history` endpoint - DONE

**Phase 4: Frontend UI Shell (DONE)**
- [X] Task 1: Create Chat FAB (`ChatFab.tsx`) - DONE
- [X] Task 2: Implement Chat UI container (`AppShell.Aside` via `ChatPanelContent` in `ChatDrawer.tsx`) - DONE
- [X] Task 3: Setup Zustand store (`chatStore.ts`) - DONE (Actions for history implemented)
- [X] Task 4: Implement API client functions (`api.ts`) - DONE (Including `getChatHistory`)

**Phase 5: Frontend Interaction Logic & History (DONE)**
- [X] Task 1: Implement message sending & display (`ChatPanelContent`) - DONE
- [X] Task 2: Implement polling for task results (`ChatPanelContent`) - DONE (Robustness improved)
- [X] Task 3: Display active proposals (`ChatPanelContent`) - DONE
- [X] Task 4: Implement proposal actions (Dismiss, Accept REPLACE_LINE) (`ChatPanelContent`) - DONE
- [X] Task 5: Implement inline editing for REPLACE_LINE proposals (`ChatPanelContent`) - DONE
- [X] Task 6: Display `line_key` on proposal cards - DONE
- [X] Task 7: Add "Accept All" functionality - DONE
- [X] Task 8: Sort proposals by `suggested_order_index` / `suggested_line_key` - DONE
- [X] Task 9: Implement Chat History Persistence (DB backend, API, Frontend Load/Display) - DONE
- [ ] Task 10: Implement actions for other proposal types (INSERT_*, NEW_LINE_*) - TODO

**Phase 6: Frontend Refinements (Partially Done)**
- [X] Task 1: Improve proposal card display (UI polish) - Addressed during Phase 5
- [X] Task 2: Enhance error handling and user feedback - Partially addressed with polling timeout
- [ ] Task 3: Handle scratchpad display/interaction - TODO
- [ ] Task 4: Visual indication of focused line/category in main script view? - TODO

**Phase 7: Advanced Agent Interactions & Context (TODO)**
- [ ] Task 1: Implement agent ability to propose INSERT_LINE_AFTER / INSERT_LINE_BEFORE / NEW_LINE_IN_CATEGORY modifications.
- [ ] Task 2: Implement agent ability to use `add_to_scratchpad` tool.
- [ ] Task 3: Enhance agent instructions/prompts for more proactivity and contextual depth.
- [ ] Task 4: Handle category-wide feedback/requests.

**NEW Phase: Agent-Staged Commits (In Progress)**
**Goal:** Refine interaction so agent stages changes (description, lines) for explicit user commit via UI buttons, improving UX and data refresh.

*Sub-Phase 1: Staged Character Description Updates (In Progress)*
    - [ ] **Backend Tool:**
        - [ ] Define Pydantic models: `StageCharacterDescriptionParams`, `StagedCharacterDescriptionData`, `StageCharacterDescriptionToolResponse`.
        - [ ] Implement `@function_tool def stage_character_description_update` in `script_collaborator_agent.py` (returns staged data, no DB write).
        - [ ] Register tool with `ScriptCollaboratorAgent`.
        - [ ] Update `AGENT_INSTRUCTIONS` for new tool.
    - [ ] **Celery Task (`run_script_collaborator_chat_task`):**
        - [ ] Detect `stage_character_description_update` tool output.
        - [ ] Add `staged_description_update: Optional[StagedCharacterDescriptionData]` to task result.
    - [ ] **Backend API (`vo_script_routes.py`):**
        - [ ] New Endpoint: `PATCH /api/vo-scripts/<script_id>/character-description` (accepts `{ new_description: str }`, updates DB).
    - [ ] **Frontend (`types.ts`):**
        - [ ] Add `StagedCharacterDescriptionData` interface.
        - [ ] Update `ChatTaskResult` to include `staged_description_update?: StagedCharacterDescriptionData;`.
    - [ ] **Frontend (`api.ts`):**
        - [ ] Add `api.commitCharacterDescription(scriptId, newDescription)` function (calls new PATCH endpoint).
    - [ ] **Frontend (`chatStore.ts`):**
        - [ ] Add state: `stagedDescriptionUpdate: StagedCharacterDescriptionData | null`.
        - [ ] Add actions: `setStagedDescriptionUpdate()`, `clearStagedDescriptionUpdate()`.
    - [ ] **Frontend (`ChatPanelContent.tsx`):**
        - [ ] Polling logic: If `successInfo.staged_description_update` present, call `setStagedDescriptionUpdate`.
        - [ ] UI: Render "Commit Character Description" card/button if `stagedDescriptionUpdate` is present.
        - [ ] Logic: "Commit" button calls `api.commitCharacterDescription`, invalidates `voScriptDetail` query, clears staged update.
        - [ ] Logic: "Dismiss" button clears staged update.

*Sub-Phase 2: Staged Line Modifications (In Progress)*
    - [X] Adapt staging pattern for `propose_script_modification` tool (created `propose_multiple_line_modifications` tool) - Backend Done
    - [X] Update Celery task to handle staged line proposals from batch tool - Backend Done
    - [ ] Frontend to display staged line proposals with commit/dismiss options - TODO
    - [ ] Commit action calls existing line update/creation API endpoints - TODO (Frontend part)

**Phase 8: Testing & Deployment (TODO)**
- [ ] Task 1: Write comprehensive frontend tests (unit, integration).
- [ ] Task 2: Write comprehensive backend tests (unit, integration).
- [ ] Task 3: Manual end-to-end testing.
- [ ] Task 4: Prepare for Heroku deployment.
- [ ] Task 5: Deployment to staging/production.

**Resilience Notes:**
- Added frontend polling timeout (`MAX_POLLING_ATTEMPTS`) as a user-facing safeguard.
- Backend OpenAI client resilience (timeout/retries) uses library defaults; explicit configuration attempts with `openai-agents` SDK were unsuccessful. Deferred.

**Known Issues/Debugging Notes (Resolved):**
- Initial `openai-agents` tool decorator was `@tool`, needed `@function_tool`.
- Pydantic `Field` constraints caused OpenAI tool schema parsing issues.
- Celery task import/logging issues.
- Flask `db upgrade` issues (Docker exec path, stamping revisions).
- Frontend modal display ("blank page") fixed using `AppModal`, then refactored to `AppShell.Aside`.
- Multiple proposals display logic fixed in Celery task.
- Agent init `TypeError` loop (`max_retries`, `client` args).
- `Runner.run_sync` `TypeError` (`messages` keyword).
- Frontend blank screen due to history fetching (`setChatDisplayHistory` in store, `useEffect` dependencies).

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

## Phase 6: Chat UI Refactor - Docked Panel (Post-MVP UX Improvement)

**Goal:** Improve usability by changing the chat interface from a modal to a docked panel/drawer that allows viewing script content simultaneously.

1.  **Task: Research & Decide on Mantine Component**
    *   **Sub-Tasks:**
        *   Evaluate Mantine `Drawer` vs. modifying `AppShell` to include a right-hand toggleable section. (Decision: `AppShell.Aside`)
        *   Consider implications for responsiveness and content shifting.
    *   **Status:** `DONE`

2.  **Task: Refactor `ChatModal.tsx` (or create `ChatDrawer.tsx`)**
    *   **Sub-Tasks:**
        *   Adapt existing chat UI elements (history, input, buttons) to fit the chosen Drawer/Panel component. (Status: `DONE` - Content moved to `ChatPanelContent`)
        *   Ensure styling and layout are appropriate for a docked view.
    *   **Status:** `DONE`

3.  **Task: Integrate Docked Chat Panel into Main Layout**
    *   **Sub-Tasks:**
        *   Modify `AppLayout.tsx` (`App.tsx`) to correctly render and manage the docked panel using `AppShell.Aside`. (Status: `DONE`)
        *   Ensure the main content area adjusts or allows overlay without full dimming, so script lines are visible. (Status: `DONE` - Main content resizes)
        *   Update `ChatFab.tsx` or chat-opening logic to control the new docked panel. (Status: `DONE` - FAB opens, close button in panel closes)
    *   **Status:** `DONE`

4.  **Task: Testing and Refinement**
    *   **Sub-Tasks:**
        *   Test chat functionality thoroughly in the new docked view. (Status: `DONE` - Basic functionality confirmed)
        *   Test responsiveness across different screen sizes. (Status: `Pending`)
        *   Gather feedback and make necessary UX adjustments. (Status: `In Progress`)
    *   **Status:** `In Progress`

## Phase 7: Advanced Agent Interactions & Context (Post-Docked Panel)

**Goal:** Enhance agent to proactively gather context, handle multi-line/category feedback, propose changes to character descriptions, and maintain conversational memory, making interaction more human-like.

1.  **Task: Enhance Agent Proactive Context Gathering, Conversational Memory & Richness**
    *   **Sub-Tasks:**
        *   **1.1 (Context Richness):** Modify `get_script_context` tool & `ScriptContextResponse`/`LineDetail` Pydantic models to fetch and return `template_global_hint`, `category_prompt_instructions`, and `template_line_prompt_hint`. (Status: `Pending`)
        *   **1.2 (Context Richness):** Modify `get_line_details` tool & `VoScriptLineFullDetail` Pydantic model to include `template_line_prompt_hint`. (Status: `Pending`)
        *   **1.3 (Conversational Memory):** Modify `run_script_collaborator_chat_task` (in `backend/tasks/script_tasks.py`) to construct the input for `Runner.run_sync` by combining `initial_prompt_context_from_prior_sessions` with the current `user_message` into a list of messages. (Status: `Pending`)
        *   **1.4 (Agent Guidance):** Refine `AGENT_INSTRUCTIONS` to explicitly guide the agent to:
            *   Utilize all newly available template context fields.
            *   Proactively use context-fetching tools before answering or proposing.
            *   Maintain conversational memory based on provided history.
            *   Ask clarifying questions when appropriate.
            *   Proactively offer suggestions.
        *   **1.5 (Tool Descriptions):** Review and refine all tool descriptions for optimal clarity to the LLM.
    *   **Status:** `Pending`
    *   **Testing:** Observe agent behavior with various queries; check if it correctly uses conversation history, calls context tools, and if its responses/proposals reflect richer template context and improved proactivity.

2.  **Task: Implement Multi-Proposal Handling (Category/Batch Refinement)**
    *   **Sub-Tasks:**
        *   Backend: Ensure agent can make multiple `propose_script_modification` calls in one turn if refining a category based on general feedback. (Agent SDK supports this; depends on LLM prompting).
        *   Frontend: Ensure `ChatPanelContent` can display multiple `activeProposals` cards gracefully. (Current map should handle it).
        *   Frontend: Add UI for "Accept All Visible Proposals" or similar batch actions (optional for first pass).
    *   **Status:** `Pending`

3.  **Task: Implement Character Description Update Tool & Flow**
    *   **Sub-Tasks:**
        *   Backend: Create new tool `propose_character_description_update(script_id: int, new_description: str, reasoning: Optional[str])` in `script_collaborator_agent.py`. It returns a structured proposal.
        *   Backend: Register this tool with `ScriptCollaboratorAgent`.
        *   Frontend: Add Pydantic models for this new proposal type in `types.ts`.
        *   Frontend: Update `ChatPanelContent` to render character description proposals (distinct UI card).
        *   Frontend: Implement "Accept & Commit" for description proposals, calling `api.updateVoScript`.
        *   Backend: Update `AGENT_INSTRUCTIONS` to guide agent on when to use this tool.
    *   **Status:** `Pending`

4.  **Task: Enhance New Line Proposals with Key/Order Suggestions & Implement "Accept"**
    *   **Sub-Tasks:**
        *   Backend: `propose_script_modification` tool already accepts `suggested_line_key` and `suggested_order_index`. Ensure agent instructions guide the LLM to provide these when `modification_type` is `INSERT_LINE_AFTER`, `INSERT_LINE_BEFORE`, or `NEW_LINE_IN_CATEGORY`.
        *   Frontend: Implement `addVoScriptLineMutation` in `ChatPanelContent.tsx`.
        *   Frontend: Implement "Accept & Commit" for `INSERT_LINE_AFTER`, `INSERT_LINE_BEFORE`, `NEW_LINE_IN_CATEGORY` modification types in `handleAcceptProposal`. This will involve:
            *   Using `suggested_line_key` (or generating one if missing).
            *   Calculating the correct `order_index` based on `target_id` and type (e.g., after target line, end of category).
            *   Getting `category_name` if `target_id` is a category_id or if needed for line insertion.
            *   Calling the `addVoScriptLineMutation`.
    *   **Status:** `Pending`

## Phase 8: End-to-End Testing & Refinement (Adjusted phase number)

**Goal:** Thoroughly test the entire feature workflow with realistic data and refine based on findings.

1.  **Task: Comprehensive E2E Testing**
    *   **Sub-Tasks:**
        *   Create diverse test scripts and scenarios in the dev database (e.g., empty scripts, scripts with many lines, different categories).
        *   Test all chat functionalities: initiating chat, sending various queries to trigger different tools, handling proposals, using scratchpad.
        *   Test edge cases: network errors during polling, API errors from backend, invalid user inputs.
        *   Verify context awareness (chatting about specific line vs. category vs. whole script).
    *   **Status:** `Pending`
    *   **Testing Strategy/Steps:**
        *   Manually execute test scenarios as a user would.
        *   Use browser dev tools and backend logs extensively.

2.  **Task: UI/UX Review and Refinement**
    *   **Sub-Tasks:**
        *   Review chat flow, clarity of proposals, ease of committing/dismissing.
        *   Address any awkward interactions or visual glitches.
    *   **Status:** `Pending`

## Phase 9: Documentation Updates (Adjusted phase number)

**Goal:** Ensure any necessary documentation is updated.

1.  **Task: Update Internal Documentation**
    *   **Sub-Tasks:**
        *   Update `agentnotes.md` with details about the new agent, tools, and API endpoints.
        *   Ensure code comments are thorough.
    *   **Status:** `Pending`

2.  **Task: User-Facing Documentation (if applicable)**
    *   **Sub-Tasks:**
        *   If needed, create a brief guide for game designers on how to use the new chat feature.
    *   **Status:** `Pending`

## Feature: AI Script Collaborator Chat (Side Car)

**Tech Spec:** [.cursor/docs/ai_script_collaborator_chat_spec.md](mdc:.cursor/docs/ai_script_collaborator_chat_spec.md)

**Overall Goal:** Implement an iterative, conversational chat interface for script refinement as a "side car" feature, augmenting existing functionalities.

--- 

### Phase 1: Backend Setup & Core Agent Infrastructure

**Goal:** Establish the foundational backend components, including database models, the basic agent structure, and asynchronous task execution.

1.  **Task: Define and Implement `ScriptNote` Database Model**
    *   **Sub-Tasks:**
        *   Define `ScriptNote` SQLAlchemy model in `backend/models.py`: (Status: `DONE`)
            *   `id` (PK, Integer)
            *   `vo_script_id` (FK to `vo_scripts.id`, Integer, Nullable=False, index=True)
            *   `category_id` (FK to `vo_script_template_categories.id`, Integer, Nullable=True, index=True)
            *   `line_id` (FK to `vo_script_lines.id`, Integer, Nullable=True, index=True)
            *   `title` (String(255), Nullable=True)
            *   `text_content` (Text, Nullable=False)
            *   `created_at` (DateTime, server_default=func.now())
            *   `updated_at` (DateTime, server_default=func.now(), onupdate=func.now())
        *   Generate Alembic migration script for `ScriptNote`. (Status: `DONE`)
        *   Apply migration to the development database. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   Verify table creation in the dev database using a DB tool or `psql`. (Status: `DONE (Verified via psql)`)
        *   Manually insert a sample `ScriptNote` record and verify. (Status: `Deferred (will be tested with 'add_to_scratchpad' tool implementation, vo_scripts table currently empty)`)
        *   `Terminal Command (Example for applying migration): alembic upgrade head` (Actual command used: `docker-compose exec backend env FLASK_APP=backend.app flask db upgrade`)

2.  **Task: Basic `ScriptCollaboratorAgent` Definition**
    *   **Sub-Tasks:**
        *   Create a new file, e.g., `backend/agents/script_collaborator_agent.py`. (Status: `DONE`)
        *   Define the `ScriptCollaboratorAgent` class using `agents.Agent` from the OpenAI Agents SDK. (Status: `DONE`)
        *   Implement initial agent instructions (system prompt) as per the tech spec. (Status: `DONE`)
        *   Initialize the agent with a model (e.g., `gpt-4o`). (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   Instantiate the agent in a Python shell/script (locally, not via API yet). (Status: `DONE`)
        *   Attempt a simple interaction using `Runner.run_sync(agent, "Hello")` to ensure it responds based on its instructions (without tools yet). (Status: `DONE`)

3.  **Task: Celery Task for Agent Execution**
    *   **Sub-Tasks:**
        *   Define a new Celery task in `backend/tasks/script_tasks.py` (e.g., `run_script_collaborator_chat_task`). (Status: `DONE`)
        *   This task will take `user_message`, `initial_prompt_context_from_prior_sessions`, `current_context`, and `script_id` as arguments. (Status: `DONE`)
        *   Inside the task, instantiate `ScriptCollaboratorAgent`. (Status: `DONE`)
        *   Call `Runner.run_sync(agent, combined_prompt)` where `combined_prompt` is constructed from user message and context. (Status: `DONE`)
        *   The task should return the structured response (AI text, proposals, etc.) as defined in the tech spec. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   Trigger the Celery task directly from a Python script with mock data. (Status: `DONE`)
        *   Verify the task executes and returns a response (even if basic, as tools aren't implemented yet). (Status: `DONE`)
        *   Check Celery worker logs for execution and any errors. (Status: `DONE`)

4.  **Task: MVP Logging Setup**
    *   **Sub-Tasks:**
        *   Ensure basic logging is configured for the backend application. (Status: `DONE` - Verified in `app.py`)
        *   Add specific log points for Celery task initiation/completion/errors. (Status: `DONE` - Implemented in `run_script_collaborator_chat_task`)
        *   Add logging for API requests for this feature. (Status: `Pending` - To be done in Phase 3)
        *   Add logging for agent/tool errors. (Status: `Pending` - To be done in Phase 2)
    *   **Status:** `In Progress` (Core Celery task logging done)
    *   **Testing Strategy/Steps:**
        *   Trigger relevant actions (API calls, task execution) and verify logs are generated with expected information. (Status: `Partially DONE` - Celery task logs verified)

--- 

### Phase 2: Agent Tool Implementation & Testing

**Goal:** Implement and test each of the four agent tools with robust Pydantic models and input validation.

1.  **Task: Implement `get_script_context` Tool**
    *   **Sub-Tasks:**
        *   Define Pydantic models for parameters and return type. (Status: `DONE`)
        *   Implement the tool logic in `backend/agents/script_collaborator_agent.py`. (Status: `DONE`)
        *   Function should query the database for `VoScript`, `VoScriptTemplateCategory`, `VoScriptLine` based on inputs. (Status: `DONE`)
        *   Include input validation (e.g., ensuring IDs are valid integers). (Status: `DONE` - Basic validation via Pydantic types, internal logic for num_surrounding)
        *   Register the tool with the `ScriptCollaboratorAgent`. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   **Unit Tests:** Test the tool function directly with mock database sessions/data, covering various scenarios (script only, with category, with line, line with surrounding lines, invalid IDs). (Status: `Pending` - More formal unit tests can be added)
        *   **Integration Tests:** Create sample `VoScript` data in the dev database. Run the Celery task with the agent configured to use this tool, and craft a prompt that *should* invoke `get_script_context`. Verify the agent receives correct context from the database. (Status: `DONE` - Tested via direct agent script execution with seeded DB data. Celery task integration is later.)

2.  **Task: Implement `propose_script_modification` Tool**
    *   **Sub-Tasks:**
        *   Define Pydantic models for parameters (including `modification_type` as an Enum if possible, `new_text` with max length) and return type. (Status: `DONE`)
        *   Implement tool logic. This tool *does not* modify the DB; it returns a structured proposal. (Status: `DONE`)
        *   Input validation (max lengths, valid IDs, valid `modification_type`). (Status: `DONE` - Basic validation in tool logic for required text; Pydantic handles type validation and `max_length` removed due to schema issues, will rely on LLM and agent prompt for now)
        *   Register tool with the agent. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   **Unit Tests:** Test the tool function directly, ensuring it correctly structures the proposal based on different inputs and validates parameters. (Status: `Pending` - More formal unit tests can be added)
        *   **Integration Tests:** Create sample `VoScript` data in the dev database. Run Celery task with agent, prompt it to suggest a change to a line. Verify the agent calls the tool and the task returns a correctly structured `proposed_modifications` object. (Status: `DONE` - Tested via direct agent script execution with seeded DB data. Celery task integration is later.)

3.  **Task: Implement `get_line_details` Tool**
    *   **Sub-Tasks:**
        *   Define Pydantic models for parameters and return type (mapping to `VoScriptLine` fields). (Status: `DONE`)
        *   Implement tool logic to fetch a specific `VoScriptLine` by ID. (Status: `DONE`)
        *   Input validation. (Status: `DONE` - Pydantic handles ID type; DB query handles existence)
        *   Register tool with the agent. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   **Unit Tests:** Mock DB session, test fetching existing and non-existing lines. (Status: `Pending` - More formal unit tests can be added)
        *   **Integration Tests:** Create `VoScriptLine` data. Run Celery task with agent, prompt it to get details for a line. Verify correct data is returned in the agent's response (via the tool). (Status: `DONE` - Tested via direct agent script execution with seeded DB data. Celery task integration is later.)

4.  **Task: Implement `add_to_scratchpad` Tool**
    *   **Sub-Tasks:**
        *   Define Pydantic models for parameters (with max lengths for text fields) and return type. (Status: `DONE`)
        *   Implement tool logic to create and save a `ScriptNote` record in the database. (Status: `DONE`)
        *   Input validation. (Status: `DONE` - Pydantic for types, internal logic for ID/type validation)
        *   Register tool with the agent. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   **Unit Tests:** Mock DB session, test `ScriptNote` creation logic and parameter validation. (Status: `Pending` - More formal unit tests can be added)
        *   **Integration Tests:** Run Celery task with agent, prompt it to save a note. Verify a `ScriptNote` record is created in the dev database with correct content and associations. (Status: `DONE` - Tested via direct agent script execution & psql verification. Celery task integration is later.)

--- 

### Phase 3: API Endpoint Implementation & Testing

**Goal:** Implement and test the API endpoints for initiating chat and checking task status.

1.  **Task: Implement `POST /api/scripts/<script_id>/chat` Endpoint**
    *   **Sub-Tasks:**
        *   Create the Flask route in `backend/routes/vo_script_routes.py`. (Status: `DONE`)
        *   Validate `script_id` and request body (using Pydantic model). (Status: `DONE`)
        *   Extract `user_message`, `initial_prompt_context_from_prior_sessions`, `current_context`. (Status: `DONE`)
        *   Call the Celery task (`run_script_collaborator_chat_task.delay(...)`) with these parameters. (Status: `DONE`)
        *   Return the Celery `task_id` in the response. (Status: `DONE`)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   Use an API client (Python script `test_chat_api.py`) to send POST requests to the endpoint with valid and invalid data. (Status: `DONE`)
        *   Verify a Celery task is enqueued (check Celery logs/monitoring). (Status: `DONE`)
        *   Verify the API returns a `202 OK` with a `task_id` for valid requests. (Status: `DONE`)
        *   Verify appropriate error responses (e.g., 400, 404) for invalid inputs. (Status: `DONE`)

2.  **Task: Implement Task Status Endpoint (e.g., `GET /api/chat-task-status/<task_id>`)**
    *   **Sub-Tasks:**
        *   Create the Flask route. (Status: `DONE` - Existing `/api/task/<task_id>/status` in `task_routes.py` is used)
        *   Query Celery for the status of the given `task_id`. (Status: `DONE` - Handled by existing endpoint)
        *   If task is `SUCCESS`, return the task result. (Status: `DONE` - Handled by existing endpoint)
        *   If task is `PENDING` or `STARTED`, return a status indicating it's still processing. (Status: `DONE` - Handled by existing endpoint)
        *   If task is `FAILURE`, return an error status and relevant error information. (Status: `DONE` - Handled by existing endpoint)
    *   **Status:** `DONE`
    *   **Testing Strategy/Steps:**
        *   After successfully calling the chat initiation endpoint, use the returned `task_id` to poll this status endpoint. (Status: `DONE` - Via `test_chat_api.py`)
        *   Simulate different task states (e.g., by adding delays or controlled failures in the Celery task for testing purposes). (Status: `Pending` - SUCCESS path tested; PENDING/FAILURE can be tested more explicitly if needed)
        *   Verify the endpoint returns correct status and data for `PENDING`, `SUCCESS`, and `FAILURE` states. (Status: `Partially DONE` - SUCCESS path verified)
        *   Test with invalid `task_id`. (Status: `Pending` - Can be added to `test_chat_api.py`)

--- 

### Phase 4: Frontend - Proposal Handling

**Goal:** Enable the frontend to understand and display structured "proposed modifications" from the AI, and allow the user to "Accept & Commit", "Edit & Commit", or "Dismiss" these proposals.

1.  **Task: Define Frontend Types for Proposals**
    *   **Sub-Tasks:**
        *   Define `ProposedModificationDetail` interface and `ModificationType` enum in `frontend/src/types.ts`. (Status: `DONE`)
        *   Update `ChatTaskResult` in `types.ts` to use `ProposedModificationDetail[]`. (Status: `DONE`)
    *   **Status:** `DONE`

2.  **Task: Update `ChatModal.tsx` to Handle and Display Proposals**
    *   **Sub-Tasks:**
        *   Store Active Proposals: Add `activeProposals` state and actions (`setActiveProposals`, `removeProposal`, `clearActiveProposals`) to `chatStore.ts`. (Status: `DONE`)
        *   Parse Proposals: In `ChatModal.tsx` polling logic, extract `proposed_modifications` from successful task results and call `setActiveProposals`. (Status: `DONE`)
        *   Render Proposals: In `ChatPanelContent` (formerly ChatModal.tsx), if `activeProposals` is not empty, map over it and render each proposal in a distinct card, showing type, target, new text, reasoning. (Status: `DONE`)
        *   Add placeholder action buttons ("Accept", "Edit", "Dismiss") to each proposal card. (Status: `DONE`)
    *   **Status:** `DONE (Display and placeholder actions implemented)

3.  **Task: Implement "Accept & Commit" Logic**
    *   **Sub-Tasks:**
        *   Define API client function in `api.ts` to update/create script lines (Status: `DONE` - `api.updateLineText` used, `api.addVoScriptLine` exists for future use).
        *   Implement `handleAcceptProposal` in `ChatPanelContent` for `REPLACE_LINE`. (Status: `DONE`)
        *   On success: Invalidate React Query cache for `voScriptDetail`, call `removeProposal(proposal.proposal_id)`, show success notification. (Status: `DONE`)
        *   Handle API errors with notifications. (Status: `DONE`)
        *   Implement logic for `INSERT_LINE_AFTER`, `INSERT_LINE_BEFORE`, `NEW_LINE_IN_CATEGORY`. (Status: `Pending` - Requires agent to suggest key/order, and frontend to use `addVoScriptLine` mutation)
    *   **Status:** `Partially DONE` (REPLACE_LINE implemented and working)
    *   **Testing Strategy/Steps:**
        *   Test `REPLACE_LINE` (Status: `DONE` - Functionally working)

4.  **Task: Implement "Dismiss" Logic**
    *   **Sub-Tasks:**
        *   Implement `handleDismissProposal` in `ChatPanelContent` to call `removeProposal(proposal.proposal_id)` from the store. (Status: `DONE`)
        *   Show confirmation notification. (Status: `DONE`)
    *   **Status:** `DONE`

5.  **Task: Implement "Edit & Commit" Logic (MVP - Simple Text Edit)**
    *   **Sub-Tasks:**
        *   When "Edit" is clicked, allow inline editing of `new_text` in proposal card. (Status: `DONE`)
        *   Show "Save Edit" and "Cancel Edit" buttons. (Status: `DONE`)
        *   "Save Edit": Use edited text and call `handleAcceptProposal`. (Status: `DONE`)
        *   "Cancel Edit": Revert UI. (Status: `DONE`)
    *   **Status:** `DONE (Pending User E2E Verification)` 
    *   **Testing Strategy/Steps:**
        *   User to test UI flow: AI proposes `REPLACE_LINE` -> Click Edit -> Modify text -> Click Save Edit -> Verify correct text is committed and UI updates. (Status: `Pending - User Verification`)

--- 

### Phase 5: Streaming Investigation & Implementation (MVP Stretch Goal)

**Goal:** If feasible for MVP, implement real-time streaming of AI responses.

1.  **Task: Investigate Agents SDK Streaming Capabilities**
    *   **Sub-Tasks:**
        *   Research if/how the OpenAI Agents SDK `Runner` can yield streamed events/tokens.
    *   **Status:** `Pending`

2.  **Task: Backend Changes for Streaming (if feasible)**
    *   **Sub-Tasks:**
        *   Modify Celery task and Flask endpoint to handle/forward a stream (e.g., using SSE).
    *   **Status:** `Pending`

3.  **Task: Frontend Changes for Streaming (if feasible)**
    *   **Sub-Tasks:**
        *   Update API client and UI to consume SSE/WebSocket stream and render tokens incrementally.
    *   **Status:** `Pending`
    *   **Testing Strategy/Steps:**
        *   If implemented, test streaming from end-to-end. Verify tokens appear in near real-time.

--- 

### Phase 6: End-to-End Testing & Refinement (Adjusted phase number)

**Goal:** Thoroughly test the entire feature workflow with realistic data and refine based on findings.

1.  **Task: Comprehensive E2E Testing**
    *   **Sub-Tasks:**
        *   Create diverse test scripts and scenarios in the dev database (e.g., empty scripts, scripts with many lines, different categories).
        *   Test all chat functionalities: initiating chat, sending various queries to trigger different tools, handling proposals, using scratchpad.
        *   Test edge cases: network errors during polling, API errors from backend, invalid user inputs.
        *   Verify context awareness (chatting about specific line vs. category vs. whole script).
    *   **Status:** `Pending`
    *   **Testing Strategy/Steps:**
        *   Manually execute test scenarios as a user would.
        *   Use browser dev tools and backend logs extensively.

2.  **Task: UI/UX Review and Refinement**
    *   **Sub-Tasks:**
        *   Review chat flow, clarity of proposals, ease of committing/dismissing.
        *   Address any awkward interactions or visual glitches.
    *   **Status:** `Pending`

--- 

### Phase 7: Documentation Updates (Adjusted phase number)

**Goal:** Ensure any necessary documentation is updated.

1.  **Task: Update Internal Documentation**
    *   **Sub-Tasks:**
        *   Update `agentnotes.md` with details about the new agent, tools, and API endpoints.
        *   Ensure code comments are thorough.
    *   **Status:** `Pending`

2.  **Task: User-Facing Documentation (if applicable)**
    *   **Sub-Tasks:**
        *   If needed, create a brief guide for game designers on how to use the new chat feature.
    *   **Status:** `Pending`

---