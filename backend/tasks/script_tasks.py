# backend/tasks/script_tasks.py
"""
Tasks for script generation and management.
"""
from backend.celery_app import celery
from celery.utils.log import get_task_logger # Import Celery task logger
from backend import models
from backend import utils_voscript
from backend.script_agents.script_writer import ScriptWriterAgent
from celery import Task
from celery.exceptions import Ignore
from sqlalchemy.orm import Session
import json
from datetime import datetime
import os
import logging
import traceback
from backend.agents.script_collaborator_agent import ScriptCollaboratorAgent, ProposedModificationResponse, AddToScratchpadResponse, GetLineDetailsResponse, ScriptContextResponse # Import all Pydantic response types from tools
from agents import Runner
# Attempt to import specific result item types if available, otherwise use attribute checking
# from agents.results import ToolCallOutputItem # This import path is a guess

# Get a logger for this module/task
logger = get_task_logger(__name__)

print("Celery Worker: Loading script_tasks.py...")

@celery.task(bind=True, base=Task, name='tasks.run_script_creation_agent')
def run_script_creation_agent(self, 
                              generation_job_db_id: int, 
                              vo_script_id: int, 
                              task_type: str, 
                              feedback_data: dict | None,
                              category_name: str | None = None):
    """Celery task to run the ScriptWriterAgent."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received script agent task.")
    print(f"  VO Script ID: {vo_script_id}")
    print(f"  Task Type: {task_type}")
    print(f"  Category Name: {category_name}")
    print(f"  Feedback Data: {feedback_data}")
    
    db: Session = next(models.get_db())
    db_job = None
    try:
        # --- 1. Update Job Status to STARTED --- 
        db_job = db.query(models.GenerationJob).filter(models.GenerationJob.id == generation_job_db_id).first()
        if not db_job:
            raise Ignore("GenerationJob record not found.")
        
        db_job.status = "STARTED"
        db_job.started_at = datetime.utcnow()
        db_job.celery_task_id = task_id
        # Store category name in job parameters if provided
        job_params = {}
        try: 
            job_params = json.loads(db_job.parameters_json) if db_job.parameters_json else {}
        except json.JSONDecodeError:
             logging.warning(f"[Task ID: {task_id}] Could not parse existing job parameters JSON.")

        job_params['task_type'] = task_type # Ensure task_type is always there
        if category_name:
           job_params['category_name'] = category_name
        if feedback_data: # Include feedback if provided
             job_params['feedback'] = feedback_data
             
        db_job.parameters_json = json.dumps(job_params)
        db.commit()
        self.update_state(state='STARTED', meta={'status': f'Agent task started ({task_type}, Category: {category_name or "All"})', 'db_id': generation_job_db_id})
        
        # --- 2. Instantiate Agent --- 
        agent_model_name = os.environ.get('OPENAI_AGENT_MODEL', 'gpt-4o')
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Using Agent Model: {agent_model_name}")
        agent_instance = ScriptWriterAgent(model_name=agent_model_name)
        
        # --- 3. Prepare Agent Input --- 
        initial_prompt = ""
        
        # --- Construct Agent Prompt --- #
        base_instruction = ""
        target_statuses = []

        if task_type == 'generate_draft':
             base_instruction = f"Generate the initial draft for all 'pending' lines in VO Script ID {vo_script_id}. Focus on fulfilling the core request for each line based on its key, hints, category instructions, and the character description provided by the get_vo_script_details tool."
             target_statuses = ['pending'] # Agent should only ask for pending lines
        else:
             # Now only draft is supported by this task
             raise ValueError(f"Unsupported task_type ('{task_type}') for agent task. Only 'generate_draft' allowed.")

        initial_prompt = f"{base_instruction} Target lines with statuses {target_statuses}. Use the available tools (get_vo_script_details, get_lines_for_processing, update_script_line) to fetch script details and update lines."
        
        logging.info(f"[Task ID: {task_id}] Agent instructed to target statuses: {target_statuses}")
        
        # --- End Construct Agent Prompt --- #

        # --- 4. Run the Agent --- 
        print(f"[Task ID: {task_id}] Running agent with prompt: {initial_prompt[:200]}...")
        agent_result = agent_instance.run(initial_prompt=initial_prompt)

        # --- 5. Process Agent Result --- 
        if hasattr(agent_result, 'final_output') and agent_result.final_output:
             final_status = "SUCCESS"
             result_msg = f"Agent successfully completed task '{task_type}' for script {vo_script_id}. Output: {agent_result.final_output}"
        else:
             final_status = "FAILURE"
             output_for_error = getattr(agent_result, 'final_output', '[No Output]') 
             result_msg = f"Agent task '{task_type}' failed or produced no output for script {vo_script_id}. Last Output: {output_for_error}"

        # --- 6. Update Job Status --- 
        db_job.status = final_status
        db_job.completed_at = datetime.utcnow()
        db_job.result_message = result_msg
        db.commit()
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Agent task finished. Updated job status to {final_status}.")
        
        return {'status': final_status, 'message': result_msg}
        
    except Exception as e:
        error_msg = f"Script agent task failed unexpectedly: {type(e).__name__}: {e}"
        print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] {error_msg}")
        if db_job:
            db_job.status = "FAILURE"; db_job.completed_at = datetime.utcnow(); db_job.result_message = error_msg
            try: db.commit()
            except: db.rollback()
        self.update_state(state='FAILURE', meta={'status': error_msg, 'db_id': generation_job_db_id})
        raise e
    finally:
        if db: db.close()

@celery.task(bind=True, name='tasks.generate_category_lines')
def generate_category_lines(self, 
                            generation_job_db_id: int, 
                            vo_script_id: int, 
                            category_name: str, 
                            target_model: str = None):
    """Celery task to generate all pending lines in a category together, ensuring variety."""
    task_id = self.request.id
    print(f"[Task ID: {task_id}, DB ID: {generation_job_db_id}] Received category batch generation task.")
    print(f"  VO Script ID: {vo_script_id}")
    print(f"  Category Name: {category_name}")
    print(f"  Target Model: {target_model or 'Default Model'}")
    
    db = None
    db_job = None
    result = {
        "status": "FAILED",
        "message": "Task not processed",
        "updated_lines": [],
        "errors": []
    }
    
    try:
        db = next(models.get_db())
        db_job = db.query(models.GenerationJob).get(generation_job_db_id)
        
        if not db_job:
            print(f"[Task ID: {task_id}] ERROR: Could not find GenerationJob with ID {generation_job_db_id}")
            result["message"] = f"Job record not found: {generation_job_db_id}"
            return result
        
        # Update job status to PROCESSING
        db_job.status = "PROCESSING"
        db_job.started_at = datetime.now()
        db.commit()
        db.refresh(db_job)
        
        # Get the VO Script to verify it exists
        vo_script = db.query(models.VoScript).get(vo_script_id)
        if not vo_script:
            print(f"[Task ID: {task_id}] ERROR: VO Script with ID {vo_script_id} not found")
            db_job.status = "FAILED"
            db_job.completed_at = datetime.now()
            db_job.result_message = f"VO Script with ID {vo_script_id} not found"
            db.commit()
            result["message"] = f"VO Script not found: {vo_script_id}"
            return result
            
        print(f"[Task ID: {task_id}] Working with VO Script: {vo_script.name} (ID: {vo_script_id})")
        
        # Find pending lines for this script that belong to the specified category
        # First, find the category ID based on the name
        print(f"[Task ID: {task_id}] Finding pending lines for category '{category_name}' in script {vo_script_id}")
        
        # Get template category ID from VoScriptTemplateCategory
        template_category = db.query(models.VoScriptTemplateCategory).filter(
            models.VoScriptTemplateCategory.name == category_name
        ).first()
        
        if not template_category:
            # Try another approach - get directly from a line that has this category (using template_line relationship)
            print(f"[Task ID: {task_id}] WARNING: Could not find template category '{category_name}' directly")
            
            # Query all lines and check their category through relationships
            all_category_lines = []
            all_lines = db.query(models.VoScriptLine).filter(
                models.VoScriptLine.vo_script_id == vo_script_id
            ).all()
            
            category_id = None
            for line in all_lines:
                if hasattr(line, 'template_line') and line.template_line:
                    if hasattr(line.template_line, 'category') and line.template_line.category:
                        if line.template_line.category.name == category_name:
                            category_id = line.template_line.category.id
                            break
            
            if category_id is None:
                print(f"[Task ID: {task_id}] ERROR: Could not find any lines with category '{category_name}'")
                db_job.status = "FAILED"
                db_job.completed_at = datetime.now()
                db_job.result_message = f"Could not find any lines with category '{category_name}'"
                db.commit()
                result["message"] = f"Category not found: {category_name}"
                return result
                
            # Now filter by the found category_id
            print(f"[Task ID: {task_id}] Found category ID {category_id} for '{category_name}' from existing lines")
            pending_lines = db.query(models.VoScriptLine).filter(
                models.VoScriptLine.vo_script_id == vo_script_id,
                models.VoScriptLine.category_id == category_id,
                models.VoScriptLine.status == "pending"
            ).order_by(models.VoScriptLine.order_index).all()
        else:
            # We found the category directly
            category_id = template_category.id
            print(f"[Task ID: {task_id}] Found category ID {category_id} for '{category_name}'")
            
            # Get all pending lines with this category ID
            pending_lines = db.query(models.VoScriptLine).filter(
                models.VoScriptLine.vo_script_id == vo_script_id,
                models.VoScriptLine.category_id == category_id,
                models.VoScriptLine.status == "pending"
            ).order_by(models.VoScriptLine.order_index).all()
        
        if not pending_lines:
            print(f"[Task ID: {task_id}] No pending lines found for category '{category_name}' in script {vo_script_id}")
            db_job.status = "SUCCESS"
            db_job.completed_at = datetime.now()
            db_job.result_message = "No pending lines found for generation"
            db.commit()
            result["status"] = "SUCCESS"
            result["message"] = "No pending lines to process"
            return result
        
        # Prepare the line contexts for batch generation
        line_contexts = []
        for line in pending_lines:
            line_contexts.append({
                "id": line.id,
                "line_key": line.line_key, 
                "order_index": line.order_index,
                "context": line.prompt_hint or "No additional context provided"
            })
            logging.info(f"Added line to contexts: id={line.id}, key={line.line_key}, status={line.status}")
        
        # Get model-related settings
        # Use target_model if provided, else use default from env
        model_to_use = target_model or os.getenv("OPENAI_MODEL", "gpt-4o")
        print(f"[Task ID: {task_id}] Using model: {model_to_use}")
        
        # Call the batch generation function from vo_script_routes
        from backend.routes.vo_script_routes import _generate_lines_batch
        
        # Existing lines not needed with context-based implementation
        existing_lines = None
        
        try:
            print(f"[Task ID: {task_id}] Calling batch generation for {len(line_contexts)} lines")
            generated_batch = _generate_lines_batch(
                db=db,
                script_id=vo_script_id, 
                pending_lines=line_contexts,
                existing_lines=existing_lines,
                target_model=model_to_use
            )
            
            if not generated_batch:
                print(f"[Task ID: {task_id}] Batch generation returned no results")
                db_job.status = "FAILED"
                db_job.completed_at = datetime.now()
                db_job.result_message = "Batch generation returned no results"
                db.commit()
                result["message"] = "Batch generation failed to return results"
                return result
            
            # Log complete result of batch generation
            print(f"[Task ID: {task_id}] Generated batch result: {generated_batch}")
            
            # Update the database with the generated lines
            print(f"[Task ID: {task_id}] Processing {len(generated_batch)} generated lines")
            
            # Track updated line IDs
            updated_lines = []
            error_lines = []
            
            for gen_item in generated_batch:
                try:
                    line_id = gen_item.get("line_id")
                    generated_text = gen_item.get("generated_text")
                    
                    print(f"[Task ID: {task_id}] Processing generated item: {gen_item}")
                    
                    if not line_id or not generated_text:
                        print(f"[Task ID: {task_id}] Skipping invalid generated item: {gen_item}")
                        error_lines.append({
                            "line_id": line_id,
                            "error": "Missing line_id or generated_text in result"
                        })
                        continue
                    
                    # Update the line in the database
                    line = db.query(models.VoScriptLine).get(line_id)
                    if not line:
                        print(f"[Task ID: {task_id}] Could not find line with ID {line_id}")
                        error_lines.append({
                            "line_id": line_id,
                            "error": "Line not found in database"
                        })
                        continue
                    
                    line.generated_text = generated_text
                    line.status = "generated"
                    line.generated_at = datetime.now()
                    db.commit()
                    db.refresh(line)
                    
                    updated_lines.append({
                        "id": line.id,
                        "line_key": line.line_key,
                        "text": line.generated_text
                    })
                    print(f"[Task ID: {task_id}] Updated line {line.id} ({line.line_key})")
                    
                except Exception as line_err:
                    print(f"[Task ID: {task_id}] Error updating line: {line_err}")
                    if 'line_id' in locals():
                        error_lines.append({
                            "line_id": line_id,
                            "error": str(line_err)
                        })
                    else:
                        error_lines.append({
                            "error": f"Error processing generated item: {str(line_err)}"
                        })
            
            # Update the job record
            if error_lines and not updated_lines:
                db_job.status = "FAILED"
                db_job.result_message = f"Failed to update any lines. Errors: {len(error_lines)}"
                result["status"] = "FAILED"
                result["message"] = f"No lines were successfully updated"
            elif error_lines:
                db_job.status = "COMPLETED_WITH_ERRORS"
                db_job.result_message = f"Updated {len(updated_lines)} lines with {len(error_lines)} errors"
                result["status"] = "PARTIAL_SUCCESS"
                result["message"] = f"Updated {len(updated_lines)} lines with {len(error_lines)} errors"
            else:
                db_job.status = "SUCCESS"
                db_job.result_message = f"Successfully updated {len(updated_lines)} lines"
                result["status"] = "SUCCESS"
                result["message"] = f"Successfully updated all {len(updated_lines)} lines"
            
            db_job.completed_at = datetime.now()
            db.commit()
            
            # Prepare the result data
            result["updated_lines"] = updated_lines
            result["errors"] = error_lines
            
            print(f"[Task ID: {task_id}] Task completed with status: {result['status']}")
            return result
            
        except Exception as gen_err:
            print(f"[Task ID: {task_id}] Error during batch generation: {gen_err}")
            db_job.status = "FAILED"
            db_job.completed_at = datetime.now()
            db_job.result_message = f"Batch generation error: {str(gen_err)}"
            db.commit()
            
            result["message"] = f"Error during batch generation: {str(gen_err)}"
            # Include traceback for debugging
            result["errors"].append({
                "error": str(gen_err),
                "traceback": traceback.format_exc()
            })
            return result
    
    except Exception as e:
        print(f"[Task ID: {task_id}] Task exception: {e}")
        # If we have a db session and job, try to update it
        try:
            if db and db_job:
                db_job.status = "FAILED"
                db_job.completed_at = datetime.now()
                db_job.result_message = f"Task error: {str(e)}"
                db.commit()
        except Exception as db_err:
            print(f"[Task ID: {task_id}] Failed to update job status after error: {db_err}")
        
        # Include traceback for debugging
        result["message"] = f"Task error: {str(e)}"
        result["errors"].append({
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return result
    
    finally:
        # Ensure database session is closed
        if db:
            try:
                db.close()
                print(f"[Task ID: {task_id}] Database session closed")
            except:
                pass 

@celery.task(name="run_script_collaborator_chat")
def run_script_collaborator_chat_task(script_id: int, user_message: str, initial_prompt_context_from_prior_sessions: list = None, current_context: dict = None):
    logger.info(f"Starting ScriptCollaboratorAgent task for SID: {script_id}, Msg: '{user_message[:50]}...'")
    if initial_prompt_context_from_prior_sessions is None: initial_prompt_context_from_prior_sessions = []
    if current_context is None: current_context = {}

    try:
        agent = ScriptCollaboratorAgent()
        logger.info(f"Running Agent with Msg: '{user_message}'")
        agent_run_result = Runner.run_sync(agent, user_message)

        proposals_for_frontend = []
        scratchpad_updates_for_frontend = []
        logger.info(f"Agent run finished. Final Output: {agent_run_result.final_output[:200]}...")

        if hasattr(agent_run_result, 'new_items') and agent_run_result.new_items:
            logger.info(f"Processing {len(agent_run_result.new_items)} new_items from agent run.")
            for i, run_item_wrapper in enumerate(agent_run_result.new_items):
                wrapper_type_name = type(run_item_wrapper).__name__
                actual_item_content = getattr(run_item_wrapper, 'item', run_item_wrapper) # Use wrapper if item is not distinct
                item_type_name = type(actual_item_content).__name__ if actual_item_content is not run_item_wrapper else wrapper_type_name
                
                logger.info(f"Item {i+1}: WrapperType='{wrapper_type_name}', ActualItemContentType='{item_type_name}'")

                if wrapper_type_name == 'ToolCallOutputItem':
                    logger.info(f"  [ToolCallOutputItem Wrapper Detected for item {i+1}]")
                    logger.info(f"    Attributes of wrapper ({wrapper_type_name}): {dir(run_item_wrapper)}")
                    
                    tool_function_output = getattr(run_item_wrapper, 'output', None)
                    logger.info(f"    run_item_wrapper.output: {str(tool_function_output)[:500]} (Type: {type(tool_function_output).__name__})")

                    if hasattr(run_item_wrapper, 'raw_item'):
                        raw_item_content = run_item_wrapper.raw_item
                        logger.info(f"    run_item_wrapper.raw_item: {str(raw_item_content)[:500]} (Type: {type(raw_item_content).__name__})")
                        if isinstance(raw_item_content, dict):
                             raw_item_actual_output = raw_item_content.get('output')
                             logger.info(f"    run_item_wrapper.raw_item['output']: {str(raw_item_actual_output)[:500]} (Type: {type(raw_item_actual_output).__name__})")
                             if tool_function_output is None and raw_item_actual_output is not None:
                                logger.info("    Using run_item_wrapper.raw_item['output'] as tool_function_output.")
                                tool_function_output = raw_item_actual_output
                    
                    # This is where we process the extracted output
                    if isinstance(tool_function_output, ProposedModificationResponse):
                        if tool_function_output.proposal:
                            logger.info(f"    Extracted PROPOSAL (Pydantic): {tool_function_output.proposal.proposal_id}")
                            proposals_for_frontend.append(tool_function_output.proposal.model_dump())
                    elif isinstance(tool_function_output, AddToScratchpadResponse):
                        if tool_function_output.status == 'success':
                            logger.info(f"    Extracted SCRATCHPAD_UPDATE (Pydantic): {tool_function_output.note_id}")
                            scratchpad_updates_for_frontend.append(tool_function_output.model_dump())
                    elif isinstance(tool_function_output, dict):
                        logger.info(f"    Tool output is a dictionary: {str(tool_function_output)[:200]}")
                        if 'proposal' in tool_function_output and isinstance(tool_function_output['proposal'], dict):
                            proposals_for_frontend.append(tool_function_output['proposal'])
                            logger.info(f"      Appended proposal from dict: {tool_function_output['proposal'].get('proposal_id')}")
                        elif 'note_id' in tool_function_output and 'status' in tool_function_output:
                            scratchpad_updates_for_frontend.append(tool_function_output)
                            logger.info(f"      Appended scratchpad from dict: {tool_function_output.get('note_id')}")
                    else:
                        logger.warning(f"    ToolCallOutputItem's output was not a recognized Pydantic model or dict. Type: {type(tool_function_output).__name__}")
                
                elif wrapper_type_name == 'ToolCallItem' and actual_item_content is not run_item_wrapper:
                    tool_name = getattr(actual_item_content, 'name', 'Unknown Tool')
                    tool_args = getattr(actual_item_content, 'arguments', '{}')
                    logger.info(f"  ToolCallItem: Called tool '{tool_name}' with args: {str(tool_args)[:200]}")
                elif wrapper_type_name == 'MessageOutputItem' and actual_item_content is not run_item_wrapper:
                    logger.info(f"  MessageOutputItem content: {str(actual_item_content)[:200]}")
        else:
            logger.warning("No 'new_items' attribute in agent_run_result, or it is empty.")
        
        response_data = {
            "ai_response_text": agent_run_result.final_output,
            "proposed_modifications": proposals_for_frontend,
            "scratchpad_updates": scratchpad_updates_for_frontend, 
            "updated_conversation_history": [] 
        }
        logger.info(f"ScriptCollaboratorAgent task completed for script_id: {script_id}. Proposals: {len(proposals_for_frontend)}, Scratchpad: {len(scratchpad_updates_for_frontend)}")
        return response_data

    except Exception as e:
        logger.error(f"Error in ScriptCollaboratorAgent task for script_id {script_id}: {e}", exc_info=True)
        raise 