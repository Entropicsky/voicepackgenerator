# AI Voice Pack Generator & Ranker

This project provides a web-based tool for:
1.  Generating multiple takes of voice lines using the ElevenLabs API based on an input script.
2.  Ranking the generated takes on a line-by-line basis to select the best options.
3.  **(New!)** Designing new voices directly from text prompts using the ElevenLabs Voice Design API.

Built with Flask (backend API), Celery (background tasks), Redis (task queue), React/TypeScript/Vite (frontend), and Docker Compose for environment management.

## Features

*   **Voice Design:**
    *   Create new ElevenLabs voices using text prompts and settings (loudness, quality, guidance).
    *   Generate multiple audio previews for a voice description.
    *   Iteratively "Hold" promising previews across generation batches.
    *   Save selected held previews directly to your ElevenLabs voice library.
*   **Batch Generation:**
    *   Select one or more ElevenLabs voices.
    *   Upload a CSV script (LineKey, Text).
    *   Configure number of takes per line and randomization ranges (Stability, Similarity, Style, Speed).
    *   Submit generation job to a background Celery worker.
*   **Job Tracking:**
    *   View history of submitted generation jobs.
    *   See live status updates polled from Celery/Database.
*   **Ranking:**
    *   View generated batches.
    *   Listen to takes line-by-line.
    *   Assign ranks (1-5) to takes within each line.
    *   Rank assignments automatically cascade within the line.
    *   Download ranked batch audio.
    *   Lock completed batches.
*   **Line Regeneration/STS:**
    *   Regenerate specific lines using new TTS settings.
    *   Generate new takes using Speech-to-Speech (STS) from uploaded audio or microphone input.
    *   Track regeneration job status inline on the ranking page.

## Project Structure

```
.
├── backend/            # Flask API, utilities, tests, Dockerfile
├── frontend/           # React frontend source, Dockerfile
├── output/             # Default location for generated audio batches (mounted into containers)
├── .cursor/            # Agent notes, docs, etc.
├── celery_app.py       # Celery app instance definition
├── tasks.py            # Celery task definitions (e.g., run_generation)
├── docker-compose.yml  # Docker Compose service definitions
├── Makefile            # Helper commands (install, test, clean - mainly for local use)
├── requirements.txt    # Root requirements (empty/optional, main ones in backend/)
├── package.json        # Root package (empty/optional, main ones in frontend/)
├── .env.example        # Example environment variables
├── .env                # Local environment variables (API keys, secrets - DO NOT COMMIT)
└── README.md           # This file
```

## Setup & Running (Docker Compose - Static Build)

1.  **Prerequisites:**
    *   Docker Desktop installed and running.
    *   Git
    *   An ElevenLabs API Key.

2.  **Clone the Repository:**
    ```bash
    git clone <repo-url>
    cd voicepackgenerator
    ```

3.  **Configure Environment:**
    *   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    *   Edit `.env` and fill in the required values:
        *   `SECRET_KEY`: Generate a random string (e.g., `python3 -c 'import secrets; print(secrets.token_hex(16))'`).
        *   `ELEVENLABS_API_KEY`: Your actual API key from ElevenLabs.
        *   Ensure `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are set to `redis://redis:6379/0`.

4.  **Build and Start Services:**
    *   From the project root directory, run:
        ```bash
        docker compose up --build -d
        ```
    *   `--build` ensures images are built (including the frontend static build) if they don't exist or if Dockerfiles have changed.
    *   `-d` runs the containers in detached mode (in the background).
    *   The first build might take a few minutes.

5.  **Access the Application:**
    *   Open your web browser and navigate to `http://localhost:5173`.
    *   The Flask API is accessible directly at `http://localhost:5001`.

6.  **View Logs:**
    ```bash
    docker compose logs -f           # View logs for all services (follow)
    docker compose logs backend      # View logs for just the backend
    docker compose logs worker       # View logs for just the worker
    docker compose logs frontend     # View logs for the Nginx frontend proxy
    ```

7.  **Stop Services:**
    ```bash
    docker compose down
    ```
    *   To also remove the Redis data volume: `docker compose down -v`

## Development

*   **Backend Changes:** Since the project root (`.`) is mounted into the `backend` and `worker` containers, changes to Python files in the `backend` directory, `celery_app.py`, or `tasks.py` should trigger auto-reloading (Flask dev server) or be picked up on the next task (Celery worker - restart worker `docker compose restart worker` for immediate effect).
*   **Frontend Changes (Static Build Workflow):**
    *   The local `./frontend` directory is **NOT** mounted into the running `frontend` container in this configuration.
    *   To see changes made to frontend code (React components, CSS, etc.):
        1.  Make your code edits locally in the `./frontend` directory.
        2.  Run `docker compose build frontend` in your terminal to rebuild the frontend image.
        3.  Run `docker compose up -d --force-recreate frontend` to restart the frontend container with the new image.
        4.  Hard refresh your browser (Cmd+Shift+R / Ctrl+Shift+R).
*   **Running Tests:** Execute tests inside the containers:
    ```bash
    # Run backend tests
    docker compose exec backend pytest

    # Run frontend tests (Requires dev dependencies - build image with dev stage if needed)
    # docker compose exec frontend npm run test # This might not work easily with static build
    # Consider running frontend tests locally: cd frontend && npm install && npm test
    ```
*   **Adding Dependencies:**
    *   Backend (Python): Add to `backend/requirements.txt`, then rebuild: `docker compose build backend`.
    *   Frontend (Node): Add to `frontend/package.json`, then rebuild: `docker compose build frontend`.

## Known Issues

*   The Vite development server (`npm run dev`) has shown instability and file-watching issues when run within Docker on macOS. The current static build configuration is a stable workaround.

## Key Technologies

*   **Backend:** Python, Flask, Celery
*   **Frontend:** React, TypeScript, Vite
*   **API:** ElevenLabs Text-to-Speech
*   **Task Queue:** Redis
*   **Environment:** Docker Compose 