# backend/routes/vo_script_routes.py

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import logging
import json # Added import
import os
from datetime import datetime, timezone # Import datetime utils

# Assuming models and helpers are accessible, adjust imports as necessary
from backend import models, tasks # Added tasks import
from backend.models import get_db
from backend.app import make_api_response, model_to_dict
# from backend.tasks import run_script_creation_agent # Celery task for agent runs -> REMOVE/COMMENT OUT
from backend import utils_openai # Import for direct OpenAI calls
from backend import utils_voscript # Import for DB utils

vo_script_bp = Blueprint('vo_script_bp', __name__, url_prefix='/api')

@vo_script_bp.route('/vo-scripts', methods=['POST'])
def create_vo_script():
    """Creates a new VO script instance."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    name = data.get('name')
    template_id = data.get('template_id')
    character_description = data.get('character_description') # Now expecting a string

    # Validate required fields
    if not name or not template_id or character_description is None: # Allow empty description string
        return make_api_response(error="Missing required fields: name, template_id, character_description", status_code=400)
    
    # Validate template_id type
    try:
        template_id = int(template_id)
    except (ValueError, TypeError):
        return make_api_response(error="template_id must be an integer", status_code=400)
    
    # Validate character_description type (should be string)
    if not isinstance(character_description, str):
         return make_api_response(error="character_description must be a string", status_code=400)

    db: Session = None
    try:
        db = next(get_db())
        # Verify template exists
        template = db.query(models.VoScriptTemplate).get(template_id)
        if not template:
            return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)
            
        new_vo_script = models.VoScript(
            name=name,
            template_id=template_id,
            character_description=character_description, # Pass string directly
            status='drafting' # Initial status
        )
        db.add(new_vo_script)
        
        # IMPORTANT: Also create placeholder vo_script_line entries for this new script
        # based on the lines defined in the associated template.
        template_lines = db.query(models.VoScriptTemplateLine).filter(
            models.VoScriptTemplateLine.template_id == template_id
        ).order_by(models.VoScriptTemplateLine.order_index).all() # Ensure order
        
        if not template_lines:
             logging.warning(f"Template ID {template_id} has no lines defined. Creating VO Script anyway.")
        
        vo_script_lines_to_add = []
        for t_line in template_lines:
            vo_script_lines_to_add.append(models.VoScriptLine(
                vo_script=new_vo_script, # Associate with the script being created
                template_line_id=t_line.id,
                status='pending' # Initial status for generation
            ))
            
        if vo_script_lines_to_add:
            db.add_all(vo_script_lines_to_add)
            
        db.commit()
        db.refresh(new_vo_script)
        logging.info(f"Created VO script ID {new_vo_script.id} ('{name}') using template ID {template_id}, added {len(vo_script_lines_to_add)} pending lines.")
        # Include lines in the response? Maybe not for POST, keep it lean.
        # Fetch again to include template name?
        created_script = db.query(models.VoScript).options(joinedload(models.VoScript.template)).get(new_vo_script.id)
        resp_data = model_to_dict(created_script)
        resp_data['template_name'] = created_script.template.name if created_script.template else None
        return make_api_response(data=resp_data, status_code=201)
        
    except IntegrityError as e:
        db.rollback()
        # Could be FK violation if template disappears, or duplicate name if unique constraint added
        logging.exception(f"Database integrity error creating vo_script: {e}")
        # Check for unique constraint violation specifically? Depends on DB schema
        # if "UNIQUE constraint failed" in str(e):
        #     return make_api_response(error=f"VO Script with name '{name}' already exists.", status_code=409)
        return make_api_response(error="Database error creating script.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error creating VO script: {e}")
        return make_api_response(error="Failed to create VO script", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_script_bp.route('/vo-scripts', methods=['GET'])
def list_vo_scripts():
    """Lists all VO script instances."""
    db: Session = None
    try:
        db = next(get_db())
        # Eager load template name for display
        scripts = db.query(models.VoScript).options(
            joinedload(models.VoScript.template)
        ).order_by(models.VoScript.updated_at.desc()).all()
        
        script_list = []
        for script in scripts:
            s_dict = model_to_dict(script, ['id', 'name', 'template_id', 'status', 'updated_at', 'character_description', 'created_at']) # Added missing fields
            # Add template name if loaded
            s_dict['template_name'] = script.template.name if script.template else None
            script_list.append(s_dict)
            
        logging.info(f"Returning {len(script_list)} VO scripts.")
        return make_api_response(data=script_list)
    except Exception as e:
        logging.exception(f"Error listing VO scripts: {e}")
        return make_api_response(error="Failed to list VO scripts", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_script_bp.route('/vo-scripts/<int:script_id>', methods=['GET'])
def get_vo_script(script_id):
    """Gets details for a specific VO script instance, including its lines and refinement prompts."""
    db: Session = None
    try:
        db = next(get_db())
        # Eager load related data: template info, lines, template lines, and categories
        script = db.query(models.VoScript).options(
            joinedload(models.VoScript.template).selectinload(models.VoScriptTemplate.categories), # Load template and its categories
            selectinload(models.VoScript.lines).selectinload(models.VoScriptLine.template_line) # Load lines and their template line link
        ).get(script_id)
        
        if script is None:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
            
        # Serialize the script, including the new refinement_prompt
        script_data = model_to_dict(script) 
        if script.template:
            script_data['template_name'] = script.template.name
            script_data['template_description'] = script.template.description 
            script_data['template_prompt_hint'] = script.template.prompt_hint 
            # Explicitly add categories with their refinement prompts
            template_categories = {
                c.id: {
                    "id": c.id,
                    "name": c.name,
                    "instructions": c.prompt_instructions,
                    "refinement_prompt": c.refinement_prompt
                }
                for c in script.template.categories
            }
        else:
             template_categories = {}
            
        # Organize lines by category, fetching category data from the loaded template_categories dict
        lines_by_category = {}
        ordered_lines = sorted(script.lines, key=lambda l: l.template_line.order_index if l.template_line else float('inf'))
        
        for line in ordered_lines:
            line_dict = { 
              **model_to_dict(line, ['id', 'generated_text', 'status', 'latest_feedback', 'generation_history']), 
              'template_line_id': line.template_line_id, 
              'line_key': line.template_line.line_key if line.template_line else None,
              'order_index': line.template_line.order_index if line.template_line else None,
              'template_prompt_hint': line.template_line.prompt_hint if line.template_line else None,
              'category_id': line.template_line.category_id if line.template_line else None
            }
            
            category_id = line.template_line.category_id if line.template_line else None
            category_info = template_categories.get(category_id) if category_id else None
            
            category_name = category_info['name'] if category_info else "Uncategorized"
            
            if category_name not in lines_by_category:
                 lines_by_category[category_name] = {
                     "id": category_id,
                     'name': category_name,
                     'instructions': category_info['instructions'] if category_info else None,
                     'refinement_prompt': category_info['refinement_prompt'] if category_info else None, # Add category prompt
                     'lines': []
                 }
            lines_by_category[category_name]['lines'].append(line_dict)

        script_data['categories'] = list(lines_by_category.values())
            
        return make_api_response(data=script_data)
    except Exception as e:
        logging.exception(f"Error getting VO script {script_id}: {e}")
        return make_api_response(error="Failed to get VO script", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_script_bp.route('/vo-scripts/<int:script_id>', methods=['PUT'])
def update_vo_script(script_id):
    """Updates an existing VO script instance (name, char desc, status, refinement_prompt)."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    
    db: Session = None
    try:
        db = next(get_db())
        script = db.query(models.VoScript).get(script_id)
        if script is None:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)

        updated = False
        # --- Update Name --- #
        if 'name' in data:
            new_name = data['name']
            if not new_name:
                 return make_api_response(error="Name cannot be empty", status_code=400)
            if new_name != script.name:
                 script.name = new_name
                 updated = True
        
        # --- Update Character Description --- #         
        if 'character_description' in data:
            new_desc = data['character_description']
            if not isinstance(new_desc, str):
                 return make_api_response(error="character_description must be a string", status_code=400)
            if new_desc != script.character_description:
                 script.character_description = new_desc
                 updated = True
        
        # --- Update Refinement Prompt --- #
        if 'refinement_prompt' in data:
             new_prompt = data['refinement_prompt']
             if not isinstance(new_prompt, (str, type(None))):
                 return make_api_response(error="refinement_prompt must be a string or null", status_code=400)
             if new_prompt != script.refinement_prompt:
                  script.refinement_prompt = new_prompt
                  updated = True
        
        # --- Update Status --- #
        if 'status' in data:
            new_status = data['status']
            allowed_statuses = ['drafting', 'review', 'locked'] # Example allowed statuses
            if new_status not in allowed_statuses:
                return make_api_response(error=f"Invalid status '{new_status}'. Allowed: {allowed_statuses}", status_code=400)
            if new_status != script.status:
                 script.status = new_status
                 updated = True

        # If nothing was actually changed, return the current script data 
        if not updated:
             # Return the basic script data (including refinement_prompt)
             return make_api_response(data=model_to_dict(script))

        # Commit changes if any were made
        db.commit()
        db.refresh(script) # Refresh to get updated timestamp etc.
        logging.info(f"Updated VO script ID {script.id}")
        
        # Return the updated basic script data (client can refetch full details if needed)
        return make_api_response(data=model_to_dict(script))

    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating VO script {script_id}: {e}")
        return make_api_response(error="Failed to update VO script", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_script_bp.route('/vo-scripts/<int:script_id>', methods=['DELETE'])
def delete_vo_script(script_id):
    """Deletes a VO script instance and its associated lines."""
    db: Session = None
    try:
        db = next(get_db())
        script = db.query(models.VoScript).get(script_id)
        if script is None:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
        
        script_name = script.name # Get name for logging
        db.delete(script) # Cascade should delete associated VoScriptLine records
        db.commit()
        logging.info(f"Deleted VO script ID {script_id} (Name: '{script_name}')")
        return make_api_response(data={"message": f"VO Script '{script_name}' deleted successfully"})
    except Exception as e:
        db.rollback()
        logging.exception(f"Error deleting VO script {script_id}: {e}")
        return make_api_response(error="Failed to delete VO script", status_code=500)
    finally:
        if db and db.is_active: db.close()

# --- VoScript Agent Trigger --- #

@vo_script_bp.route('/vo-scripts/<int:script_id>/run-agent', methods=['POST'])
def run_vo_script_agent(script_id):
    """Triggers the VO Script creation/refinement agent via Celery."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    task_type = data.get('task_type', 'generate_draft') 
    feedback_data = data.get('feedback') # Optional feedback dict/list for refine_feedback
    category_name = data.get('category_name') # Optional category name for refine_category
    
    # Define allowed task types
    allowed_task_types = ['generate_draft', 'refine_feedback', 'refine_category']
    
    if task_type not in allowed_task_types:
        return make_api_response(error=f"Invalid task_type. Allowed: {allowed_task_types}", status_code=400)
        
    # Validate category_name if task_type requires it
    if task_type == 'refine_category' and not category_name:
         return make_api_response(error="Missing required field 'category_name' for task_type 'refine_category'", status_code=400)
    
    # Ensure category_name is string if provided
    if category_name and not isinstance(category_name, str):
         return make_api_response(error="'category_name' must be a string if provided", status_code=400)
        
    db: Session = None
    db_job = None
    try:
        db = next(get_db())
        # Verify script exists
        script = db.query(models.VoScript).get(script_id)
        if not script:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
            
        # Create Job record
        job_params = {"task_type": task_type} # Base params
        if feedback_data:
             job_params["feedback"] = feedback_data
        if category_name:
             job_params["category_name"] = category_name
             
        db_job = models.GenerationJob(
            status="PENDING",
            job_type="script_creation", 
            target_batch_id=str(script_id), 
            parameters_json=json.dumps(job_params) # Store task type, feedback, category
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created Script Creation Job DB ID: {db_job_id} for VO Script ID {script_id}")

        # Enqueue Celery task
        task = tasks.run_script_creation_agent.delay(
            db_job_id,
            script_id,
            task_type,
            feedback_data, # Pass feedback (can be None)
            category_name # Pass category name (can be None)
        )
        logging.info(f"Enqueued script creation task: Celery ID {task.id}, DB Job ID {db_job_id}")
        
        # Link Celery task ID to Job record
        db_job.celery_task_id = task.id
        db.commit()
        
        return make_api_response(data={'job_id': db_job_id, 'task_id': task.id}, status_code=202)
        
    except Exception as e:
        logging.exception(f"Error submitting script creation job for VO script {script_id}: {e}")
        if db_job and db_job.id and db.is_active: # Mark DB job as failed if possible
            try: 
                db_job.status = "SUBMIT_FAILED"
                db_job.result_message = f"Enqueue failed: {e}"
                db.commit()
            except: 
                db.rollback()
        elif db and db.is_active:
             db.rollback()
        return make_api_response(error="Failed to start script creation task", status_code=500)
    finally:
        if db and db.is_active: db.close()

# --- VoScript Feedback --- #

@vo_script_bp.route('/vo-scripts/<int:script_id>/feedback', methods=['POST'])
def submit_vo_script_feedback(script_id):
    """Submits user feedback for a specific line within a VO script."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    line_id = data.get('line_id')
    feedback_text = data.get('feedback_text')

    if line_id is None or feedback_text is None: # Allow empty feedback text
        return make_api_response(error="Missing required fields: line_id, feedback_text", status_code=400)
    
    try:
        line_id = int(line_id)
    except (ValueError, TypeError):
        return make_api_response(error="line_id must be an integer", status_code=400)
        
    if not isinstance(feedback_text, str):
        return make_api_response(error="feedback_text must be a string", status_code=400)

    db: Session = None
    try:
        db = next(get_db())
        
        # Find the specific VoScriptLine using both script_id and line_id
        script_line = db.query(models.VoScriptLine).filter(
            models.VoScriptLine.vo_script_id == script_id,
            models.VoScriptLine.id == line_id
        ).first()

        if not script_line:
            # Check if the script itself exists to provide a better error message
            script_exists = db.query(models.VoScript.id).filter(models.VoScript.id == script_id).scalar() is not None
            if not script_exists:
                return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
            else:
                return make_api_response(error=f"Line with ID {line_id} not found within VO Script ID {script_id}", status_code=404)

        # Update the feedback field
        script_line.latest_feedback = feedback_text
        
        # Potentially update script status? Or just update the line?
        # For now, just update the line.
        
        db.commit()
        db.refresh(script_line) # Refresh to get updated timestamp if any
        logging.info(f"Updated feedback for VO Script ID {script_id}, Line ID {line_id}")
        
        # Return the updated line info (or just success)
        return make_api_response(data=model_to_dict(script_line, ['id', 'vo_script_id', 'latest_feedback', 'updated_at']))

    except Exception as e:
        db.rollback()
        logging.exception(f"Error submitting feedback for VO script {script_id}, line {line_id}: {e}")
        return make_api_response(error="Failed to submit feedback", status_code=500)
    finally:
        if db and db.is_active: db.close()

# --- NEW: Line Refinement Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/lines/<int:line_id>/refine', methods=['POST'])
def refine_vo_script_line(script_id: int, line_id: int):
    # Import model_to_dict locally if needed to avoid top-level import cycle potential
    from backend.app import model_to_dict 
    """Refines a single VO script line using OpenAI based on user prompt."""
    data = request.get_json()
    if not data or 'line_prompt' not in data:
        logging.warning(f"Refine line request missing 'line_prompt' for script {script_id}, line {line_id}")
        return jsonify({"error": "Missing 'line_prompt' in request body"}), 400
    
    user_prompt = data['line_prompt']
    # Optional: Get model override from request?
    target_model = data.get('model', utils_openai.DEFAULT_REFINEMENT_MODEL)

    db: Session = next(get_db())
    try:
        # 1. Get context for the line
        line_context = utils_voscript.get_line_context(db, line_id)
        if not line_context:
            logging.warning(f"Refine line request: Context not found for script {script_id}, line {line_id}")
            return jsonify({"error": f"Line context not found for line_id {line_id}"}), 404
        
        # Ensure the line belongs to the script specified in the URL (optional check)
        # if line_context['script_id'] != script_id: 
        #     return jsonify({"error": "Line does not belong to the specified script"}), 400
            
        # 2. Construct prompt for OpenAI (Basic Example)
        # TODO: Refine this prompt construction logic significantly!
        openai_prompt = (
            f"You are a creative writer for video game voiceovers.\n"
            f"Character Description:\n{line_context.get('character_description', 'N/A')}\n\n"
            f"Template Hint: {line_context.get('template_hint', 'N/A')}\n"
            f"Category: {line_context.get('category_name', 'N/A')}\n"
            f"Category Instructions: {line_context.get('category_instructions', 'N/A')}\n"
            f"Line Key: {line_context.get('line_key', 'N/A')}\n"
            f"Line Hint: {line_context.get('line_template_hint', 'N/A')}\n\n"
            f"Current Line Text:\n{line_context.get('current_text', '')}\n\n"
            f"User Refinement Request: \"{user_prompt}\"\n\n"
            f"Rewrite the 'Current Line Text' based ONLY on the 'User Refinement Request', while staying consistent with the character description and other hints. "
            f"Only output the refined line text, with no extra explanation or preamble. If no change is needed based on the request, output the original text exactly."
        )
        
        logging.info(f"Sending prompt to OpenAI for line {line_id}. Prompt start: {openai_prompt[:200]}...") # Log start of prompt

        # 3. Call OpenAI Responses API
        refined_text = utils_openai.call_openai_responses_api(
            prompt=openai_prompt,
            model=target_model
            # Pass other params like temperature if needed
        )
        
        if refined_text is None:
            logging.error(f"OpenAI refinement failed for script {script_id}, line {line_id}")
            return jsonify({"error": "OpenAI refinement failed. Check logs."}), 500
            
        logging.info(f"Refined text received for line {line_id}: '{refined_text[:100]}...'")

        # 4. Update Database
        # Determine new status - simple logic for now
        new_status = "review" if refined_text != line_context.get('current_text') else line_context.get('status', 'generated')
        
        updated_line = utils_voscript.update_line_in_db(
            db, 
            line_id, 
            refined_text, 
            new_status, 
            target_model # Log which model did the refinement
        )
        
        if updated_line is None:
            logging.error(f"Database update failed after refinement for script {script_id}, line {line_id}")
            # DB already rolled back in utility function
            return jsonify({"error": "Database update failed after refinement."}), 500

        # 5. Return updated line data
        # Use model_to_dict or similar serialization
        return jsonify({"data": model_to_dict(updated_line)}), 200

    except Exception as e:
        # Log any unexpected errors during the process
        logging.exception(f"Unexpected error during line refinement for script {script_id}, line {line_id}: {e}")
        # Ensure DB session is rolled back if error occurred before update_line_in_db handled it
        if db.is_active:
             try: db.rollback()
             except: pass # Ignore rollback errors
        return jsonify({"error": "An unexpected error occurred during refinement."}), 500
    finally:
        # Ensure DB session is closed
        if db:
            db.close()

# --- NEW: Category Refinement Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/categories/refine', methods=['POST'])
def refine_vo_script_category(script_id: int):
    """Refines all VO script lines within a category using OpenAI.
       Incorporates global script prompt and line feedback into the prompt.
    """
    from backend.app import model_to_dict # Import locally
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request body"}), 400
    
    category_name = data.get('category_name')
    category_prompt = data.get('category_prompt')
    target_model = data.get('model', utils_openai.DEFAULT_REFINEMENT_MODEL)

    if not category_name:
        return jsonify({"error": "Missing 'category_name' in request body"}), 400
    if not category_prompt:
         return jsonify({"error": "Missing 'category_prompt' in request body"}), 400

    db: Session = next(get_db())
    updated_lines_data = []
    errors_occurred = False
    try:
        # 1. Get context (now includes script prompt)
        lines_to_process = utils_voscript.get_category_lines_context(db, script_id, category_name)
        
        if not lines_to_process:
            logging.info(f"No lines found for category '{category_name}' in script {script_id}. Nothing to refine.")
            return jsonify({"data": []}), 200 

        logging.info(f"Found {len(lines_to_process)} potential lines to refine for category '{category_name}' in script {script_id}.")

        # 2. Iterate and refine each NON-LOCKED line
        for line_context in lines_to_process:
            line_id = line_context['line_id']
            
            # ---> ADD CHECK FOR LOCK STATUS <--- #
            if line_context.get('is_locked', False): # Default to False if key missing (shouldn't happen)
                logging.info(f"Skipping locked line {line_id} during category refinement.")
                continue # Skip to the next line
                
            # Construct Hierarchical Prompt
            script_prompt_text = line_context.get('script_refinement_prompt') or "N/A"
            line_feedback_text = line_context.get('latest_feedback') or "N/A"
            
            openai_prompt = (
                f"You are a creative writer for video game voiceovers.\n"
                f"Character Description:\n{line_context.get('character_description', 'N/A')}\n\n"
                f"Template Hint: {line_context.get('template_hint', 'N/A')}\n"
                f"Category: {line_context.get('category_name', 'N/A')}\n"
                f"Category Instructions: {line_context.get('category_instructions', 'N/A')}\n"
                f"Line Key: {line_context.get('line_key', 'N/A')}\n"
                f"Line Hint: {line_context.get('line_template_hint', 'N/A')}\n\n"
                f"--- Prompts (Apply these hierarchically) ---\n"
                f"Global Script Prompt: {script_prompt_text}\n"
                f"Category Prompt: {category_prompt}\n"
                f"Line Feedback/Prompt: {line_feedback_text}\n"
                f"--- End Prompts ---\n\n"
                f"Current Line Text:\n{line_context.get('current_text', '')}\n\n"
                f"Rewrite the 'Current Line Text' based on ALL applicable prompts above (Global, Category, Line), while staying consistent with the character description and other hints. Prioritize the most specific prompt if conflicts arise. "
                f"Only output the refined line text, with no extra explanation or preamble. If no change is needed based on the prompts, output the original text exactly."
            )
            
            logging.info(f"Sending hierarchical category-refine prompt to OpenAI for line {line_id}...")
            refined_text = utils_openai.call_openai_responses_api(
                prompt=openai_prompt,
                model=target_model
            )

            if refined_text is None:
                logging.error(f"OpenAI category refinement failed for script {script_id}, line {line_id}")
                errors_occurred = True 
                continue 
            
            logging.info(f"Refined text received for line {line_id} via category refine.")

            # Update Database for this line
            new_status = "review" if refined_text != line_context.get('current_text') else line_context.get('status', 'generated')
            updated_line = utils_voscript.update_line_in_db(
                db, line_id, refined_text, new_status, target_model
            )
            
            if updated_line is None:
                logging.error(f"Database update failed after category refinement for script {script_id}, line {line_id}")
                errors_occurred = True 
            else:
                updated_lines_data.append(model_to_dict(updated_line)) 

        # 3. Return results
        if errors_occurred:
             status_code = 207 # Multi-Status
             message = "Category refinement completed with some errors."
        else:
             status_code = 200
             message = "Category refinement completed successfully."
             
        return jsonify({"message": message, "data": updated_lines_data}), status_code

    except Exception as e:
        logging.exception(f"Unexpected error during category refinement for script {script_id}, category {category_name}: {e}")
        if db.is_active: 
            try: db.rollback()
            except: pass
        return jsonify({"error": "An unexpected error occurred during category refinement."}), 500
    finally:
        if db:
            db.close()

# --- NEW: Script Refinement Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/refine', methods=['POST'])
def refine_vo_script(script_id: int):
    """Refines all VO script lines for a script using OpenAI based on global,
       category, and line prompts.
    """
    from backend.app import model_to_dict # Import locally
    data = request.get_json()
    
    global_prompt = data.get('global_prompt') if data else None
    if not global_prompt:
        return jsonify({"error": "Missing 'global_prompt' in request body"}), 400
        
    target_model = data.get('model', utils_openai.DEFAULT_REFINEMENT_MODEL)

    db: Session = next(get_db())
    updated_lines_data = []
    errors_occurred = False
    try:
        # 1. Get context (now includes script prompt and category prompts)
        lines_to_process = utils_voscript.get_script_lines_context(db, script_id)
        
        if not lines_to_process:
            logging.info(f"No lines found for script {script_id}. Nothing to refine.")
            return jsonify({"data": []}), 200 

        logging.info(f"Found {len(lines_to_process)} potential lines to refine for script {script_id}.")

        # 2. Iterate and refine each NON-LOCKED line
        for line_context in lines_to_process:
            line_id = line_context['line_id']
            
            # ---> ADD CHECK FOR LOCK STATUS <--- #
            if line_context.get('is_locked', False):
                logging.info(f"Skipping locked line {line_id} during script refinement.")
                continue # Skip to the next line
                
            # Construct Hierarchical Prompt
            script_prompt_text = line_context.get('script_refinement_prompt') or "N/A" # Already included from get_script_lines_context
            category_prompt_text = line_context.get('category_refinement_prompt') or "N/A"
            line_feedback_text = line_context.get('latest_feedback') or "N/A"
            
            # TODO: Further refine prompt structure and instructions
            openai_prompt = (
                f"You are a creative writer for video game voiceovers.\n"
                f"Character Description:\n{line_context.get('character_description', 'N/A')}\n\n"
                f"Template Hint: {line_context.get('template_hint', 'N/A')}\n"
                f"Category: {line_context.get('category_name', 'N/A')}\n"
                f"Category Instructions: {line_context.get('category_instructions', 'N/A')}\n"
                f"Line Key: {line_context.get('line_key', 'N/A')}\n"
                f"Line Hint: {line_context.get('line_template_hint', 'N/A')}\n\n"
                f"--- Prompts (Apply these hierarchically) ---\n"
                f"Global Script Prompt: {global_prompt}\n" # Use prompt from request here
                f"Category Prompt: {category_prompt_text}\n"
                f"Line Feedback/Prompt: {line_feedback_text}\n"
                f"--- End Prompts ---\n\n"
                f"Current Line Text:\n{line_context.get('current_text', '')}\n\n"
                f"Rewrite the 'Current Line Text' based on ALL applicable prompts above (Global, Category, Line), while staying consistent with the character description and other hints. Prioritize the most specific prompt if conflicts arise. "
                f"Only output the refined line text, with no extra explanation or preamble. If no change is needed based on the prompts, output the original text exactly."
            )
            
            logging.info(f"Sending hierarchical script-refine prompt to OpenAI for line {line_id}...")
            refined_text = utils_openai.call_openai_responses_api(
                prompt=openai_prompt,
                model=target_model
            )

            if refined_text is None:
                logging.error(f"OpenAI script refinement failed for script {script_id}, line {line_id}")
                errors_occurred = True 
                continue 
            
            logging.info(f"Refined text received for line {line_id} via script refine.")

            # Update Database for this line
            new_status = "review" if refined_text != line_context.get('current_text') else line_context.get('status', 'generated')
            updated_line = utils_voscript.update_line_in_db(
                db, line_id, refined_text, new_status, target_model
            )
            
            if updated_line is None:
                logging.error(f"Database update failed after script refinement for script {script_id}, line {line_id}")
                errors_occurred = True
            else:
                updated_lines_data.append(model_to_dict(updated_line)) 

        # 3. Return results
        if errors_occurred:
             status_code = 207 # Multi-Status
             message = "Script refinement completed with some errors."
        else:
             status_code = 200
             message = "Script refinement completed successfully."
             
        return jsonify({"message": message, "data": updated_lines_data}), status_code

    except Exception as e:
        logging.exception(f"Unexpected error during script refinement for script {script_id}: {e}")
        if db.is_active: 
            try: db.rollback()
            except: pass
        return jsonify({"error": "An unexpected error occurred during script refinement."}), 500
    finally:
        if db:
            db.close()

# --- NEW: Line Locking Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/lines/<int:line_id>/toggle-lock', methods=['PATCH'])
def toggle_lock_vo_script_line(script_id: int, line_id: int):
    """Toggles the is_locked status of a specific VO script line."""
    # from backend.app import model_to_dict # Import locally - not needed if manually constructing dict
    db: Session = next(get_db())
    try:
        # Find the specific line, ensuring it belongs to the correct script
        line = db.query(models.VoScriptLine).filter(
            models.VoScriptLine.id == line_id,
            models.VoScriptLine.vo_script_id == script_id
        ).first()

        if not line:
            return jsonify({"error": f"Line not found with ID {line_id} for script {script_id}"}), 404
        
        # Toggle the status
        line.is_locked = not line.is_locked
        new_lock_status = line.is_locked
        
        db.commit()
        db.refresh(line)
        logging.info(f"Toggled lock status for line {line_id} (script {script_id}) to {new_lock_status}")
        
        # Manually construct response dict with specific fields
        response_data = {
            "id": line.id,
            "is_locked": line.is_locked,
            "updated_at": line.updated_at.isoformat() if line.updated_at else None
        }
        return jsonify({"data": response_data}), 200

    except Exception as e:
        db.rollback()
        logging.exception(f"Error toggling lock for line {line_id}, script {script_id}: {e}")
        return jsonify({"error": "Failed to toggle lock status."}), 500
    finally:
        if db:
            db.close()

# --- NEW: Manual Text Update Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/lines/<int:line_id>/update-text', methods=['PATCH'])
def update_vo_script_line_text(script_id: int, line_id: int):
    """Updates the generated_text for a specific line (manual edit)."""
    # from backend.app import model_to_dict # Import locally - No longer needed
    data = request.get_json()
    if not data or 'generated_text' not in data:
        return jsonify({"error": "Missing 'generated_text' in request body"}), 400
    
    new_text = data['generated_text']
    if not isinstance(new_text, str):
         return jsonify({"error": "'generated_text' must be a string"}), 400
         
    db: Session = next(get_db())
    try:
        line = db.query(models.VoScriptLine).filter(
            models.VoScriptLine.id == line_id,
            models.VoScriptLine.vo_script_id == script_id
        ).first()

        if not line:
            return jsonify({"error": f"Line not found with ID {line_id} for script {script_id}"}), 404
        
        # Update text and set status to 'manual'
        line.generated_text = new_text
        line.status = 'manual' 
        line.latest_feedback = None # Clear feedback on manual edit
        
        # Add to history (optional but good practice)
        current_history = line.generation_history if isinstance(line.generation_history, list) else []
        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "manual_edit",
            "text": new_text,
            "model": "user"
        }
        current_history.append(history_entry)
        line.generation_history = current_history
        
        db.commit()
        db.refresh(line)
        logging.info(f"Manually updated text for line {line_id} (script {script_id})")
        
        # Manually construct response dict
        response_data = {
            "id": line.id,
            "vo_script_id": line.vo_script_id,
            "template_line_id": line.template_line_id,
            "category_id": line.category_id,
            "generated_text": line.generated_text,
            "status": line.status,
            "latest_feedback": line.latest_feedback,
            "generation_history": line.generation_history,
            "line_key": line.line_key,
            "order_index": line.order_index,
            "prompt_hint": line.prompt_hint,
            "is_locked": line.is_locked,
            "created_at": line.created_at.isoformat() if line.created_at else None,
            "updated_at": line.updated_at.isoformat() if line.updated_at else None
        }
        return jsonify({"data": response_data}), 200 # Return full updated line manually constructed

    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating text for line {line_id}, script {script_id}: {e}")
        return jsonify({"error": "Failed to update line text."}), 500
    finally:
        if db:
            db.close()
            
# --- NEW: Delete Line Endpoint --- #
@vo_script_bp.route('/vo-scripts/<int:script_id>/lines/<int:line_id>', methods=['DELETE'])
def delete_vo_script_line(script_id: int, line_id: int):
    """Deletes a specific VO script line."""
    db: Session = next(get_db())
    try:
        line = db.query(models.VoScriptLine).filter(
            models.VoScriptLine.id == line_id,
            models.VoScriptLine.vo_script_id == script_id
        ).first()

        if not line:
            return jsonify({"error": f"Line not found with ID {line_id} for script {script_id}"}), 404
            
        db.delete(line)
        db.commit()
        logging.info(f"Deleted line {line_id} from script {script_id}")
        
        return jsonify({"message": "Line deleted successfully"}), 200

    except Exception as e:
        db.rollback()
        logging.exception(f"Error deleting line {line_id}, script {script_id}: {e}")
        return jsonify({"error": "Failed to delete line."}), 500
    finally:
        if db:
            db.close()

# Other VoScript endpoints (GET lines, POST feedback) can be added later

# Other VoScript CRUD endpoints will be added here... 