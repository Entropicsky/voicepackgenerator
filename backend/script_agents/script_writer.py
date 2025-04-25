# backend/agents/script_writer.py
import os
import logging
from typing import List, Dict, Any

# Correct imports for Agents SDK
from agents import Agent, Runner, function_tool

# Local imports
from backend import models
from backend.models import get_db, SessionLocal
from backend.app import model_to_dict
from sqlalchemy.orm import joinedload, selectinload, Session

# --- Agent Tools --- #

@function_tool
def get_vo_script_details(vo_script_id: int) -> Dict[str, Any]:
    """Fetches details for a specific VO Script, including character description and full template info (template hints, categories, lines)."""
    logging.info(f"[Tool] Called get_vo_script_details for vo_script_id: {vo_script_id}")
    db: Session = None
    try:
        db = next(get_db())
        script = db.query(models.VoScript).options(
            # Eager load template, its categories, and its lines
            joinedload(models.VoScript.template).selectinload(models.VoScriptTemplate.categories),
            joinedload(models.VoScript.template).selectinload(models.VoScriptTemplate.template_lines)
        ).get(vo_script_id)
        
        if not script:
            logging.error(f"[Tool] VO Script {vo_script_id} not found.")
            return {"error": f"VO Script {vo_script_id} not found"}
        
        # Serialize data for the agent
        script_details = model_to_dict(script, ['id', 'name', 'character_description', 'status'])
        if script.template:
            script_details['template'] = model_to_dict(script.template, ['id', 'name', 'description', 'prompt_hint'])
            script_details['template']['categories'] = [
                model_to_dict(c, ['id', 'name', 'prompt_instructions'])
                for c in script.template.categories
            ]
            script_details['template']['template_lines'] = [
                model_to_dict(l, ['id', 'category_id', 'line_key', 'prompt_hint', 'order_index'])
                for l in script.template.template_lines
            ]
            
        logging.info(f"[Tool] Returning details for VO Script {vo_script_id}")
        return script_details
    except Exception as e:
        logging.exception(f"[Tool] Error in get_vo_script_details for {vo_script_id}: {e}")
        return {"error": f"Failed to get script details: {e}"}
    finally:
        if db and db.is_active: db.close()

@function_tool
def get_lines_for_processing(vo_script_id: int, statuses: List[str]) -> List[Dict[str, Any]]:
    """Fetches VO Script Lines matching the given statuses for a specific VO Script. Includes template line info (key, hints, category info) and latest feedback."""
    logging.info(f"[Tool] Called get_lines_for_processing for vo_script_id: {vo_script_id}, statuses: {statuses}")
    db: Session = None
    try:
        db = next(get_db())
        lines = db.query(models.VoScriptLine).options(
            # Eager load the template line definition and its category
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category)
        ).filter(
            models.VoScriptLine.vo_script_id == vo_script_id,
            models.VoScriptLine.status.in_(statuses)
        ).order_by(models.VoScriptLine.id).all() # Order consistently
        
        result_lines = []
        for line in lines:
            line_data = model_to_dict(line, ['id', 'generated_text', 'status', 'latest_feedback']) # Base line info
            if line.template_line:
                line_data['line_key'] = line.template_line.line_key
                line_data['order_index'] = line.template_line.order_index
                line_data['template_prompt_hint'] = line.template_line.prompt_hint
                if line.template_line.category:
                    line_data['category_name'] = line.template_line.category.name
                    line_data['category_prompt_instructions'] = line.template_line.category.prompt_instructions
            result_lines.append(line_data)
            
        # Order by template order index after fetching and merging data
        result_lines.sort(key=lambda l: l.get('order_index', float('inf')))
            
        logging.info(f"[Tool] Returning {len(result_lines)} lines for processing for VO Script {vo_script_id}")
        return result_lines
    except Exception as e:
        logging.exception(f"[Tool] Error in get_lines_for_processing for {vo_script_id}: {e}")
        return [] # Return empty list on error
    finally:
        if db and db.is_active: db.close()

@function_tool
def update_script_line(vo_script_line_id: int, generated_text: str, new_status: str) -> bool:
    """Updates the generated text and status for a specific VO Script Line."""
    logging.info(f"[Tool] Called update_script_line for vo_script_line_id: {vo_script_line_id}, status: {new_status}")
    db: Session = None
    try:
        db = next(get_db())
        line = db.query(models.VoScriptLine).get(vo_script_line_id)
        if not line:
            logging.error(f"[Tool] Line {vo_script_line_id} not found for update.")
            return False
        
        line.generated_text = generated_text
        line.status = new_status
        # Reset feedback only if the new status indicates processing/approval?
        # e.g., if new_status in ['draft', 'approved']:
        #     line.latest_feedback = None 
        db.commit()
        logging.info(f"[Tool] Successfully updated line {vo_script_line_id}")
        return True
    except Exception as e:
        if db: db.rollback()
        logging.exception(f"[Tool] Error updating line {vo_script_line_id}: {e}")
        return False
    finally:
        if db and db.is_active: db.close()

# --- Agent Definition --- #

class ScriptWriterAgent:
    def __init__(self):
        self.agent_model = os.getenv("OPENAI_AGENT_MODEL", "gpt-4o") # Default to gpt-4o
        self.instructions = ( # Combined instructions from tech spec
            "You are an expert creative writer specializing in voiceover scripts for video game characters. "
            "Your goal is to generate compelling, in-character lines based on a detailed character description and script structure templates. "
            "Carefully consider all provided context: the overall character description, the general template prompt hint, the specific category instructions, and any line-specific hints. "
            "When refining lines, pay close attention to the user's feedback and the previous version of the line to make targeted improvements. "
            "Ensure generated lines adhere to any specified constraints (e.g., length, originality, tone). "
            "Use the available tools to read script details and save your generated lines."
        )
        # Tools are now implemented with DB logic
        self.tools = [
            get_vo_script_details,
            get_lines_for_processing,
            update_script_line
        ]
        
        # Initialize the actual agent using the SDK's Agent class
        self.agent = Agent(
            name="ScriptWriterAgent",
            instructions=self.instructions,
            model=self.agent_model,
            tools=self.tools
        )
        logging.info(f"ScriptWriterAgent initialized successfully with model {self.agent_model}.")
             
    def run(self, initial_prompt: str):
        """Runs the agent with a given prompt."""
        logging.info(f"Running ScriptWriterAgent with model {self.agent_model}...")
        try:
            # Use the Runner from the SDK
            result = Runner.run_sync(self.agent, input=initial_prompt)
            # Corrected: Check final_output existence
            run_status = "completed" if hasattr(result, 'final_output') and result.final_output else "failed"
            logging.info(f"ScriptWriterAgent run finished with status: {run_status}")
            logging.info(f"Agent final output: {getattr(result, 'final_output', '{No output attribute}')}") 
            # Add placeholder status attribute for compatibility with task processing logic
            result.status = run_status 
            # TODO: Add processing for result.steps if needed for debugging/logging
            return result
        except Exception as e:
            logging.exception(f"Error running ScriptWriterAgent: {e}")
            # Return a dummy failure result
            class DummyErrorResult:
                 final_output = f"Agent run failed: {e}"
                 status = "failed"
            return DummyErrorResult()

# Example Usage (for testing purposes, can be removed later)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Testing Agent Initialization...")
    writer_agent = ScriptWriterAgent()
    # Example tool call (requires DB setup and existing data)
    # print("\nTesting get_vo_script_details tool...")
    # details = get_vo_script_details(vo_script_id=1) # Replace 1 with a valid ID
    # print(details)
    # print("\nTesting run...")
    # result = writer_agent.run(initial_prompt="Generate draft for script ID 1.")
    # print(f"Run Status: {result.status}")
    # print(f"Final Output: {result.final_output}") 