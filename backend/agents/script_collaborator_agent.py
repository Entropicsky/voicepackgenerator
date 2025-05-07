from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid # For generating unique proposal IDs
from enum import Enum
from datetime import datetime # Ensure datetime is imported for Pydantic model

# Database session and models
from backend import models # To access VoScript, VoScriptLine etc.
from sqlalchemy.orm import Session 

# Helper to get DB session (assuming models.get_db() is appropriate)
# This mirrors the FastAPI dependency pattern for use in tools.
def get_db_session() -> Session:
    db = next(models.get_db()) # models.get_db() is a generator
    try:
        yield db
    finally:
        db.close()

# It's good practice to load the model name from an environment variable
# For MVP, we can default if not set, but production should have it set.
OPENAI_AGENT_MODEL = os.getenv("OPENAI_AGENT_MODEL", "gpt-4o")

# Initial Agent Instructions from the Tech Spec
AGENT_INSTRUCTIONS = ("""
    You are an expert scriptwriting assistant. You are collaborating with a game designer to refine voice-over scripts.
    Your goal is to help them improve script lines, brainstorm ideas, and ensure consistency.
    When asked to modify a line or suggest new content, use the 'propose_script_modification' tool.
    For general discussion or brainstorming that isn't a direct line edit, use your conversational abilities. You can use the 'add_to_scratchpad' tool to save interesting ideas.
    Always be helpful, concise, and focus on the user's active script context (e.g., a specific line or category they are working on).
""")

# --- Pydantic Models for Tools ---
class GetScriptContextParams(BaseModel):
    script_id: int
    category_id: Optional[int] = None
    line_id: Optional[int] = None
    include_surrounding_lines: Optional[int] = None # Made Optional, default will be handled in logic

class LineDetail(BaseModel):
    id: int
    line_key: Optional[str] = None
    text: Optional[str] = None
    order_index: Optional[int] = None
    # Add other relevant fields from VoScriptLine as needed for context

class ScriptContextResponse(BaseModel):
    script_id: int
    script_name: Optional[str] = None
    character_description: Optional[str] = None
    category_name: Optional[str] = None
    lines: Optional[List[LineDetail]] = None # For category/full script context
    target_line: Optional[LineDetail] = None # For specific line context
    surrounding_before: Optional[List[LineDetail]] = None
    surrounding_after: Optional[List[LineDetail]] = None
    error: Optional[str] = None

# --- Tool Definition ---
@function_tool
def get_script_context(params: GetScriptContextParams) -> ScriptContextResponse:
    """
    Fetches the content of the current script, a specific category, or a specific line.
    Can optionally include a few surrounding lines for better conversational context if a line_id is provided.
    """
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)
    
    # Handle default for include_surrounding_lines
    num_surrounding = params.include_surrounding_lines if params.include_surrounding_lines is not None else 3
    # Basic validation for the number, even if not in schema
    num_surrounding = max(0, min(num_surrounding, 10)) # Cap between 0 and 10

    response_data = {"script_id": params.script_id}
    
    try:
        script = db.query(models.VoScript).filter(models.VoScript.id == params.script_id).first()
        if not script:
            return ScriptContextResponse(script_id=params.script_id, error="Script not found.")
        
        response_data["script_name"] = script.name
        response_data["character_description"] = script.character_description

        query = db.query(models.VoScriptLine).filter(models.VoScriptLine.vo_script_id == params.script_id)

        if params.category_id:
            category = db.query(models.VoScriptTemplateCategory).filter(models.VoScriptTemplateCategory.id == params.category_id).first()
            if category:
                response_data["category_name"] = category.name
            # Important: Filter VoScriptLine by category_id. This assumes VoScriptLine.category_id links to VoScriptTemplateCategory.id
            # Need to confirm VoScriptLine.category_id is correctly populated and refers to the template category ID.
            # If VoScriptLine.category_id refers to something else, or if category context is derived differently (e.g. via template_line), this needs adjustment.
            query = query.filter(models.VoScriptLine.category_id == params.category_id) 
        
        if params.line_id:
            # If category_id was also provided, query is already filtered by category.
            target_line_db = query.filter(models.VoScriptLine.id == params.line_id).first()
            if not target_line_db:
                 return ScriptContextResponse(script_id=params.script_id, error=f"Line ID {params.line_id} not found in script or specified scope.")

            response_data["target_line"] = LineDetail(
                id=target_line_db.id, 
                line_key=target_line_db.line_key, 
                text=target_line_db.generated_text, 
                order_index=target_line_db.order_index
            )
            
            if num_surrounding > 0 and target_line_db.order_index is not None:
                # Base query for surrounding lines (within the same script, and same category if category_id is present)
                surrounding_query_base = db.query(models.VoScriptLine).filter(models.VoScriptLine.vo_script_id == params.script_id)
                if params.category_id:
                    surrounding_query_base = surrounding_query_base.filter(models.VoScriptLine.category_id == params.category_id)

                lines_before_db = surrounding_query_base.filter(models.VoScriptLine.order_index < target_line_db.order_index)\
                    .order_by(models.VoScriptLine.order_index.desc())\
                    .limit(num_surrounding).all() # Use num_surrounding
                response_data["surrounding_before"] = [
                    LineDetail(id=l.id, line_key=l.line_key, text=l.generated_text, order_index=l.order_index) 
                    for l in reversed(lines_before_db)
                ]

                lines_after_db = surrounding_query_base.filter(models.VoScriptLine.order_index > target_line_db.order_index)\
                    .order_by(models.VoScriptLine.order_index.asc())\
                    .limit(num_surrounding).all() # Use num_surrounding
                response_data["surrounding_after"] = [
                    LineDetail(id=l.id, line_key=l.line_key, text=l.generated_text, order_index=l.order_index) 
                    for l in lines_after_db
                ]
        else:
            # No specific line_id, fetch all lines for the script (and category if specified)
            all_lines_db = query.order_by(models.VoScriptLine.order_index, models.VoScriptLine.id).all()
            response_data["lines"] = [
                LineDetail(id=l.id, line_key=l.line_key, text=l.generated_text, order_index=l.order_index) 
                for l in all_lines_db
            ]
            
        return ScriptContextResponse(**response_data)

    except Exception as e:
        # TODO: Add proper logging here
        print(f"Error in get_script_context: {e}") # Temporary print
        import traceback
        traceback.print_exc() # Temporary print
        return ScriptContextResponse(script_id=params.script_id, error=f"Error fetching script context: {str(e)}")
    finally:
        # Ensure the generator is exhausted to close the session via the try/finally in get_db_session
        # This happens naturally if next(db_session_gen) was the only call, 
        # but if it were in a loop, it needs careful handling.
        # The way get_db_session is written, db.close() handles it.
        pass

# --- Pydantic Models for propose_script_modification Tool ---
class ModificationType(str, Enum):
    REPLACE_LINE = "REPLACE_LINE"
    INSERT_LINE_AFTER = "INSERT_LINE_AFTER"
    INSERT_LINE_BEFORE = "INSERT_LINE_BEFORE"
    NEW_LINE_IN_CATEGORY = "NEW_LINE_IN_CATEGORY"

class ProposeScriptModificationParams(BaseModel):
    script_id: int
    modification_type: ModificationType
    target_id: int 
    new_text: Optional[str] = None
    character_id: Optional[int] = None
    metadata_notes: Optional[str] = None
    reasoning: Optional[str] = None
    suggested_line_key: Optional[str] = None
    suggested_order_index: Optional[int] = None

class ProposedModificationDetail(BaseModel):
    proposal_id: str
    script_id: int
    modification_type: ModificationType
    target_id: int
    new_text: Optional[str] = None
    character_id: Optional[int] = None
    metadata_notes: Optional[str] = None
    reasoning: Optional[str] = None
    suggested_line_key: Optional[str] = None
    suggested_order_index: Optional[int] = None

class ProposedModificationResponse(BaseModel):
    proposal: Optional[ProposedModificationDetail] = None
    error: Optional[str] = None

# --- Tool Definition for propose_script_modification ---
@function_tool
def propose_script_modification(params: ProposeScriptModificationParams) -> ProposedModificationResponse:
    """
    Proposes a modification to a script line or category.
    This tool DOES NOT directly write to the database. It returns a structured proposal for the user to review and commit.
    'target_id' should be a line_id for REPLACE_LINE, INSERT_LINE_AFTER, INSERT_LINE_BEFORE.
    'target_id' should be a category_id for NEW_LINE_IN_CATEGORY.
    'new_text' is required for modifications that add or change text.
    """
    try:
        if params.modification_type in [ModificationType.REPLACE_LINE, ModificationType.NEW_LINE_IN_CATEGORY] and not params.new_text:
            return ProposedModificationResponse(error=f"New text is required for modification type {params.modification_type.value}.")
        if params.modification_type in [ModificationType.INSERT_LINE_AFTER, ModificationType.INSERT_LINE_BEFORE] and not params.new_text:
             return ProposedModificationResponse(error=f"New text is required for modification type {params.modification_type.value}.")

        proposal_id = str(uuid.uuid4())
        
        proposal_detail = ProposedModificationDetail(
            proposal_id=proposal_id,
            script_id=params.script_id,
            modification_type=params.modification_type,
            target_id=params.target_id,
            new_text=params.new_text,
            character_id=params.character_id,
            metadata_notes=params.metadata_notes,
            reasoning=params.reasoning,
            suggested_line_key=params.suggested_line_key,
            suggested_order_index=params.suggested_order_index
        )
        return ProposedModificationResponse(proposal=proposal_detail)

    except Exception as e:
        print(f"Error in propose_script_modification: {e}")
        import traceback
        traceback.print_exc()
        return ProposedModificationResponse(error=f"Error creating proposal: {str(e)}")

# --- Pydantic Models for get_line_details Tool ---
class GetLineDetailsParams(BaseModel):
    line_id: int

class VoScriptLineFullDetail(BaseModel):
    id: int
    vo_script_id: int
    template_line_id: Optional[int] = None
    category_id: Optional[int] = None
    line_key: Optional[str] = None
    order_index: Optional[int] = None
    prompt_hint: Optional[str] = None
    generated_text: Optional[str] = None
    status: Optional[str] = None
    # generation_history: Optional[Dict[str, Any]] = None # Omitting for MVP simplicity unless strictly needed by agent
    latest_feedback: Optional[str] = None
    is_locked: Optional[bool] = None
    created_at: Optional[datetime] = None 
    updated_at: Optional[datetime] = None

class GetLineDetailsResponse(BaseModel):
    line_details: Optional[VoScriptLineFullDetail] = None
    error: Optional[str] = None

# --- Tool Definition for get_line_details ---
@function_tool
def get_line_details(params: GetLineDetailsParams) -> GetLineDetailsResponse:
    """
    Fetches all details for a specific VO script line given its ID.
    """
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)

    try:
        line_db = db.query(models.VoScriptLine).filter(models.VoScriptLine.id == params.line_id).first()

        if not line_db:
            return GetLineDetailsResponse(error=f"VoScriptLine with ID {params.line_id} not found.")

        line_detail_data = {
            "id": line_db.id,
            "vo_script_id": line_db.vo_script_id,
            "template_line_id": line_db.template_line_id,
            "category_id": line_db.category_id,
            "line_key": line_db.line_key,
            "order_index": line_db.order_index,
            "prompt_hint": line_db.prompt_hint,
            "generated_text": line_db.generated_text,
            "status": line_db.status,
            "latest_feedback": line_db.latest_feedback,
            "is_locked": line_db.is_locked,
            "created_at": line_db.created_at,
            "updated_at": line_db.updated_at
        }
        
        line_details_obj = VoScriptLineFullDetail(**line_detail_data)
        return GetLineDetailsResponse(line_details=line_details_obj)

    except Exception as e:
        print(f"Error in get_line_details: {e}") 
        import traceback
        traceback.print_exc()
        return GetLineDetailsResponse(error=f"Error fetching line details: {str(e)}")
    finally:
        pass 

# --- Pydantic Models for add_to_scratchpad Tool ---
class AddToScratchpadParams(BaseModel):
    script_id: int
    text_to_save: str 
    related_entity_id: Optional[int] = None
    related_entity_type: Optional[str] = None # Should be "category" or "line"
    note_title: Optional[str] = None

class AddToScratchpadResponse(BaseModel):
    note_id: Optional[int] = None
    status: str # "success" or "error"
    message: Optional[str] = None

# --- Tool Definition for add_to_scratchpad ---
@function_tool
def add_to_scratchpad(params: AddToScratchpadParams) -> AddToScratchpadResponse:
    """
    Saves a text snippet, idea, or note to a scratchpad associated with the script.
    Can optionally be linked to a specific category ID or line ID using related_entity_id and related_entity_type (e.g., type 'category' or 'line').
    """
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)
    try:
        script = db.query(models.VoScript).filter(models.VoScript.id == params.script_id).first()
        if not script:
            return AddToScratchpadResponse(status="error", message=f"Script ID {params.script_id} not found.")

        category_id_to_save = None
        line_id_to_save = None

        if params.related_entity_id is not None and params.related_entity_type:
            entity_type = params.related_entity_type.lower()
            if entity_type == "category":
                category = db.query(models.VoScriptTemplateCategory).filter(models.VoScriptTemplateCategory.id == params.related_entity_id).first()
                if not category:
                    return AddToScratchpadResponse(status="error", message=f"Category ID {params.related_entity_id} not found.")
                category_id_to_save = params.related_entity_id
            elif entity_type == "line":
                line = db.query(models.VoScriptLine).filter(models.VoScriptLine.id == params.related_entity_id).first()
                if not line:
                    return AddToScratchpadResponse(status="error", message=f"Line ID {params.related_entity_id} not found.")
                if line.vo_script_id != params.script_id:
                    return AddToScratchpadResponse(status="error", message=f"Line ID {params.related_entity_id} does not belong to Script ID {params.script_id}.")
                line_id_to_save = params.related_entity_id
            else:
                return AddToScratchpadResponse(status="error", message=f"Invalid related_entity_type: '{params.related_entity_type}'. Must be 'category' or 'line'.")
        elif params.related_entity_id is not None and not params.related_entity_type:
            return AddToScratchpadResponse(status="error", message="related_entity_type is required if related_entity_id is provided.")
        elif params.related_entity_type is not None and params.related_entity_id is None:
            return AddToScratchpadResponse(status="error", message="related_entity_id is required if related_entity_type is provided.")

        new_note = models.ScriptNote(
            vo_script_id=params.script_id,
            text_content=params.text_to_save,
            title=params.note_title,
            category_id=category_id_to_save,
            line_id=line_id_to_save
        )
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        return AddToScratchpadResponse(note_id=new_note.id, status="success", message="Note saved successfully.")
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error in add_to_scratchpad tool: {e}", exc_info=True) # Use Flask logger
        return AddToScratchpadResponse(status="error", message=f"Error saving note: {str(e)}")
    finally:
        pass # DB session closed by get_db_session context manager

class ScriptCollaboratorAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            name="ScriptCollaboratorAgent",
            instructions=AGENT_INSTRUCTIONS,
            model=OPENAI_AGENT_MODEL,
            tools=[
                get_script_context, 
                propose_script_modification,
                get_line_details,
                add_to_scratchpad # Register the new tool
            ],
            **kwargs
        )

# Example of how to instantiate (for local testing, not for direct use by Celery task yet)
if __name__ == "__main__":
    # This section is for direct execution testing of this file
    # Ensure OPENAI_API_KEY is set in your environment for this to work
    print(f"Initializing ScriptCollaboratorAgent with model: {OPENAI_AGENT_MODEL}")
    try:
        agent = ScriptCollaboratorAgent() # Agent is initialized with get_script_context tool
        print("Agent initialized successfully.")
        
        # Test the get_script_context tool by having the agent use it
        print("\n--- Testing get_script_context tool via Agent Runner --- (Requires script ID 1 to exist)")
        # Craft a query that should encourage the agent to use the get_script_context tool.
        # The tool's description is: "Fetches the content of the current script, a specific category, or a specific line..."
        user_query_for_tool = "Can you fetch the context for script ID 1, specifically line ID 2, and include 1 surrounding line before and after?"
        # More direct: user_query_for_tool = "Use the get_script_context tool with script_id 1, line_id 2, and include_surrounding_lines 1"

        print(f"\nUser Query: {user_query_for_tool}")
        result_via_agent = Runner.run_sync(agent, user_query_for_tool)
        
        print(f"\nAgent Final Output:\n{result_via_agent.final_output}")
        
        print("\n--- Agent Run Steps (to inspect tool calls) ---")
        if hasattr(result_via_agent, 'steps') and result_via_agent.steps:
            for step_num, step in enumerate(result_via_agent.steps):
                print(f"\nStep {step_num + 1}: Type: {step.type}")
                if hasattr(step, 'item') and step.item:
                    print(f"  Item Name (if any): {getattr(step.item, 'name', 'N/A')}")
                    # Try to print raw_item if it exists and gives useful tool call/output info
                    if hasattr(step.item, 'raw_item'):
                        raw_item_details = step.item.raw_item
                        if isinstance(raw_item_details, dict) and 'name' in raw_item_details and 'arguments' in raw_item_details:
                            print(f"    Tool Call: {raw_item_details.get('name')}")
                            print(f"    Arguments: {raw_item_details.get('arguments')}")
                        elif isinstance(raw_item_details, dict) and 'call_id' in raw_item_details and 'output' in raw_item_details:
                            print(f"    Tool Output (for call_id {raw_item_details.get('call_id')}): {raw_item_details.get('output')}")
                        else:
                            print(f"    Raw Item Details: {raw_item_details}") # Fallback
                    else:
                        print(f"  Full Item Details: {step.item}")
                else:
                    print(f"  Step content: {step}")
        elif hasattr(result_via_agent, 'raw_responses') and result_via_agent.raw_responses:
            print("No 'steps' attribute. Showing raw_responses instead:")
            for i, resp in enumerate(result_via_agent.raw_responses):
                 if hasattr(resp, 'output'):
                    print(f"  Raw Response {i+1} Output: {resp.output}")
        else:
            print("No 'steps' or 'raw_responses' with output found in agent result. Full result object:")
            print(result_via_agent)

        print("\n--- Testing propose_script_modification tool via Agent Runner ---")
        query_propose_change = "For script 1, propose replacing line ID 2 with the text 'The alien ship is approaching fast!' and reason that it's more direct."
        print(f"\nUser Query: {query_propose_change}")
        result_proposal_agent = Runner.run_sync(agent, query_propose_change)
        print(f"\nAgent Final Output for proposal:\n{result_proposal_agent.final_output}")
        print("\n--- Agent Run Steps for proposal (to inspect tool calls) ---")
        if hasattr(result_proposal_agent, 'steps') and result_proposal_agent.steps:
            for step_num, step in enumerate(result_proposal_agent.steps):
                print(f"\nStep {step_num + 1}: Type: {step.type}")
                if hasattr(step, 'item') and step.item:
                    print(f"  Item Name (if any): {getattr(step.item, 'name', 'N/A')}")
                    if hasattr(step.item, 'raw_item'):
                        raw_item_details = step.item.raw_item
                        if isinstance(raw_item_details, dict) and 'name' in raw_item_details and 'arguments' in raw_item_details:
                            print(f"    Tool Call: {raw_item_details.get('name')}")
                            print(f"    Arguments: {raw_item_details.get('arguments')}")
                        elif isinstance(raw_item_details, dict) and 'call_id' in raw_item_details and 'output' in raw_item_details:
                            print(f"    Tool Output (for call_id {raw_item_details.get('call_id')}): {raw_item_details.get('output')}")
                        else:
                            print(f"    Raw Item Details: {raw_item_details}")
                    else:
                        print(f"  Full Item Details: {step.item}")
                else:
                    print(f"  Step content: {step}")
        elif hasattr(result_proposal_agent, 'raw_responses') and result_proposal_agent.raw_responses:
            print("No 'steps' attribute. Showing raw_responses instead for proposal:")
            for i, resp in enumerate(result_proposal_agent.raw_responses):
                 if hasattr(resp, 'output'):
                    print(f"  Raw Response {i+1} Output: {resp.output}")
        else:
            print("No 'steps' or 'raw_responses' with output found in proposal agent result. Full result object:")
            print(result_proposal_agent)

        # Test for get_line_details tool
        print("\n--- Testing get_line_details tool via Agent Runner ---")
        query_get_details = "Show me all details for line ID 2 in script 1."
        print(f"\nUser Query: {query_get_details}")
        result_line_details_agent = Runner.run_sync(agent, query_get_details)
        print(f"\nAgent Final Output for line details:\n{result_line_details_agent.final_output}")
        print("\n--- Agent Run Steps for line details (to inspect tool calls) ---")
        if hasattr(result_line_details_agent, 'steps') and result_line_details_agent.steps:
            for step_num, step in enumerate(result_line_details_agent.steps):
                print(f"\nStep {step_num + 1}: Type: {step.type}")
                if hasattr(step, 'item') and step.item:
                    print(f"  Item Name (if any): {getattr(step.item, 'name', 'N/A')}")
                    if hasattr(step.item, 'raw_item'):
                        raw_item_details = step.item.raw_item
                        if isinstance(raw_item_details, dict) and 'name' in raw_item_details and 'arguments' in raw_item_details:
                            print(f"    Tool Call: {raw_item_details.get('name')}")
                            print(f"    Arguments: {raw_item_details.get('arguments')}")
                        elif isinstance(raw_item_details, dict) and 'call_id' in raw_item_details and 'output' in raw_item_details:
                            print(f"    Tool Output (for call_id {raw_item_details.get('call_id')}): {raw_item_details.get('output')}")
                        else:
                            print(f"    Raw Item Details: {raw_item_details}")
                    else:
                        print(f"  Full Item Details: {step.item}")
                else:
                    print(f"  Step content: {step}")
        elif hasattr(result_line_details_agent, 'raw_responses') and result_line_details_agent.raw_responses:
            print("No 'steps' attribute. Showing raw_responses instead for line details:")
            for i, resp in enumerate(result_line_details_agent.raw_responses):
                 if hasattr(resp, 'output'):
                    print(f"  Raw Response {i+1} Output: {resp.output}")
        else:
            print("No 'steps' or 'raw_responses' with output found in line details agent result. Full result object:")
            print(result_line_details_agent)

        # Test for add_to_scratchpad tool
        print("\n--- Testing add_to_scratchpad tool via Agent Runner ---")
        # Test 1: General note for script 1
        query_add_general_note = "For script 1, please add a scratchpad note titled 'Overall Theme Ideas' with the content 'Explore themes of betrayal and redemption for the main character arc.'"
        print(f"\nUser Query (General Note): {query_add_general_note}")
        result_general_note = Runner.run_sync(agent, query_add_general_note)
        print(f"\nAgent Final Output (General Note):\n{result_general_note.final_output}")
        print("\n--- Agent Run Steps for General Note (to inspect tool calls) ---")
        if hasattr(result_general_note, 'steps') and result_general_note.steps:
            for step_num, step in enumerate(result_general_note.steps):
                print(f"\nStep {step_num + 1}: Type: {step.type}")
                if hasattr(step, 'item') and step.item and hasattr(step.item, 'raw_item'):
                    raw_item_details = step.item.raw_item
                    if isinstance(raw_item_details, dict) and 'name' in raw_item_details and 'arguments' in raw_item_details:
                        print(f"    Tool Call: {raw_item_details.get('name')}")
                        print(f"    Arguments: {raw_item_details.get('arguments')}")
                    elif isinstance(raw_item_details, dict) and 'call_id' in raw_item_details and 'output' in raw_item_details:
                        tool_output_str = str(raw_item_details.get('output'))
                        print(f"    Tool Output (for call_id {raw_item_details.get('call_id')}): {tool_output_str[:500]}...") # Truncate
        # Verify with psql: SELECT * FROM script_notes WHERE vo_script_id = 1 AND title = 'Overall Theme Ideas';

        # Test 2: Note linked to a specific line (e.g., line ID 2 in script ID 1)
        query_add_line_note = "For script ID 1, add a note to line ID 2 specifically, with the title 'Pacing Check' and text 'Remind self to check the pacing of this line during voice recording.'"
        print(f"\nUser Query (Line Note): {query_add_line_note}")
        result_line_note = Runner.run_sync(agent, query_add_line_note)
        print(f"\nAgent Final Output (Line Note):\n{result_line_note.final_output}")
        print("\n--- Agent Run Steps for Line Note (to inspect tool calls) ---")
        if hasattr(result_line_note, 'steps') and result_line_note.steps:
            for step_num, step in enumerate(result_line_note.steps):
                print(f"\nStep {step_num + 1}: Type: {step.type}")
                if hasattr(step, 'item') and step.item and hasattr(step.item, 'raw_item'):
                    raw_item_details = step.item.raw_item
                    if isinstance(raw_item_details, dict) and 'name' in raw_item_details and 'arguments' in raw_item_details:
                        print(f"    Tool Call: {raw_item_details.get('name')}")
                        print(f"    Arguments: {raw_item_details.get('arguments')}")
                    elif isinstance(raw_item_details, dict) and 'call_id' in raw_item_details and 'output' in raw_item_details:
                        tool_output_str = str(raw_item_details.get('output'))
                        print(f"    Tool Output (for call_id {raw_item_details.get('call_id')}): {tool_output_str[:500]}...") # Truncate
        # Verify with psql: SELECT * FROM script_notes WHERE vo_script_id = 1 AND line_id = 2;

    except Exception as e:
        print(f"Error during agent initialization or test run: {e}")
        import traceback
        traceback.print_exc()
        print("Please ensure OPENAI_API_KEY is set and DB has test data (e.g., VoScript ID 1 with lines).") 