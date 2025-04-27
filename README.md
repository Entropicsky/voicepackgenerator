# AI Voice Pack Generator & Ranker

This project provides a web-based tool for:
1.  Generating multiple takes of voice lines using the ElevenLabs API based on an input script.
2.  Ranking the generated takes on a line-by-line basis to select the best options.
3.  **(New!)** Designing new voices directly from text prompts using the ElevenLabs Voice Design API.
4.  **(New!)** Managing scripts through a database with a full-featured editor and versioning.
5.  **(New!)** Cropping audio takes directly within the ranking interface.

Built with Flask (backend API), Celery (background tasks), Redis (task queue), React/TypeScript/Vite (frontend), **pydub** (audio processing), **WaveSurfer.js** (waveform display), and Docker Compose for environment management.

## Features

*   **Script Management:**
    *   Create, edit, and delete scripts through a web interface.
    *   Import scripts from CSV files.
    *   Archive/unarchive scripts to keep your workspace organized.
    *   Generate voice takes directly from saved scripts.
    *   Update script text when regenerating takes for improved iteration.
*   **Voice Design:**
    *   Create new ElevenLabs voices using text prompts and settings (loudness, quality, guidance).
    *   Generate multiple audio previews for a voice description.
    *   Iteratively "Hold" promising previews across generation batches.
    *   Save selected held previews directly to your ElevenLabs voice library.
*   **Batch Generation:**
    *   Select one or more ElevenLabs voices.
    *   Upload a CSV script or select from saved scripts.
    *   Configure number of takes per line and randomization ranges (Stability, Similarity, Style, Speed).
    *   Submit generation job to a background Celery worker.
*   **Job Tracking:**
    *   View history of submitted generation jobs.
    *   See live status updates polled from Celery/Database.
*   **Ranking & Editing:**
    *   View generated batches.
    *   Listen to takes line-by-line.
    *   Assign ranks (1-5) to takes within each line.
    *   Rank assignments automatically cascade within the line.
    *   Move ranked takes up/down or unrank/trash them directly from the ranked panel.
    *   **(New!)** Edit takes using an inline waveform editor:
        *   Visualize the audio waveform.
        *   Select start/end points using draggable regions.
        *   Preview the selected audio region.
        *   Save the crop, overwriting the original audio file in R2 via a background task.
    *   Download ranked batch audio.
    *   Lock completed batches.
*   **Line Regeneration/STS:**
    *   Regenerate specific lines using new TTS settings.
    *   Generate new takes using Speech-to-Speech (STS) from uploaded audio or microphone input.
    *   Update source scripts when regenerating takes to maintain text consistency.
    *   Track regeneration job status inline on the ranking page.

## Project Structure

```
.
├── backend/
│   ├── app.py            # Main Flask application
│   ├── models.py         # SQLAlchemy database models
│   ├── celery_app.py     # Celery application setup
│   ├── tasks.py          # Celery task definitions (generation, cropping, etc.)
│   ├── utils_elevenlabs.py # ElevenLabs API interactions
│   ├── utils_r2.py       # Cloudflare R2 interactions
│   ├── tests/            # Backend unit/integration tests
│   ├── Dockerfile        # Dockerfile for backend (used locally)
│   ├── requirements.txt  # Python dependencies
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React application layout (Header, Navbar, Routes)
│   │   ├── main.tsx        # React entry point
│   │   ├── api.ts          # Frontend API client functions
│   │   ├── types.ts        # TypeScript type definitions
│   │   ├── pages/          # Page components (Generation, Ranking, Scripts, etc.)
│   │   ├── components/     # Reusable UI components (Selectors, Forms, Modals, etc.)
│   │   ├── contexts/       # React Context providers (Voice, Ranking)
│   │   ├── hooks/          # Custom React hooks
│   │   └── assets/         # Static assets like images (if imported)
│   ├── public/
│   │   └── images/       # Static assets served directly (e.g., logo)
│   ├── Dockerfile        # Dockerfile for frontend (used locally for Nginx serving)
│   ├── package.json      # Frontend dependencies and scripts
│   ├── tsconfig.json     # TypeScript configuration
│   ├── vite.config.ts    # Vite build configuration
│   └── ...
├── migrations/         # Alembic database migration scripts
├── output/             # Default local location for generated audio batches (mounted into containers)
├── .cursor/            # Agent notes, docs, rules, tools
├── .github/            # GitHub specific files (e.g., workflows - if added)
├── .vscode/            # VSCode settings (if added)
├── Dockerfile          # Root Dockerfile (used by Heroku web dyno, runs Nginx/Gunicorn)
├── Dockerfile.worker   # Dockerfile for the Celery worker (used by Heroku worker dyno)
├── docker-compose.yml  # Docker Compose service definitions for local dev
├── heroku.yml          # Heroku build and deployment configuration
├── start.sh            # Script run by root Dockerfile for Heroku (starts Nginx/Gunicorn)
├── Makefile            # Helper commands (install, test, clean, etc.)
├── .env.example        # Example environment variables
├── .env                # Local environment variables (API keys, secrets - DO NOT COMMIT)
├── .gitignore          # Git ignore patterns
└── README.md           # This file
```

## Setup & Running (Docker Compose - Local Development)

This project uses Docker Compose for a consistent local development environment.

**Key Local Configuration Differences:**

*   **Database:** Uses a PostgreSQL database running in a dedicated `db` service container (`postgres:16-alpine`). Data persists locally in a Docker volume (`pgdata`). Connection is configured via `DATABASE_URL` in `docker-compose.yml`.
*   **Redis:** Uses a standard `redis:alpine` container. Data persists locally in a Docker volume (`redis_data`). Connection is configured via `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` in `.env` (typically `redis://redis:6379/0`).
*   **Nginx:** The `frontend` service uses a custom `entrypoint.sh` script to substitute `PORT=80` and `PROXY_UPSTREAM=http://backend:5000` into `nginx.template.conf` before starting Nginx.

**Steps:**

1.  **Prerequisites:**
    *   Docker Desktop installed and running.
    *   Git
    *   An ElevenLabs API Key.
    *   **(New!)** `ffmpeg` installed on your system (or ensure it's installed in the backend Docker image). `pydub` relies on it.

2.  **Clone the Repository:**
    ```bash
    git clone <repo-url>
    cd voicepackgenerator
    ```

3.  **Configure Local Environment:**
    *   Copy `env.example` to `.env`:
        ```bash
        cp env.example .env
        ```
    *   Edit `.env` and fill in the required values:
        *   `SECRET_KEY`: Generate a random string (e.g., `python3 -c 'import secrets; print(secrets.token_hex(16))'`).
        *   `ELEVENLABS_API_KEY`: Your actual API key from ElevenLabs.
        *   `R2_BUCKET_NAME`: Your Cloudflare R2 bucket name (e.g., `voicepackgenerator-dev`).
        *   `R2_ENDPOINT_URL`: Your R2 S3 endpoint (e.g., `https://<account_id>.r2.cloudflarestorage.com`).
        *   `R2_ACCESS_KEY_ID`: Your R2 Access Key ID.
        *   `R2_SECRET_ACCESS_KEY`: Your R2 Secret Access Key.
        *   `OPENAI_API_KEY`: Your OpenAI API Key (for AI Wizard / Script Agent).
        *   `OPENAI_MODEL`: OpenAI model for text optimization (e.g., `gpt-4o`). Defaults to `gpt-4o` if not set.
        *   `OPENAI_AGENT_MODEL`: OpenAI model for VO Script agent generation/refinement (e.g., `gpt-4o`). Defaults to `gpt-4o` if not set.
        *   Ensure `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set to `redis://redis:6379/0` (or your local Redis if configured differently).
        *   Ensure `DATABASE_URL` is set for the local Postgres container (e.g., `postgresql://postgres:password@db:5432/app`).

4.  **Build and Start Services:**
    *   From the project root directory, run:
        ```bash
        docker compose up --build -d
        ```
    *   The first build (especially after dependency changes) might take a few minutes. This will create the Postgres `db` container and apply database migrations if this is the first run.

5.  **Access the Application:**
    *   Open your web browser and navigate to `http://localhost:5173`.
    *   The Flask API is accessible directly at `http://localhost:5001`.

6.  **Database Migrations (Local):**
    *   Database schema changes are managed using Flask-Migrate and Alembic.
    *   To generate a new migration after changing `backend/models.py`:
        ```bash
        docker compose run --rm backend flask --app backend.app:app db migrate -m "Your migration message"
        ```
    *   To apply migrations to the local Postgres container:
        ```bash
        docker compose run --rm backend flask --app backend.app:app db upgrade
        ```

7.  **View Logs:**
    ```bash
    docker compose logs -f           # View logs for all services (follow)
    docker compose logs backend      # View logs for just the backend
    docker compose logs worker       # View logs for just the worker
    docker compose logs frontend     # View logs for the Nginx frontend proxy
    docker compose logs db           # View logs for the Postgres database
    ```

8.  **Stop Services:**
    ```bash
    docker compose down
    ```
    *   To also remove the Postgres (`pgdata`) and Redis (`redis_data`) volumes: `docker compose down -v`

## Heroku Deployment

Deployment to Heroku is managed via `heroku.yml` and uses Docker container builds.

**Key Heroku Configuration Differences:**

*   **Database:** Uses the provisioned Heroku Postgres addon. The connection string is automatically provided via the `DATABASE_URL` config var.
*   **Redis:** Uses the provisioned Heroku Redis addon. The connection string (usually `rediss://...`) is automatically provided via the `REDIS_URL` config var. The `backend/celery_app.py` detects the `rediss://` scheme and configures SSL accordingly (currently using `ssl_cert_reqs=ssl.CERT_NONE`).
*   **Web Dyno (`web`):** Builds using the root `Dockerfile`. Runs Nginx and Gunicorn *in the same container*. The `start.sh` script:
    *   Uses `envsubst` to substitute the Heroku-provided `$PORT` and `PROXY_UPSTREAM=http://127.0.0.1:5000` into `frontend/nginx.template.conf` creating `/etc/nginx/nginx.conf`.
    *   Starts Nginx, which then proxies `/api/` and `/audio/` requests to Gunicorn running on `127.0.0.1:5000`.
*   **Worker Dyno (`worker`):** Builds using `Dockerfile.worker`. Runs the Celery worker directly.
*   **Migrations:** The `release` phase in `heroku.yml` automatically runs `flask db upgrade` before new code is released, ensuring the Heroku Postgres database schema is up-to-date.
*   **Environment Variables:** Required variables like `SECRET_KEY`, `ELEVENLABS_API_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_AGENT_MODEL` must be set manually in the Heroku app's settings (Config Vars). `DATABASE_URL` and `REDIS_URL` are typically set automatically by the addons.
*   **(New!)** Ensure `ffmpeg` is included in the backend Docker buildpack or build process for Heroku if not using the exact same Dockerfile base.

**Deployment Steps:**

1.  Ensure changes are committed to Git.
2.  Run: `git push heroku master`

## Development

*   **Backend Changes:** Changes to Python files (`backend/`, `tasks.py`, etc.) should auto-reload the Flask dev server locally when using `docker compose up`. For the worker, restart it: `docker compose restart worker`.
*   **Frontend Changes:** Requires rebuilding the frontend image: `docker compose build frontend`, then recreating the container: `docker compose up -d --force-recreate frontend`.
*   **Database Schema Changes:** Modify models in `backend/models.py`, then generate and apply migrations using the `flask db` commands outlined in the local setup section.

## Known Issues

*   The Vite development server (`
*   **(New!)** Audio Editor rendering relies on `withinPortal={false}` workaround due to conflict between WaveSurfer and Mantine Modal portal. Styling is basic.

## Backlog / Future Features

*   Audio Cropping:
    *   Improve editor styling when rendered inline.
    *   Investigate/Fix Mantine Modal portal conflict.
    *   Add task polling/notifications for crop completion.
    *   Implement non-destructive cropping (save as new file + metadata update).
    *   Add Undo functionality.
    *   Add Volume Normalization/Fade options.
*   Testing Framework implementation.
*   Cloudflare Access Authentication (Requires Custom Domain).
*   Batch action improvements (e.g., bulk delete/archive).
*   More detailed job progress reporting.