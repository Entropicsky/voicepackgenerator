# backend/routes/vo_script_routes.py

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import logging
import json # Added import

# Assuming models and helpers are accessible, adjust imports as necessary
from backend import models, tasks # Added tasks import
from backend.models import get_db
from backend.app import make_api_response, model_to_dict

vo_script_bp = Blueprint('vo_script_api', __name__, url_prefix='/api')

@vo_script_bp.route('/vo-scripts', methods=['POST'])
def create_vo_script():
    """Creates a new VO script instance."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    name = data.get('name')
    template_id = data.get('template_id')
    character_description = data.get('character_description') # This should be a JSON object/dict

    if not name or not template_id or character_description is None:
        return make_api_response(error="Missing required fields: name, template_id, character_description", status_code=400)
    
    try:
        template_id = int(template_id)
    except (ValueError, TypeError):
        return make_api_response(error="template_id must be an integer", status_code=400)
    
    if not isinstance(character_description, dict):
         return make_api_response(error="character_description must be a JSON object", status_code=400)

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
            character_description=character_description,
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
        return make_api_response(data=model_to_dict(new_vo_script), status_code=201)
        
    except IntegrityError as e:
        db.rollback()
        # Should only be FK violation if template disappears mid-request
        logging.exception(f"Database integrity error creating vo_script: {e}")
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
            s_dict = model_to_dict(script, ['id', 'name', 'template_id', 'status', 'updated_at'])
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
    """Gets details for a specific VO script instance, including its lines."""
    db: Session = None
    try:
        db = next(get_db())
        # Eager load related data: template info, lines, and each line's template_line info
        script = db.query(models.VoScript).options(
            joinedload(models.VoScript.template),
            selectinload(models.VoScript.lines).selectinload(models.VoScriptLine.template_line)
        ).get(script_id)
        
        if script is None:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
            
        # Serialize the script and its nested lines
        script_data = model_to_dict(script)
        if script.template:
            script_data['template_name'] = script.template.name
            
        # Order lines based on the template line's order_index
        ordered_lines = sorted(script.lines, key=lambda l: l.template_line.order_index if l.template_line else float('inf'))
        
        script_data['lines'] = [
            { 
              **model_to_dict(line, ['id', 'generated_text', 'status', 'latest_feedback']),
              'line_key': line.template_line.line_key if line.template_line else None, # Get key from template line
              'order_index': line.template_line.order_index if line.template_line else None
            } 
            for line in ordered_lines
        ]
            
        return make_api_response(data=script_data)
    except Exception as e:
        logging.exception(f"Error getting VO script {script_id}: {e}")
        return make_api_response(error="Failed to get VO script", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_script_bp.route('/vo-scripts/<int:script_id>', methods=['PUT'])
def update_vo_script(script_id):
    """Updates an existing VO script instance (name, character_description, status)."""
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
        if 'name' in data:
            new_name = data['name']
            if not new_name:
                 return make_api_response(error="Name cannot be empty", status_code=400)
            if new_name != script.name:
                 script.name = new_name
                 updated = True
                 
        if 'character_description' in data:
            new_desc = data['character_description']
            if not isinstance(new_desc, dict):
                 return make_api_response(error="character_description must be a JSON object", status_code=400)
            if new_desc != script.character_description:
                 script.character_description = new_desc
                 updated = True
                 
        if 'status' in data:
            # Add validation for allowed statuses if needed
            new_status = data['status']
            allowed_statuses = ['drafting', 'review', 'locked'] # Example allowed statuses
            if new_status not in allowed_statuses:
                return make_api_response(error=f"Invalid status '{new_status}'. Allowed: {allowed_statuses}", status_code=400)
            if new_status != script.status:
                 script.status = new_status
                 updated = True

        if not updated:
            return make_api_response(data=model_to_dict(script)) # Return current data if no changes

        db.commit()
        db.refresh(script)
        logging.info(f"Updated VO script ID {script.id}")
        # Return the updated script, but maybe not the lines for brevity?
        # Fetching again to include template name easily
        updated_script = db.query(models.VoScript).options(joinedload(models.VoScript.template)).get(script_id)
        resp_data = model_to_dict(updated_script)
        resp_data['template_name'] = updated_script.template.name if updated_script.template else None
        return make_api_response(data=resp_data)

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
    task_type = data.get('task_type', 'generate_draft') # e.g., 'generate_draft', 'refine_feedback'
    feedback_data = data.get('feedback') # Optional feedback dict/list
    allowed_task_types = ['generate_draft', 'refine_feedback']
    
    if task_type not in allowed_task_types:
        return make_api_response(error=f"Invalid task_type. Allowed: {allowed_task_types}", status_code=400)
        
    db: Session = None
    db_job = None
    try:
        db = next(get_db())
        # Verify script exists
        script = db.query(models.VoScript).get(script_id)
        if not script:
            return make_api_response(error=f"VO Script with ID {script_id} not found", status_code=404)
            
        # Create Job record
        job_params = {"task_type": task_type, "feedback": feedback_data}
        db_job = models.GenerationJob(
            status="PENDING",
            job_type="script_creation", # Specific job type for this agent
            target_batch_id=str(script_id), # Using target_batch_id to store script_id
            parameters_json=json.dumps(job_params) # Store task type and feedback
        )
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        db_job_id = db_job.id
        logging.info(f"Created Script Creation Job DB ID: {db_job_id} for VO Script ID {script_id}")

        # Enqueue Celery task 
        # Ensure the task exists in backend/tasks.py
        task = tasks.run_script_creation_agent.delay(
            db_job_id,
            script_id,
            task_type,
            feedback_data # Pass feedback (can be None)
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

# Other VoScript endpoints (GET lines, POST feedback) can be added later

# Other VoScript CRUD endpoints will be added here... 