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
from backend.agents.script_collaborator_agent import (
    ScriptCollaboratorAgent, 
    ProposedModificationResponse, 
    AddToScratchpadResponse, 
    GetLineDetailsResponse, 
    ScriptContextResponse,
    StageCharacterDescriptionToolResponse, # Import new response type
    StagedCharacterDescriptionData, # Import new data type
    ProposeMultipleModificationsResponse, # Import new response type
    UpdateCharacterDescriptionResponse, # Added UpdateCharacterDescriptionResponse
    ProposedModificationDetail, # Also need the detail model
)
from agents import Runner, ToolCallItem, ToolCallOutputItem, MessageOutputItem # Adjust imports as needed
from typing import List, Dict, Any, Optional
from sqlalchemy import desc # For ordering history

# Get a logger for this module/task
logger = get_task_logger(__name__)

print("Celery Worker: Loading script_tasks.py...")

# Resilience: Configure OpenAI client retries and timeout
# These can be overridden by environment variables
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_CHAT_MAX_RETRIES", 2)) 
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_CHAT_TIMEOUT_SECONDS", 30.0))

# --- Constants --- #
CHAT_HISTORY_LIMIT_FOR_AGENT = 20 # How many past messages to load from DB for agent context

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

@celery.task(bind=True, name='run_script_collaborator_chat')
def run_script_collaborator_chat_task(self, script_id: int, user_message: str, initial_prompt_context_from_prior_sessions: Optional[List[Dict]] = None, current_context: Optional[Dict] = None):
    """Celery task to run the AI script collaborator agent."""
    logger.info(f"Starting ScriptCollaboratorAgent task SID: {script_id}, TaskID: {self.request.id}, Msg: '{user_message[:50]}...'")
    logger.info(f"Context: CategoryID: {current_context.get('category_id') if current_context else 'N/A'}, LineID: {current_context.get('line_id') if current_context else 'N/A'}")
    
    # Initialize state
    ai_response_text = ""
    proposed_modifications_list = []
    scratchpad_updates_list = []
    staged_description_update_result: Optional[StagedCharacterDescriptionData] = None
    
    db: Optional[Session] = None
    try:
        # --- Instantiate Agent --- 
        logger.info(f"Task {self.request.id}: Instantiating ScriptCollaboratorAgent with default client settings.")
        agent = ScriptCollaboratorAgent()

        # --- Prepare Input History --- 
        db = next(models.get_db())
        # 1. Load actual history from DB
        history_records = db.query(models.ChatMessageHistory).filter(
            models.ChatMessageHistory.vo_script_id == script_id
        ).order_by(models.ChatMessageHistory.timestamp.asc()).all()
        
        db_history_messages = [
            {"role": record.role, "content": record.content} 
            for record in history_records
        ]
        logger.info(f"Loaded {len(db_history_messages)} messages from DB history for script {script_id}.")
        
        # 2. Construct the input list for the agent
        full_input_history = []
        # ** NEW: Prepend system message with current script ID **
        full_input_history.append({"role": "system", "content": f"Current context is for Script ID: {script_id}"})
        # Add historical messages
        full_input_history.extend(db_history_messages)
        # Add the latest user message
        full_input_history.append({"role": "user", "content": user_message})

        logger.info(f"Running Agent with {len(full_input_history)} total messages in input history.")
        # Update task state to PROGRESS
        self.update_state(state='PROGRESS', meta={'status_message': 'Agent processing request...'})

        # --- Run Agent --- 
        # agent_run_result = Runner.run_sync(agent, messages=full_input_history) # Old call
        agent_run_result = Runner.run_sync(agent, full_input_history) # Corrected call
        logger.info(f"Task {self.request.id}: Agent run finished. Final Output: {agent_run_result.final_output[:100]}...")
        
        # --- Save History --- 
        # Save the user message and the final AI response to the DB history
        try:
            user_msg_record = models.ChatMessageHistory(vo_script_id=script_id, role='user', content=user_message)
            ai_msg_record = models.ChatMessageHistory(vo_script_id=script_id, role='assistant', content=agent_run_result.final_output)
            db.add_all([user_msg_record, ai_msg_record])
            db.commit()
            logger.info(f"Task {self.request.id}: Saved user and assistant messages to history for script {script_id}.")
        except Exception as hist_err:
            logger.error(f"Task {self.request.id}: Failed to save chat history for script {script_id}: {hist_err}")
            db.rollback() # Rollback history save if it fails, but proceed with task result

        # --- Process Agent Result --- 
        ai_response_text = agent_run_result.final_output
        
        # Process tool calls and outputs
        if hasattr(agent_run_result, 'new_items') and agent_run_result.new_items:
            logger.info(f"Task {self.request.id}: Processing {len(agent_run_result.new_items)} new_items from agent run.")
            # Iterate through steps to find tool calls and their outputs
            for i, item_wrapper in enumerate(agent_run_result.new_items):
                logger.info(f"Task {self.request.id}: Item {i+1}: WrapperType='{item_wrapper.type}', ActualItemContentType='{type(item_wrapper.item).__name__}'")
                
                if isinstance(item_wrapper.item, ToolCallItem):
                    tool_name = getattr(item_wrapper.item, 'name', 'N/A') # Should be present in raw_item?
                    raw_args_str = getattr(item_wrapper.item, 'arguments', '{}') # Should be present in raw_item?
                    logger.info(f"Task {self.request.id}:   [ToolCallItem Details] Name: {tool_name}, Raw Arguments String: {raw_args_str}")
                    try:
                         # Ensure arguments are parsed safely if they are JSON string
                         # The SDK might already parse it based on the Pydantic model
                         # Let's assume item.arguments might already be a dict if parsed by SDK
                         parsed_args = getattr(item_wrapper.item, 'arguments', {})
                         if isinstance(parsed_args, str):
                              parsed_args = json.loads(parsed_args)
                         logger.info(f"Task {self.request.id}:     Parsed Arguments: {parsed_args}")
                    except Exception as parse_err:
                         logger.error(f"Task {self.request.id}:     Error parsing tool arguments: {parse_err}. Raw: {raw_args_str}")
                
                elif isinstance(item_wrapper.item, ToolCallOutputItem):
                    logger.info(f"Task {self.request.id}:   [ToolCallOutputItem Details]")
                    # The actual output is often nested, potentially already parsed Pydantic model or raw string/dict
                    tool_output = getattr(item_wrapper.item, 'output', None)
                    raw_item_info = getattr(item_wrapper.item, 'raw_item', {})
                    logger.info(f"Task {self.request.id}:     item.output (Pydantic if parsed): {tool_output} (Type: {type(tool_output).__name__})")
                    logger.info(f"Task {self.request.id}:     item.raw_item (from SDK): {raw_item_info} (Type: {type(raw_item_info).__name__})")

                    # Process based on known response types
                    if isinstance(tool_output, ProposedModificationResponse):
                        if tool_output.proposal:
                            logger.info(f"Task {self.request.id}:     >>> Added 1 proposal from SINGLE ProposedModificationResponse.")
                            proposed_modifications_list.append(tool_output.proposal)
                    elif isinstance(tool_output, ProposeMultipleModificationsResponse): # Handle BATCH response
                        if tool_output.proposals_staged:
                            logger.info(f"Task {self.request.id}:     >>> Added {len(tool_output.proposals_staged)} proposals from BATCH ProposeMultipleModificationsResponse.")
                            proposed_modifications_list.extend(tool_output.proposals_staged)
                    elif isinstance(tool_output, AddToScratchpadResponse):
                        if tool_output.status == 'success' and tool_output.note_id is not None:
                            scratchpad_updates_list.append({"note_id": tool_output.note_id, "message": tool_output.message})
                    elif isinstance(tool_output, StageCharacterDescriptionToolResponse): # Handle new staged description tool
                        if tool_output.staged_update:
                            logger.info(f"Task {self.request.id}:     >>> Staged character description update received.")
                            staged_description_update_result = tool_output.staged_update # Store it
                        if tool_output.error:
                             logger.warning(f"Task {self.request.id}:     Tool stage_character_description_update reported an error: {tool_output.error}")
                    # Add checks for other tool output types if needed (GetScriptContextResponse, GetLineDetailsResponse, etc.)
                    # These usually don't add directly to the final task result lists, but good to log/verify
                    elif isinstance(tool_output, (ScriptContextResponse, GetLineDetailsResponse, UpdateCharacterDescriptionResponse)):
                         pass # Expected tool outputs, no specific action needed for final result lists
                    else:
                         logger.warning(f"Task {self.request.id}:     ToolCallOutputItem.output was not a recognized Pydantic model or dict. Type: {type(tool_output).__name__}")

                elif isinstance(item_wrapper.item, MessageOutputItem):
                     # This is usually the final AI text message, already captured in agent_run_result.final_output
                    pass
                else:
                    logger.warning(f"Task {self.request.id}: Unhandled item type in new_items: {type(item_wrapper.item).__name__}")

        logger.info(f"Task {self.request.id}: Completed. Proposals: {len(proposed_modifications_list)}, StagedDesc: {staged_description_update_result is not None}")
        return {
            "ai_response_text": ai_response_text,
            "proposed_modifications": [p.model_dump() for p in proposed_modifications_list], # Serialize Pydantic models
            "scratchpad_updates": scratchpad_updates_list, # Already dicts
            "staged_description_update": staged_description_update_result.model_dump() if staged_description_update_result else None # Serialize if present
        }

    except Exception as e:
        logger.exception(f"Task {self.request.id}: Error running ScriptCollaboratorAgent task for script {script_id}: {e}")
        # Optionally save error to history?
        # Raise the exception so Celery marks the task as FAILURE
        raise
    finally:
        if db and db.is_active:
            db.close() 