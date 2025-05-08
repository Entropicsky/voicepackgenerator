# backend/routes/generation_routes.py
"""
Routes for voice generation and job management.
"""
from flask import Blueprint, request, jsonify
from backend import models
from backend.utils.response_utils import make_api_response
import json
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models import GenerationJob
import logging

generation_bp = Blueprint('generation', __name__, url_prefix='/api')

@generation_bp.route('/generate', methods=['POST'])
def start_generation():
    """Endpoint to start an asynchronous generation task using VO Script."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    config_data = request.get_json()
    
    # --- Expect vo_script_id --- 
    vo_script_id = config_data.get('vo_script_id')
    if vo_script_id is None: # Check if None explicitly
         return make_api_response(error="Missing required field: vo_script_id", status_code=400)
    
    # Basic validation for other keys
    required_keys = ['skin_name', 'voice_ids', 'variants_per_line']
    if not all(key in config_data for key in required_keys):
        missing = [key for key in required_keys if key not in config_data]
        return make_api_response(error=f'Missing required configuration keys: {missing}', status_code=400)
    
    # Prepare config_data for storage, removing potentially large fields we don't need
    # Remove old script fields if they accidentally slipped through
    config_data.pop('script_id', None)
    config_data.pop('script_csv_content', None)
    
    # Update script_source info
    config_data['script_source'] = {"source_type": "vo_script", "vo_script_id": vo_script_id}
    config_data_json = json.dumps(config_data)

    db: Session = next(models.get_db()) # Get DB session again for job creation
    db_job = None
    try:
        # 1. Create Job record in DB
        db_job = models.GenerationJob(
            status="PENDING",
            parameters_json=config_data_json,
            job_type="full_batch" # Explicitly set job type
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        print(f"Created GenerationJob record with DB ID: {db_job_id}")

        # 2. Enqueue Celery task, passing DB ID and vo_script_id
        from backend.tasks import run_generation
        task = run_generation.delay(
            db_job_id,
            config_data_json, # Pass full config for other params
            vo_script_id=vo_script_id # Pass the validated vo_script_id
        )
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
        elif db and db.is_active:
            db.rollback()

        return make_api_response(error="Failed to start generation task", status_code=500)
    finally:
        if db and db.is_active: db.close() # Ensure session is closed

@generation_bp.route('/jobs', methods=['GET'])
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

@generation_bp.route('/optimize-line-text', methods=['POST'])
def optimize_line_text():
    """Optimizes the provided line text for ElevenLabs using OpenAI."""
    import logging
    import os
    import openai
    
    logging.info("--- Entered /api/optimize-line-text endpoint ---")
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    line_text = data.get('line_text')

    if not line_text:
        return make_api_response(error="Missing required field: line_text", status_code=400)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.error("OPENAI_API_KEY environment variable not set.")
        return make_api_response(error="OpenAI API key not configured on server.", status_code=500)

    # Construct the absolute path to the scripthelp file relative to this script's location
    # __file__ gives the path to the current script
    # os.path.dirname gets the directory containing the script
    # os.path.join combines it with the relative path to the prompts file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level from routes directory to backend directory
    backend_dir = os.path.dirname(current_dir)
    prompt_guidelines_path = os.path.join(backend_dir, 'prompts', 'scripthelp.md')

    try:
        logging.info(f"Reading prompt guidelines from: {prompt_guidelines_path}")
        with open(prompt_guidelines_path, 'r', encoding='utf-8') as f:
            prompt_guidelines = f.read()
        # Extract the core rules/instructions part, assuming the initial text is boilerplate
        # This might need adjustment based on the exact file structure
        guidelines_start_marker = "### ElevenLabs Prompt-Writing Rules:"
        guidelines_end_marker = "### Example Agent Prompt:" # Or end of file if marker not present
        
        start_index = prompt_guidelines.find(guidelines_start_marker)
        end_index = prompt_guidelines.find(guidelines_end_marker)
        
        if start_index != -1:
            if end_index != -1:
                 rules_section = prompt_guidelines[start_index:end_index].strip()
            else:
                 rules_section = prompt_guidelines[start_index:].strip()
            # Add the instruction to only return the prompt text
            # --- MODIFIED INSTRUCTION --- 
            instruction_line = "You are an expert prompt writer for ElevenLabs TTS. Rewrite the following voice line based *strictly* on the rules provided below to optimize it for ElevenLabs, focusing on natural pace and emotion.\\n\\nRules:"
            base_prompt = f"{instruction_line}\\n{rules_section}\\n\\nVoice Line to rewrite:"
        else:
             logging.warning("Could not find start marker in scripthelp.md, using full file content as guidelines.")
             # --- MODIFIED INSTRUCTION (Fallback) --- 
             instruction_line = "You are an expert prompt writer for ElevenLabs TTS. Rewrite the following voice line based *strictly* on the rules provided below to optimize it for ElevenLabs, focusing on natural pace and emotion.\\n\\nRules:"
             base_prompt = f"{instruction_line}\\n{prompt_guidelines}\\n\\nVoice Line to rewrite:"

        # --- MODIFIED FINAL PROMPT with explicit sections and stricter output instruction --- 
        input_line_label = "--- VOICE LINE TO OPTIMIZE ---"
        output_label = "--- OPTIMIZED LINE (Respond with ONLY the single, best optimized text line below this line. DO NOT include multiple variations, explanations, or the original line.) ---"
        full_prompt = f"{base_prompt.replace('Voice Line to rewrite:', '').strip()}\n\n{input_line_label}\n{line_text}\n\n{output_label}" # Construct with labeled sections
        
        logging.debug(f"Constructed OpenAI Prompt:\n{full_prompt}")

    except FileNotFoundError:
        logging.error(f"Prompt guidelines file not found at: {prompt_guidelines_path}")
        return make_api_response(error="Server configuration error: Prompt guidelines file missing.", status_code=500)
    except Exception as e:
        logging.exception(f"Error reading or processing prompt guidelines file: {e}")
        return make_api_response(error="Server configuration error reading guidelines.", status_code=500)

    try:
        logging.info("Initializing OpenAI client...")
        client = openai.OpenAI(api_key=api_key) # Explicitly pass key

        # Use the model specified in the environment variable, default to gpt-4o
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        logging.info(f"Using OpenAI model: {openai_model}")

        logging.info(f"Calling OpenAI Responses API (model {openai_model}) for text optimization...")
        response = client.responses.create(
            model=openai_model, # Use the variable here
            input=full_prompt,
            temperature=1.0, # Set temperature back to 1.0 for variability
            # Add other parameters as needed based on responseapi.md if defaults aren't sufficient
            text={ "format": { "type": "text" } } # Request plain text if API supports this structure directly
        )
        logging.info("Received response from OpenAI.")

        # --- Extracting the text ---
        # According to responseapi.md structure and common SDK patterns:
        # The response.output is an array. The first item is usually the message.
        # The message's content is an array. The first item is usually the output_text.
        optimized_text = None
        if response.output and len(response.output) > 0:
            first_output_item = response.output[0]
            if first_output_item.type == "message" and first_output_item.content and len(first_output_item.content) > 0:
                 first_content_item = first_output_item.content[0]
                 if first_content_item.type == "output_text":
                      optimized_text = first_content_item.text.strip()

        if optimized_text:
            logging.info(f"Successfully optimized text. Result: '{optimized_text}'")
            return make_api_response(data={"optimized_text": optimized_text})
        else:
            logging.error(f"Could not extract optimized text from OpenAI response. Response structure: {response}")
            return make_api_response(error="Failed to parse optimized text from AI response.", status_code=500)

    except openai.APIConnectionError as e:
        logging.error(f"OpenAI API request failed to connect: {e}")
        return make_api_response(error="Failed to connect to OpenAI service.", status_code=503) # 503 Service Unavailable
    except openai.RateLimitError as e:
        logging.error(f"OpenAI API request hit rate limit: {e}")
        return make_api_response(error="Rate limit exceeded for OpenAI service.", status_code=429) # 429 Too Many Requests
    except openai.APIStatusError as e:
        logging.error(f"OpenAI API returned an error status: {e.status_code} - {e.response}")
        return make_api_response(error=f"OpenAI service error: {e.message}", status_code=e.status_code if e.status_code else 500)
    except Exception as e:
        logging.exception(f"Unexpected error calling OpenAI API: {e}") # Log full traceback
        return make_api_response(error="An unexpected error occurred during AI text optimization.", status_code=500) 

@generation_bp.route('/jobs/by-batch/<batch_id>', methods=['GET'])
def get_job_by_batch_id(batch_id):
    """Finds a GenerationJob associated with a specific batch ID."""
    db: Session = None
    try:
        db = next(models.get_db())
        
        # Search for jobs where the result_batch_ids_json contains the batch_id
        # Note: This assumes result_batch_ids_json stores a JSON list like '["batch1", "batch2"]'
        # Using LIKE might be inefficient on large tables without specific indexing.
        # Consider a more robust linking mechanism if performance becomes an issue.
        # FIX: Correctly format the string with escaped quotes
        target_pattern = f'%\"{batch_id}\"%'
        
        job = db.query(GenerationJob).filter(
            GenerationJob.result_batch_ids_json.like(target_pattern)
        ).order_by(GenerationJob.id.desc()).first() # Get the most recent job associated with the batch

        if job:
            return make_api_response(data=model_to_dict(job))
        else:
            return make_api_response(error=f"No generation job found associated with batch ID {batch_id}", status_code=404)

    except Exception as e:
        logging.exception(f"Error searching for job by batch ID {batch_id}: {e}")
        return make_api_response(error="Failed to search for job by batch ID", status_code=500)
    finally:
        if db and db.is_active: db.close() 