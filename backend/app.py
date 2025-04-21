# backend/app.py
from flask import Flask, jsonify, request, current_app, Response, redirect, send_file
from dotenv import load_dotenv
import os
from celery.result import AsyncResult
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
import zipfile
import io
import base64
from sqlalchemy import func, Boolean
import csv
from flask_migrate import Migrate
import time # For timing
import logging # For better logging
from werkzeug.middleware.proxy_fix import ProxyFix
import urllib.parse # Added for URL encoding/decoding
from typing import Dict

# Import celery app instance from root
from backend.celery_app import celery
# Import tasks from root
from backend import tasks
# Import utils from backend package
from . import utils_elevenlabs
from . import utils_r2 # Added utils_r2
from . import models # Import the models module

# Standard preview text
VOICE_PREVIEW_TEXT = "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal."

# Load environment variables from .env file for local development
# Within Docker, env vars are passed by docker-compose
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Add ProxyFix middleware to handle X-Forwarded-* headers correctly
# Trust 2 proxies (Heroku Router + Nginx Web Dyno)
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=2, x_proto=1, x_host=1, x_prefix=1
)

# Initialize Flask-Migrate
# Ensure the database engine is available
migrate = Migrate(app, models.engine) # Pass the SQLAlchemy engine from models.py

# Initialize Database
try:
    models.init_db()
except Exception as e:
    # Log the error but allow app to continue if possible?
    # Or should failure to init DB be fatal?
    print(f"CRITICAL: Database initialization failed: {e}")
    # Depending on requirements, might exit here: sys.exit(1)

# Configure CORS if needed, for example:
# from flask_cors import CORS
# CORS(app) # Allow all origins

# Example: Access an env var
print(f"Flask App: ELEVENLABS_API_KEY loaded? {'Yes' if os.getenv('ELEVENLABS_API_KEY') else 'No'}")

# --- Helper Function --- #
def make_api_response(data: dict = None, error: str = None, status_code: int = 200) -> Response:
    if error:
        response_data = {"error": error}
        status_code = status_code if status_code >= 400 else 500
    else:
        response_data = {"data": data if data is not None else {}}
    return jsonify(response_data), status_code

# --- API Endpoints --- #

@app.route('/api/ping')
def ping():
    print("Received request for /api/ping")
    return make_api_response(data={"message": "pong from Flask!"})

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Endpoint to get available voices, supports filtering/sorting."""
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    voice_type = request.args.get('voice_type', None)
    sort = request.args.get('sort', None)
    sort_direction = request.args.get('sort_direction', None)
    next_page_token = request.args.get('next_page_token', None)
    print(f"API Route /api/voices received search='{search}'")

    try:
        voices = utils_elevenlabs.get_available_voices(
            search=search,
            category=category,
            voice_type=voice_type,
            sort=sort,
            sort_direction=sort_direction,
            next_page_token=next_page_token
        )
        # V2 response includes more details, potentially filter/map here if needed
        # For now, return the full voice objects from V2
        return make_api_response(data=voices)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching voices via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/voices route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

@app.route('/api/generate', methods=['POST'])
def start_generation():
    """Endpoint to start an asynchronous generation task and record it."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    config_data = request.get_json()
    # config_data_json = json.dumps(config_data) # Store later after validation

    # --- MODIFIED: Script Source Validation --- 
    script_csv_content = config_data.get('script_csv_content')
    script_id = config_data.get('script_id')
    script_source_info = {}

    if script_id is not None and script_csv_content is not None:
        return make_api_response(error="Provide either 'script_id' or 'script_csv_content', not both.", status_code=400)
    elif script_id is None and script_csv_content is None:
        return make_api_response(error="Missing required script input: provide either 'script_id' or 'script_csv_content'.", status_code=400)
    elif script_id is not None:
        # Validate script_id is an integer and exists
        try:
            script_id = int(script_id)
            db: Session = next(models.get_db()) # Need DB context here for validation
            script = db.query(models.Script).get(script_id)
            if not script:
                 db.close()
                 return make_api_response(error=f"Script with ID {script_id} not found.", status_code=404)
            script_source_info = {"source_type": "db", "script_id": script_id, "script_name": script.name}
            print(f"Using script ID {script_id} ('{script.name}') for generation.")
            db.close() # Close session after validation
        except ValueError:
            return make_api_response(error="Invalid script_id format, must be an integer.", status_code=400)
        except Exception as e:
            if 'db' in locals() and db.is_active: db.close()
            print(f"Error validating script_id {script_id}: {e}")
            return make_api_response(error="Failed to validate script ID", status_code=500)
        # Remove script_csv_content from config_data to avoid storing it unnecessarily
        config_data.pop('script_csv_content', None)
    elif script_csv_content is not None:
        script_source_info = {"source_type": "csv", "details": "CSV content provided"}
        print("Using provided CSV content for generation.")
        # Remove script_id from config_data if it was present but None
        config_data.pop('script_id', None)
    # --- END MODIFIED --- 

    # Basic validation for other keys (ensure required keys exist, excluding the script source handled above)
    required_keys = ['skin_name', 'voice_ids', 'variants_per_line']
    if not all(key in config_data for key in required_keys):
        missing = [key for key in required_keys if key not in config_data]
        return make_api_response(error=f'Missing required configuration keys: {missing}', status_code=400)
    
    # Add script source info to the config before saving to JSON
    config_data['script_source'] = script_source_info
    config_data_json = json.dumps(config_data)

    db: Session = next(models.get_db()) # Get DB session again for job creation
    db_job = None
    try:
        # 1. Create Job record in DB
        db_job = models.GenerationJob(
            status="PENDING",
            parameters_json=config_data_json
            # submitted_at is default
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        print(f"Created GenerationJob record with DB ID: {db_job_id}")

        # 2. Enqueue Celery task, passing DB ID and script source
        # --- MODIFIED: Pass either script_id or csv_content to task --- 
        task = tasks.run_generation.delay(
            db_job_id,
            config_data_json, # Pass full config for other params
            script_id=script_id if script_id is not None else None, # Pass script_id if used
            script_csv_content=script_csv_content if script_csv_content is not None else None # Pass CSV if used
        )
        # --- END MODIFIED --- 
        print(f"Enqueued generation task with Celery ID: {task.id} for DB Job ID: {db_job_id}")

        # 3. Update Job record with Celery task ID
        db_job.celery_task_id = task.id
        db.commit()

        # 4. Return IDs to frontend
        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)

    except Exception as e:
        print(f"Error during job submission/enqueueing: {e}")
        # Attempt to rollback DB changes if job was created but task failed?
        if db_job and db_job.id and db.is_active:
            try:
                 db_job.status = "SUBMIT_FAILED"
                 db_job.result_message = f"Failed to enqueue Celery task: {e}"
                 db.commit()
            except Exception as db_err:
                 print(f"Failed to update job status after enqueue error: {db_err}")
                 db.rollback() # Rollback any partial changes
        elif db.is_active:
            db.rollback()

        return make_api_response(error="Failed to start generation task", status_code=500)
    finally:
        if db.is_active: db.close() # Ensure session is closed

@app.route('/api/generate/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Endpoint to check the status of a generation task."""
    try:
        # Use the celery instance imported from the module
        task_result = AsyncResult(task_id, app=celery)

        response_data = {
            'task_id': task_id,
            'status': task_result.status, # PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
            'info': None
        }

        if task_result.status == 'PENDING':
            response_data['info'] = {'status': 'Task is waiting to be processed.'}
        elif task_result.status == 'FAILURE':
            # task_result.info should contain the exception
            response_data['info'] = {'error': str(task_result.info), 'traceback': task_result.traceback}
            # Return 200 OK, but indicate failure in the payload
        elif task_result.status == 'SUCCESS':
            # task_result.info should contain the return value of the task
            response_data['info'] = task_result.info
        else:
            # For STARTED, RETRY, or custom states, info might be a dict (e.g., progress)
            if isinstance(task_result.info, dict):
                response_data['info'] = task_result.info
            else:
                response_data['info'] = {'status': str(task_result.info)}

        return make_api_response(data=response_data)

    except Exception as e:
        print(f"Error checking task status for {task_id}: {e}")
        return make_api_response(error="Failed to retrieve task status", status_code=500)

@app.route('/api/models', methods=['GET'])
def get_models():
    """Endpoint to get available models, supports capability filtering."""
    capability = request.args.get('capability', None)
    require_sts = capability == 'sts'
    print(f"API Route /api/models received capability='{capability}', require_sts={require_sts}")
    
    try:
        models_list = utils_elevenlabs.get_available_models(require_sts=require_sts)
        
        model_options = [
            {"model_id": m.get('model_id'), "name": m.get('name')}
            for m in models_list if m.get('model_id') and m.get('name')
        ]
        return make_api_response(data=model_options)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching models via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/models route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

# --- Job History API Endpoint --- #

@app.route('/api/jobs', methods=['GET'])
def list_generation_jobs():
    """Lists previously submitted generation jobs from the database."""
    db: Session = next(models.get_db())
    try:
        jobs = db.query(models.GenerationJob).order_by(models.GenerationJob.submitted_at.desc()).all()
        job_list = [
            {
                "id": job.id,
                "celery_task_id": job.celery_task_id,
                "status": job.status,
                "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "parameters_json": job.parameters_json, 
                "result_message": job.result_message,
                "result_batch_ids_json": job.result_batch_ids_json, 
                "job_type": job.job_type,
                "target_batch_id": job.target_batch_id,
                "target_line_key": job.target_line_key
            }
            for job in jobs
        ]
        return make_api_response(data=job_list)
    except Exception as e:
        print(f"Error listing jobs: {e}")
        return make_api_response(error="Failed to list generation jobs", status_code=500)
    finally:
        db.close()

# --- NEW: Script Management API Endpoints --- #

@app.route('/api/scripts', methods=['GET'])
def list_scripts():
    """Lists available scripts from the database."""
    start_time = time.time()
    logging.info("Entered /api/scripts endpoint")
    db: Session = None
    try:
        logging.info("Attempting to get DB session...")
        db = next(models.get_db())
        logging.info("DB session acquired.")
        
        # Get filter and sort parameters
        include_archived = request.args.get('include_archived', 'false').lower() == 'true'
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_direction = request.args.get('sort_direction', 'desc')

        # Basic validation for sort parameters
        allowed_sort_columns = {'name', 'created_at', 'updated_at', 'is_archived'}
        if sort_by not in allowed_sort_columns:
            sort_by = 'updated_at' # Default to updated_at if invalid
        if sort_direction not in {'asc', 'desc'}:
            sort_direction = 'desc'
        
        # Get the SQLAlchemy model attribute for sorting
        sort_column_attr = getattr(models.Script, sort_by, models.Script.updated_at)
        order_by_attr = sort_column_attr.asc() if sort_direction == 'asc' else sort_column_attr.desc()

        # Query scripts and their line counts
        # Use a subquery to count lines efficiently
        line_count_subquery = (
            db.query(
                models.ScriptLine.script_id,
                func.count(models.ScriptLine.id).label("line_count")
            )
            .group_by(models.ScriptLine.script_id)
            .subquery()
        )
        
        # Base query
        logging.info(f"Building base query for scripts (include_archived={include_archived})...")
        scripts_query = (
            db.query(
                models.Script,
                func.coalesce(line_count_subquery.c.line_count, 0).label("line_count")
            )
            .outerjoin(line_count_subquery, models.Script.id == line_count_subquery.c.script_id)
        )

        # Apply archive filter
        if not include_archived:
            scripts_query = scripts_query.filter(models.Script.is_archived == False)
            
        # Apply sorting
        scripts_query = scripts_query.order_by(order_by_attr)
        
        logging.info(f"Executing scripts query (sort_by={sort_by}, direction={sort_direction})...")
        query_start_time = time.time()
        scripts_with_counts = scripts_query.all()
        query_end_time = time.time()
        logging.info(f"Query executed in {query_end_time - query_start_time:.4f} seconds. Found {len(scripts_with_counts)} scripts.")

        script_list = [
            {
                "id": script.id,
                "name": script.name,
                "description": script.description,
                "line_count": line_count,
                "is_archived": script.is_archived, # Include archive status
                "created_at": script.created_at.isoformat() if script.created_at else None,
                "updated_at": script.updated_at.isoformat() if script.updated_at else None,
            }
            for script, line_count in scripts_with_counts
        ]
        end_time = time.time()
        logging.info(f"Successfully processed /api/scripts in {end_time - start_time:.4f} seconds.")
        return make_api_response(data=script_list)
    except Exception as e:
        end_time = time.time()
        logging.exception(f"Error in /api/scripts after {end_time - start_time:.4f} seconds: {e}") # Log full traceback
        return make_api_response(error="Failed to list scripts", status_code=500)
    finally:
        if db and db.is_active:
            logging.info("Closing DB session for /api/scripts.")
            db.close()
        else:
            logging.warning("DB session was not active or not acquired for /api/scripts at cleanup.")

@app.route('/api/scripts/<int:script_id>', methods=['GET'])
def get_script_details(script_id):
    """Gets the full details of a specific script, including its lines."""
    db: Session = next(models.get_db())
    try:
        # Query the script and eagerly load its lines using the relationship
        # The relationship already defines the ordering by order_index
        script = db.query(models.Script).options(joinedload(models.Script.lines)).get(script_id)

        if not script:
            return make_api_response(error=f"Script with ID {script_id} not found", status_code=404)

        # Format the response
        script_data = {
            "id": script.id,
            "name": script.name,
            "description": script.description,
            "created_at": script.created_at.isoformat() if script.created_at else None,
            "updated_at": script.updated_at.isoformat() if script.updated_at else None,
            "lines": [
                {
                    "id": line.id,
                    "line_key": line.line_key,
                    "text": line.text,
                    "order_index": line.order_index
                }
                for line in script.lines # Access the ordered lines via relationship
            ]
        }
        return make_api_response(data=script_data)

    except Exception as e:
        print(f"Error getting script details for ID {script_id}: {e}")
        return make_api_response(error="Failed to retrieve script details", status_code=500)
    finally:
        db.close()

@app.route('/api/scripts', methods=['POST'])
def create_script():
    """Creates a new script, optionally importing lines from CSV."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    script_name = data.get('name')
    description = data.get('description')
    csv_content = data.get('csv_content') # Optional CSV data

    if not script_name:
        return make_api_response(error="Missing required field: name", status_code=400)

    db: Session = next(models.get_db())
    try:
        # Check for existing script with the same name
        existing_script = db.query(models.Script).filter(models.Script.name == script_name).first()
        if existing_script:
            return make_api_response(error=f"Script name '{script_name}' already exists", status_code=409) # 409 Conflict

        # Create the new script object
        new_script = models.Script(
            name=script_name,
            description=description
            # created_at/updated_at handled by server_default
        )
        db.add(new_script)
        # Flush to get the new_script.id before adding lines
        db.flush()
        print(f"Creating script '{script_name}' with ID {new_script.id}")

        script_lines = []
        if csv_content:
            print(f"Importing lines from CSV content for script ID {new_script.id}")
            try:
                # Use io.StringIO to treat the string as a file
                csvfile = io.StringIO(csv_content)
                # Assuming header: line_key,text
                reader = csv.DictReader(csvfile)
                for index, row in enumerate(reader):
                    line_key = row.get('line_key')
                    text = row.get('text')
                    if not line_key or text is None: # Allow empty text, but key must exist
                        raise ValueError(f"Invalid CSV format or missing data at row {index + 2}")
                    script_lines.append(models.ScriptLine(
                        script_id=new_script.id,
                        line_key=line_key.strip(),
                        text=text.strip(),
                        order_index=index
                    ))
                print(f"Parsed {len(script_lines)} lines from CSV.")
                # Add all parsed lines to the session
                db.add_all(script_lines)
            except Exception as e:
                # Rollback the script creation if CSV parsing fails
                db.rollback()
                print(f"Error parsing CSV: {e}")
                return make_api_response(error=f"Failed to parse CSV content: {e}", status_code=400)
        else:
             print(f"Creating empty script (no CSV provided) for script ID {new_script.id}")

        # Commit the transaction (either script only or script + lines)
        db.commit()
        db.refresh(new_script) # Refresh to get final state

        # Prepare response data (excluding lines for brevity, use GET endpoint for full details)
        created_script_data = {
            "id": new_script.id,
            "name": new_script.name,
            "description": new_script.description,
            "created_at": new_script.created_at.isoformat() if new_script.created_at else None,
            "updated_at": new_script.updated_at.isoformat() if new_script.updated_at else None,
            "line_count": len(script_lines) # Return line count if imported
        }
        return make_api_response(data=created_script_data, status_code=201)

    except Exception as e:
        db.rollback() # Rollback on any other unexpected error
        print(f"Error creating script '{script_name}': {e}")
        return make_api_response(error="Failed to create script", status_code=500)
    finally:
        db.close()

@app.route('/api/scripts/<int:script_id>', methods=['PUT'])
def update_script(script_id):
    """Updates a script's metadata and/or replaces its lines."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    new_name = data.get('name')
    new_description = data.get('description')
    new_lines_data = data.get('lines') # Expects a list of {"line_key": ..., "text": ..., "order_index": ...}

    db: Session = next(models.get_db())
    try:
        # Fetch the existing script
        script = db.query(models.Script).get(script_id)
        if not script:
            return make_api_response(error=f"Script with ID {script_id} not found", status_code=404)

        updated = False
        # Update metadata if provided
        if new_name is not None and new_name != script.name:
            # Check for name conflict if changing name
            existing_script = db.query(models.Script).filter(models.Script.name == new_name, models.Script.id != script_id).first()
            if existing_script:
                return make_api_response(error=f"Script name '{new_name}' already exists", status_code=409)
            script.name = new_name
            updated = True
            print(f"Updating script {script_id} name to '{new_name}'")

        # Use `get` method for description to handle explicit null vs not provided
        if data.get('description', script.description) != script.description:
            script.description = new_description # Can be set to None
            updated = True
            print(f"Updating script {script_id} description")

        # Update lines if provided
        if new_lines_data is not None:
            print(f"Replacing lines for script ID {script_id}. Got {len(new_lines_data)} new lines.")
            updated = True
            # Delete existing lines efficiently (using the cascade is one way, but explicit delete is clearer here)
            db.query(models.ScriptLine).filter(models.ScriptLine.script_id == script_id).delete(synchronize_session=False)
            
            # Create new line objects from payload
            new_lines = []
            seen_keys = set()
            for index, line_data in enumerate(new_lines_data):
                line_key = line_data.get('line_key')
                text = line_data.get('text')
                order_index = line_data.get('order_index') # Use provided index for ordering

                if not line_key or text is None or order_index is None:
                     raise ValueError(f"Invalid line data format at index {index}. Missing key, text, or order_index.")
                if line_key in seen_keys:
                     raise ValueError(f"Duplicate line_key '{line_key}' found in input data.")
                seen_keys.add(line_key)

                new_lines.append(models.ScriptLine(
                    script_id=script_id,
                    line_key=line_key.strip(),
                    text=text.strip(),
                    order_index=int(order_index) # Ensure integer
                ))
            
            # Add all new lines
            if new_lines:
                db.add_all(new_lines)
        elif updated:
            # If only metadata updated, still touch updated_at implicitly via commit
            pass
        else:
            # Nothing to update
            return make_api_response(data={"message": "No changes detected"}) # Or return current data?

        db.commit()
        db.refresh(script) # Refresh to get updated timestamps etc.

        # Return updated script metadata (lines can be fetched via GET if needed)
        updated_script_data = {
            "id": script.id,
            "name": script.name,
            "description": script.description,
            "created_at": script.created_at.isoformat() if script.created_at else None,
            "updated_at": script.updated_at.isoformat() if script.updated_at else None,
            # Calculate line count after commit/refresh if needed
            # "line_count": db.query(func.count(models.ScriptLine.id)).filter(models.ScriptLine.script_id == script_id).scalar()
        }
        return make_api_response(data=updated_script_data)

    except ValueError as ve:
        db.rollback()
        print(f"Validation error updating script {script_id}: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except Exception as e:
        db.rollback()
        print(f"Error updating script {script_id}: {e}")
        return make_api_response(error="Failed to update script", status_code=500)
    finally:
        db.close()

@app.route('/api/scripts/<int:script_id>', methods=['DELETE'])
def delete_script(script_id):
    """Deletes a script and its associated lines."""
    db: Session = next(models.get_db())
    try:
        # Fetch the existing script
        script = db.query(models.Script).get(script_id)
        if not script:
            return make_api_response(error=f"Script with ID {script_id} not found", status_code=404)

        # Delete the script (cascade should handle lines)
        db.delete(script)
        db.commit()
        print(f"Deleted script ID {script_id} ('{script.name}')")

        return make_api_response(data={"message": f"Script '{script.name}' deleted successfully"})
        # Could also return 204 No Content

    except Exception as e:
        db.rollback()
        print(f"Error deleting script {script_id}: {e}")
        return make_api_response(error="Failed to delete script", status_code=500)
    finally:
        db.close()

# NEW: Endpoint to Archive/Unarchive a script
@app.route('/api/scripts/<int:script_id>/archive', methods=['PATCH'])
def toggle_script_archive_status(script_id):
    """Archives or unarchives a script."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    archive_flag = data.get('archive')

    if archive_flag is None or not isinstance(archive_flag, bool):
        return make_api_response(error="Missing or invalid 'archive' boolean field in request body", status_code=400)

    db: Session = next(models.get_db())
    try:
        script = db.query(models.Script).get(script_id)
        if not script:
            return make_api_response(error=f"Script with ID {script_id} not found", status_code=404)

        if script.is_archived == archive_flag:
            # No change needed, return current state
            action = "archived" if archive_flag else "active"
            message = f"Script is already {action}."
        else:
            script.is_archived = archive_flag
            db.commit()
            action = "archived" if archive_flag else "unarchived"
            message = f"Script successfully {action}."
            print(f"Script ID {script_id} ('{script.name}') set to is_archived={archive_flag}")
        
        db.refresh(script)
        # Prepare response data (match listScripts format for consistency)
        line_count = db.query(func.count(models.ScriptLine.id)).filter(models.ScriptLine.script_id == script_id).scalar()
        updated_script_data = {
            "id": script.id,
            "name": script.name,
            "description": script.description,
            "line_count": line_count,
            "is_archived": script.is_archived,
            "created_at": script.created_at.isoformat() if script.created_at else None,
            "updated_at": script.updated_at.isoformat() if script.updated_at else None,
        }
        return make_api_response(data=updated_script_data, status_code=200) # Use data field for consistency

    except Exception as e:
        db.rollback()
        action = "archiving" if archive_flag else "unarchiving"
        print(f"Error {action} script {script_id}: {e}")
        return make_api_response(error=f"Failed to {action.replace('ing', '')} script", status_code=500)
    finally:
        db.close()

# --- Batch & Ranking API Endpoints (Refactored for R2) --- #

@app.route('/api/batches', methods=['GET'])
def list_batches():
    """Lists available batches by querying successful jobs from the database."""
    logging.info("--- Entered /api/batches endpoint --- ")
    try:
        db: Session = next(models.get_db())
        batches = []
        try:
            logging.info("Querying successful generation jobs...")
            successful_jobs = (
                db.query(models.GenerationJob)
                .filter(
                    models.GenerationJob.status.in_(["SUCCESS", "COMPLETED_WITH_ERRORS"]),
                    models.GenerationJob.result_batch_ids_json.isnot(None)
                )
                .order_by(models.GenerationJob.completed_at.desc())
                .all()
            )
            logging.info(f"Found {len(successful_jobs)} potential jobs.")

            processed_prefixes = set()
            for job in successful_jobs:
                try:
                    # Prefixes are stored as a JSON list string
                    prefixes_or_ids = json.loads(job.result_batch_ids_json)
                    if isinstance(prefixes_or_ids, list):
                        for item in prefixes_or_ids:
                            # Check if it looks like a prefix (contains slashes)
                            if isinstance(item, str) and '/' in item:
                                prefix = item
                                if prefix not in processed_prefixes:
                                    parts = prefix.split('/')
                                    if len(parts) >= 3:
                                         batch_info = {
                                             'batch_prefix': prefix, # This is the ID now
                                             'skin_name': parts[0],
                                             'voice_name': parts[1],
                                             'id': parts[2], # The original timestamp-id part
                                             'generated_at_utc': None # TODO: Consider fetching this if needed
                                         }
                                         batches.append(batch_info)
                                         processed_prefixes.add(prefix)
                                    else:
                                         logging.warning(f"Unexpected batch prefix format in job {job.id}: {prefix}")
                            elif isinstance(item, str): # Looks like an old batch_id
                                 logging.warning(f"Found old-style batch ID in job {job.id}: {item}. Skipping.")
                            else:
                                 logging.warning(f"Found non-string item in result_batch_ids_json for job {job.id}: {item}")

                except json.JSONDecodeError:
                    logging.warning(f"Failed to parse result_batch_ids_json for job {job.id}: {job.result_batch_ids_json}")

        finally:
             db.close()

        logging.info(f"--- Exiting /api/batches successfully. Returning {len(batches)} batches. ---")
        return make_api_response(data=batches)
    except Exception as e:
        logging.exception(f"--- Error in /api/batches: {e} ---")
        return make_api_response(error="Failed to list batches", status_code=500)

# Route now uses <path:batch_prefix> to capture the full prefix including slashes
@app.route('/api/batch/<path:batch_prefix>', methods=['GET'])
def get_batch_metadata(batch_prefix):
    """Gets the metadata for a specific batch prefix from R2."""
    # batch_prefix comes URL-decoded automatically by Flask
    if not batch_prefix or '..' in batch_prefix: # Basic security check
        return make_api_response(error="Invalid batch prefix", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    logging.info(f"Attempting to fetch metadata from R2: {metadata_blob_key}") # Use logging

    try:
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            logging.warning(f"Metadata blob not found for prefix '{batch_prefix}'") # Use logging
            return make_api_response(error=f"Metadata not found for batch prefix '{batch_prefix}'", status_code=404)

        # Decode and parse JSON
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            return make_api_response(data=metadata)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Failed to parse metadata JSON for {metadata_blob_key}: {e}")
            return make_api_response(error="Failed to parse batch metadata", status_code=500)

    except Exception as e:
        logging.exception(f"Unexpected error getting metadata for {batch_prefix}: {e}")
        return make_api_response(error="Failed to get batch metadata", status_code=500)

# Note: Batch ID is now the full R2 Prefix
@app.route('/api/batch/<path:batch_prefix>/take/<path:filename>', methods=['PATCH'])
def update_take_rank(batch_prefix, filename):
    """Updates the rank of a specific take within a batch by modifying metadata in R2."""
    # Basic security check
    if not batch_prefix or '..' in batch_prefix:
        return make_api_response(error="Invalid batch prefix", status_code=400)
    if not filename or '..' in filename or not filename.endswith('.mp3'):
        return make_api_response(error="Invalid filename", status_code=400)

    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    new_rank = data.get('rank')

    if new_rank is not None:
        try:
            new_rank = int(new_rank)
            if not (1 <= new_rank <= 6): raise ValueError()
        except (ValueError, TypeError):
            return make_api_response(error="Invalid rank value. Must be integer 1-6 or null.", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    logging.info(f"Updating rank for take '{filename}' in prefix '{batch_prefix}'. New rank: {new_rank}") # Use logging

    try:
        # 1. Download current metadata
        logging.info(f"Downloading metadata: {metadata_blob_key}") # Use logging
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            return make_api_response(error=f"Metadata not found for batch '{batch_prefix}'", status_code=404)
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
             logging.error(f"Failed to parse metadata JSON for {metadata_blob_key}: {e}")
             return make_api_response(error="Failed to parse batch metadata for update", status_code=500)

        # 2. Find and update the take
        take_updated = False
        updated_take_info = None
        for take in metadata.get('takes', []):
             if take.get('file') == filename:
                 take['rank'] = new_rank
                 take['ranked_at'] = datetime.now(timezone.utc).isoformat() if new_rank is not None else None
                 take_updated = True
                 updated_take_info = take
                 logging.info(f"Found and updated take metadata for {filename}") # Use logging
                 break

        if not take_updated:
            return make_api_response(error=f"Take '{filename}' not found in batch '{batch_prefix}'", status_code=404)

        # 3. Upload the modified metadata (overwrite)
        logging.info(f"Uploading updated metadata: {metadata_blob_key}") # Use logging
        updated_metadata_bytes = json.dumps(metadata, indent=2).encode('utf-8')
        upload_success = utils_r2.upload_blob(
            blob_name=metadata_blob_key,
            data=updated_metadata_bytes,
            content_type='application/json'
        )

        if not upload_success:
             logging.error(f"Failed to upload updated metadata for {metadata_blob_key}")
             return make_api_response(error="Failed to save updated rank to storage", status_code=500)

        logging.info(f"Successfully updated rank for {filename} in {batch_prefix}") # Use logging
        return make_api_response(data={
            "status": "Rank updated successfully",
            "updated_take": updated_take_info
        })

    except Exception as e:
        logging.exception(f"Unexpected error updating rank for {filename} in {batch_prefix}: {e}")
        return make_api_response(error="Failed to update take rank", status_code=500)

# --- Regeneration Endpoints (Refactored for R2) --- #

# Route uses <path:batch_prefix>
@app.route('/api/batch/<path:batch_prefix>/regenerate_line', methods=['POST'])
def regenerate_line(batch_prefix):
    """Endpoint to start a line regeneration task, using batch prefix."""
    if not request.is_json: return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    required_keys = ['line_key', 'line_text', 'num_new_takes', 'settings', 'replace_existing']
    if not all(key in data for key in required_keys):
        missing = [key for key in required_keys if key not in data]; return make_api_response(error=f'Missing keys: {missing}', status_code=400)

    line_key = data['line_key']; line_text = data['line_text']; num_new_takes = data['num_new_takes']
    settings = data['settings']; replace_existing = data['replace_existing']; update_script = data.get('update_script', False)
    settings_json = json.dumps(settings)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check if target batch metadata exists in R2
        metadata_blob_key = f"{batch_prefix}/metadata.json"
        if not utils_r2.blob_exists(metadata_blob_key):
             return make_api_response(error=f"Target batch prefix '{batch_prefix}' not found for regeneration", status_code=404)

        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING", job_type="line_regen",
            target_batch_id=batch_prefix, # Store the prefix
            target_line_key=line_key,
            parameters_json=json.dumps(data)
        )
        db.add(db_job); db.commit(); db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created Line Regen Job DB ID: {db_job_id} for prefix {batch_prefix}") # Use logging

        # Enqueue Celery task, passing the BATCH PREFIX
        task = tasks.regenerate_line_takes.delay(
            db_job_id, batch_prefix, line_key, line_text, # Pass prefix as batch_id
            num_new_takes, settings_json, replace_existing, update_script
        )
        logging.info(f"Enqueued line regen task: Celery ID {task.id}, DB Job ID {db_job_id}") # Use logging
        db_job.celery_task_id = task.id; db.commit()
        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)
    except Exception as e:
        logging.exception(f"Error submitting line regeneration job for prefix {batch_prefix}: {e}")
        if db_job and db_job.id: # Mark job as failed
            try: db_job.status = "SUBMIT_FAILED"; db_job.result_message = f"Enqueue failed: {e}"; db.commit()
            except: db.rollback()
        return make_api_response(error="Failed to start line regeneration task", status_code=500)
    finally: db.close()

# Route uses <path:batch_prefix>
@app.route('/api/batch/<path:batch_prefix>/speech_to_speech', methods=['POST'])
def start_speech_to_speech_line(batch_prefix):
    """Endpoint to start a line speech-to-speech task, using batch prefix."""
    if not request.is_json: return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    required_keys = ['line_key', 'source_audio_b64', 'num_new_takes', 'target_voice_id', 'model_id', 'settings', 'replace_existing']
    if not all(key in data for key in required_keys): missing = [k for k in required_keys if k not in data]; return make_api_response(error=f'Missing keys: {missing}', status_code=400)

    line_key = data['line_key']; source_audio_b64 = data['source_audio_b64']
    num_new_takes = data['num_new_takes']; target_voice_id = data['target_voice_id']
    model_id = data['model_id']; settings = data['settings']; replace_existing = data['replace_existing']
    settings_json = json.dumps(settings)
    if not source_audio_b64 or not source_audio_b64.startswith('data:audio'): return make_api_response(error='Invalid audio data URI', status_code=400)
    if not isinstance(num_new_takes, int) or num_new_takes <= 0: return make_api_response(error='Invalid num_new_takes', status_code=400)
    try: header, encoded = source_audio_b64.split(';base64,', 1)
    except: return make_api_response(error='Failed to decode source audio data', status_code=400)

    db: Session = next(models.get_db())
    db_job = None
    try:
        # Check if target batch metadata exists in R2
        metadata_blob_key = f"{batch_prefix}/metadata.json"
        if not utils_r2.blob_exists(metadata_blob_key):
             return make_api_response(error=f"Target batch prefix '{batch_prefix}' not found for STS", status_code=404)

        # Create Job DB record
        db_job = models.GenerationJob(
            status="PENDING", job_type="sts_line_regen",
            target_batch_id=batch_prefix, # Store the prefix
            target_line_key=line_key,
            parameters_json=json.dumps({ 'target_voice_id': target_voice_id, 'model_id': model_id, 'num_new_takes': num_new_takes, 'settings': settings, 'replace_existing': replace_existing, 'source_audio_info': header })
        )
        db.add(db_job); db.commit(); db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created STS Line Job DB ID: {db_job_id} for prefix {batch_prefix}") # Use logging

        # Enqueue Celery task, passing BATCH PREFIX and base64 string
        task = tasks.run_speech_to_speech_line.delay(
            db_job_id, batch_prefix, line_key, source_audio_b64, # Pass prefix
            num_new_takes, target_voice_id, model_id, settings_json, replace_existing
        )
        logging.info(f"Enqueued STS line task: Celery ID {task.id}, DB Job ID {db_job_id}") # Use logging
        db_job.celery_task_id = task.id; db.commit()
        return make_api_response(data={'task_id': task.id, 'job_id': db_job_id}, status_code=202)
    except Exception as e:
        logging.exception(f"Error submitting STS line job for prefix {batch_prefix}: {e}")
        if db_job and db_job.id: # Mark job as failed
            try: db_job.status = "SUBMIT_FAILED"; db_job.result_message = f"Enqueue failed: {e}"; db.commit()
            except: db.rollback()
        return make_api_response(error="Failed to start speech-to-speech task", status_code=500)
    finally: db.close()

# --- NEW: Audio Cropping Endpoint --- #
@app.route('/api/batch/<path:batch_prefix>/takes/<path:filename>/crop', methods=['POST'])
def crop_take(batch_prefix, filename):
    """Endpoint to start a Celery task to crop an audio take."""
    # Basic security/validation
    if not batch_prefix or '..' in batch_prefix:
        return make_api_response(error="Invalid batch prefix", status_code=400)
    if not filename or '..' in filename or not filename.endswith('.mp3'):
        return make_api_response(error="Invalid filename", status_code=400)
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    
    data = request.get_json()
    start_time = data.get('startTime')
    end_time = data.get('endTime')

    if start_time is None or end_time is None:
        return make_api_response(error="Missing required fields: startTime and endTime", status_code=400)

    try:
        start_seconds = float(start_time)
        end_seconds = float(end_time)
        if start_seconds < 0 or end_seconds <= 0 or start_seconds >= end_seconds:
            raise ValueError("Invalid start/end time values.")
    except (ValueError, TypeError):
        return make_api_response(error="Invalid startTime or endTime format. Must be numbers in seconds.", status_code=400)

    # Construct the full R2 object key for the take
    # Assuming the structure skin/voice/batch/takes/filename
    r2_object_key = f"{batch_prefix}/takes/{filename}"
    logging.info(f"Received crop request for R2 key: {r2_object_key}, Start: {start_seconds}, End: {end_seconds}")

    # Optional: Check if batch is locked (we decided to disallow cropping locked batches in the spec)
    metadata_blob_key = f"{batch_prefix}/metadata.json"
    try:
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if metadata_bytes:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            if metadata.get('ranked_at_utc') is not None:
                logging.warning(f"Attempted to crop take in locked batch: {batch_prefix}")
                return make_api_response(error="Cannot crop takes in a locked batch.", status_code=403) # 403 Forbidden
        else:
             # If metadata doesn't exist, something is wrong, but let task handle R2 key check
             logging.warning(f"Metadata not found for batch {batch_prefix} during crop request, but proceeding.")
    except Exception as meta_err:
        logging.error(f"Error checking batch lock status during crop request for {batch_prefix}: {meta_err}")
        # Decide if this error should prevent the crop or just be logged
        # return make_api_response(error="Failed to check batch lock status", status_code=500)

    try:
        # Enqueue the Celery task
        task = tasks.crop_audio_take.delay(r2_object_key, start_seconds, end_seconds)
        logging.info(f"Enqueued crop task with Celery ID: {task.id} for R2 key {r2_object_key}")
        
        # Return task ID immediately (or job ID if we were creating one)
        # Frontend will need to poll task status or just rely on overwrite
        return make_api_response(data={'task_id': task.id, 'message': 'Crop task started.'}, status_code=202)

    except Exception as e:
        logging.exception(f"Error enqueueing crop task for {r2_object_key}: {e}")
        return make_api_response(error="Failed to start audio cropping task", status_code=500)

# --- NEW: Voice Design API Endpoints --- #

@app.route('/api/voice-design/previews', methods=['POST'])
def create_voice_design_previews():
    """Endpoint to generate voice previews based on description and settings."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    
    # Extract parameters from request data
    voice_description = data.get('voice_description')
    text = data.get('text')
    auto_generate_text = data.get('auto_generate_text', False)
    loudness = data.get('loudness')
    quality = data.get('quality')
    seed = data.get('seed')
    guidance_scale = data.get('guidance_scale')
    output_format = data.get('output_format', 'mp3_44100_128')

    if not voice_description:
         return make_api_response(error="Missing required field: voice_description", status_code=400)

    try:
        previews, generated_text = utils_elevenlabs.create_voice_previews(
            voice_description=voice_description,
            text=text,
            auto_generate_text=auto_generate_text,
            loudness=loudness,
            quality=quality,
            seed=seed,
            guidance_scale=guidance_scale,
            output_format=output_format
        )
        return make_api_response(data={"previews": previews, "text": generated_text})
    except ValueError as ve:
        # Catch validation errors from the utility function
        print(f"Validation error creating voice previews: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error creating voice previews: {e}")
        # Determine appropriate status code based on error? (e.g., 422 for validation)
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error creating voice previews: {e}")
        return make_api_response(error="Failed to create voice previews", status_code=500)

@app.route('/api/voice-design/save', methods=['POST'])
def save_voice_design_preview():
    """Endpoint to save a selected voice preview to the library."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    generated_voice_id = data.get('generated_voice_id')
    voice_name = data.get('voice_name')
    voice_description = data.get('voice_description')
    labels = data.get('labels') # Optional

    if not all([generated_voice_id, voice_name, voice_description]):
        missing = [k for k, v in {'generated_voice_id': generated_voice_id, 'voice_name': voice_name, 'voice_description': voice_description}.items() if not v]
        return make_api_response(error=f"Missing required fields: {missing}", status_code=400)
        
    try:
        saved_voice_details = utils_elevenlabs.save_generated_voice(
            generated_voice_id=generated_voice_id,
            voice_name=voice_name,
            voice_description=voice_description,
            labels=labels
        )
        # Maybe map this response to our VoiceOption type before sending?
        # For now, just return the full details.
        return make_api_response(data=saved_voice_details)
    except ValueError as ve:
        print(f"Validation error saving voice: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error saving voice: {e}")
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error saving voice: {e}")
        return make_api_response(error="Failed to save voice", status_code=500)

# --- Audio Serving Endpoint --- #

@app.route('/audio/<path:blob_key>')
def serve_audio(blob_key):
    """Serves audio files by redirecting to a presigned R2 URL."""
    if not blob_key or '..' in blob_key or not blob_key.endswith('.mp3'):
        return make_api_response(error="Invalid audio path", status_code=400)

    logging.info(f"Request to serve audio for blob key: {blob_key}") # Use logging
    try:
        presigned_url = utils_r2.generate_presigned_url(blob_key, expiration=3600)
        
        if presigned_url:
            logging.info(f"Redirecting to presigned URL for: {blob_key}") # Use logging
            return redirect(presigned_url, code=302)
        else:
            if utils_r2.blob_exists(blob_key):
                 logging.error(f"Failed to generate presigned URL for existing blob: {blob_key}")
                 return make_api_response(error="Failed to generate temporary audio URL", status_code=500)
            else:
                 logging.warning(f"Audio blob not found in R2: {blob_key}")
                 return make_api_response(error="Audio file not found", status_code=404)

    except Exception as e:
        logging.exception(f"Error serving audio file {blob_key}: {e}")
        return make_api_response(error="Failed to serve audio file", status_code=500)

# --- Batch Download Endpoint --- #

@app.route('/api/batch/<path:batch_prefix>/download', methods=['GET'])
def download_batch_zip(batch_prefix):
    """Creates and returns a ZIP archive with takes organized by rank based on metadata."""
    if not batch_prefix or '..' in batch_prefix: # Basic security check
        return make_api_response(error="Invalid batch prefix", status_code=400)

    metadata_blob_key = f"{batch_prefix}/metadata.json"
    zip_filename_base = batch_prefix.replace('/', '_')
    zip_download_name = f"{zip_filename_base}.zip"
    logging.info(f"Request to download zip for batch prefix: {batch_prefix}")

    memory_file = io.BytesIO()
    try:
        # 1. Download and parse metadata
        logging.info(f"Downloading metadata: {metadata_blob_key}")
        metadata_bytes = utils_r2.download_blob_to_memory(metadata_blob_key)
        if not metadata_bytes:
            logging.warning(f"Metadata blob not found: {metadata_blob_key}")
            return make_api_response(error=f"Batch prefix '{batch_prefix}' metadata not found.", status_code=404)
        try:
            metadata = json.loads(metadata_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Failed to parse metadata JSON for zip: {metadata_blob_key}: {e}")
            return make_api_response(error="Failed to parse batch metadata for zip.", status_code=500)

        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 2. Add metadata.json to zip
            zf.writestr("metadata.json", metadata_bytes)
            logging.info("Added metadata.json to zip.")

            # 3. Iterate through takes listed in metadata
            takes_list = metadata.get('takes', [])
            added_files_count = 0
            failed_files_count = 0
            added_ranked_count = 0
            
            logging.info(f"Found {len(takes_list)} takes listed in metadata.")

            # Cache downloaded audio bytes to avoid re-downloading for ranked folder
            audio_data_cache: Dict[str, bytes] = {}

            for take in takes_list:
                r2_key = take.get('r2_key')
                filename = take.get('file') # This should be just the base filename
                rank = take.get('rank')
                
                if not r2_key or not filename:
                    logging.warning(f"Skipping take due to missing r2_key or file in metadata: {take}")
                    continue
                
                # Ensure the file is in the cache (download if needed)
                if r2_key not in audio_data_cache:
                    logging.info(f"Downloading {r2_key} for zip...") 
                    audio_bytes = utils_r2.download_blob_to_memory(r2_key)
                    if audio_bytes is None:
                        failed_files_count += 1
                        logging.warning(f"Failed to download {r2_key} for zip file. Skipping.")
                        continue # Skip this take entirely if download fails
                    audio_data_cache[r2_key] = audio_bytes
                else:
                    # Should not happen with current loop structure, but good practice
                    audio_bytes = audio_data_cache[r2_key]

                # Add to takes/ folder
                takes_arcname = f"takes/{filename}" 
                zf.writestr(takes_arcname, audio_bytes)
                added_files_count += 1
                logging.debug(f"Added {takes_arcname} to zip.")

                # If ranked (1-5), also add to ranked/0X/ folder
                if isinstance(rank, int) and 1 <= rank <= 5:
                    ranked_arcname = f"ranked/{rank:02d}/{filename}"
                    try:
                        zf.writestr(ranked_arcname, audio_bytes)
                        added_ranked_count += 1
                        logging.debug(f"Added {ranked_arcname} to zip.")
                    except Exception as zip_err:
                        # Log error adding ranked file but continue
                        logging.error(f"Failed to add ranked file {ranked_arcname} to zip: {zip_err}")
                # Rank 6 (Trash) is ignored for zip download
            
            if failed_files_count > 0:
                 logging.warning(f"Failed to download {failed_files_count} audio files listed in metadata for zip.")
                 
            logging.info(f"Added metadata, {added_files_count} takes files, and {added_ranked_count} ranked file copies to zip for {batch_prefix}")

        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_download_name
        )

    except Exception as e:
        logging.exception(f"Unexpected error creating zip for {batch_prefix}: {e}")
        return make_api_response(error="Failed to create batch zip file", status_code=500)

# --- NEW: Voice Preview Endpoint --- #
@app.route('/api/voices/<string:voice_id>/preview', methods=['GET'])
def get_voice_preview(voice_id):
    """Generates and streams a short audio preview for a given voice ID."""
    logging.info(f"Received preview request for voice_id: {voice_id}")
    try:
        # Use the new stream function from utils
        # Note: Ensure the generate_preview_audio_stream function exists and works
        preview_response = utils_elevenlabs.generate_preview_audio_stream(
            voice_id=voice_id,
            text=VOICE_PREVIEW_TEXT
        )
        
        # Check if the response has content before creating the Flask response
        if preview_response.content is None and preview_response.status_code != 200:
             # Handle case where the stream function failed gracefully but indicated an issue
             # Use the status code and potentially the content from the failed response
             logging.error(f"Preview generation failed upstream for {voice_id}. Status: {preview_response.status_code}")
             error_detail = "Preview generation failed."
             try: 
                 error_detail = preview_response.json().get('detail', error_detail)
             except: pass # Ignore if response isn't JSON
             return make_api_response(error=error_detail, status_code=preview_response.status_code)
        
        # Stream the audio content back
        # The iter_content chunk size can be adjusted
        def generate_chunks():
            try:
                for chunk in preview_response.iter_content(chunk_size=1024):
                    yield chunk
                logging.info(f"Finished streaming preview for {voice_id}")
            except Exception as stream_err:
                logging.error(f"Error during preview streaming for {voice_id}: {stream_err}")
                # Don't yield further, let the client handle the broken stream
            finally:
                 # Ensure the underlying connection is closed if the response object supports it
                if hasattr(preview_response, 'close'):
                     preview_response.close()

        logging.info(f"Streaming preview audio for {voice_id}...")
        return Response(generate_chunks(), mimetype='audio/mpeg')

    except utils_elevenlabs.ElevenLabsError as e:
        logging.error(f"ElevenLabsError generating preview for {voice_id}: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        logging.exception(f"Unexpected error generating preview for {voice_id}: {e}") # Log traceback
        return make_api_response(error="An unexpected server error occurred", status_code=500)

# We don't need the app.run() block here when using 'flask run' or gunicorn/waitress 