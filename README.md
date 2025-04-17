# AI Voice Pack Generator & Ranker

This project provides a web-based tool for:
1.  Generating multiple takes of voice lines using the ElevenLabs API based on an input script.
2.  Ranking the generated takes on a line-by-line basis to select the best options.

Built with Flask (backend API), Celery (background tasks), Redis (task queue), React/TypeScript/Vite (frontend), and Docker Compose for environment management.

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

## Setup & Running (Docker Compose - Recommended)

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
        docker-compose up --build -d
        ```
    *   `--build` ensures images are built if they don't exist or if Dockerfiles have changed.
    *   `-d` runs the containers in detached mode (in the background).
    *   The first build might take a few minutes to download base images and install dependencies.

5.  **Access the Application:**
    *   Open your web browser and navigate to `http://localhost:5173`.
    *   The Flask API is accessible directly at `http://localhost:5001` (due to current port mapping).

6.  **View Logs:**
    ```bash
    docker-compose logs -f           # View logs for all services (follow)
    docker-compose logs backend      # View logs for just the backend
    docker-compose logs worker       # View logs for just the worker
    ```

7.  **Stop Services:**
    ```bash
    docker-compose down
    ```
    *   To also remove the Redis data volume: `docker-compose down -v`

## Development

*   **Code Changes:** Since the `backend` and `frontend` directories are mounted as volumes, code changes should be reflected automatically.
    *   The Flask development server (`backend` service) should auto-reload on Python file changes.
    *   The Vite development server (`frontend` service) supports Hot Module Replacement (HMR).
    *   Changes to `celery_app.py` or `tasks.py` might require restarting the `worker` service: `docker-compose restart worker`.
*   **Running Tests:** Execute tests inside the containers for consistency:
    ```bash
    # Run backend tests
    docker-compose exec backend pytest

    # Run frontend tests
    docker-compose exec frontend npm run test
    ```
*   **Adding Dependencies:**
    *   Backend (Python): Add to `backend/requirements.txt`, then rebuild the image: `docker-compose build backend`.
    *   Frontend (Node): Run `docker-compose exec frontend npm install <package-name>`.

## Key Technologies

*   **Backend:** Python, Flask, Celery
*   **Frontend:** React, TypeScript, Vite
*   **API:** ElevenLabs Text-to-Speech
*   **Task Queue:** Redis
*   **Environment:** Docker Compose 