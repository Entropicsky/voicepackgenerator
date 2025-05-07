from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid # For generating unique proposal IDs
from enum import Enum
from datetime import datetime # Ensure datetime is imported for Pydantic model

# Database session and models
from backend import models # To access VoScript, VoScriptLine etc.
from sqlalchemy.orm import Session, joinedload

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
    You are an expert scriptwriting assistant, designed to be a highly capable and context-aware collaborator for game designers working on voice-over scripts. Your primary goal is to help them draft, refine, and brainstorm script content effectively.

    **Core Principles:**
    1.  **Be Context-Driven:** Before answering questions about script content (lines, categories, overall script) or proposing modifications, YOU MUST first use the available tools (`get_script_context`, `get_line_details`) to fetch the most current information from the database. Do not rely on prior turn memory for specific line text or script structure; always fetch fresh data if the query pertains to it.
    2.  **Informed Proposals:** When using the `propose_script_modification` tool, ensure your suggestions are based on the context you've actively fetched for the relevant script, category, or line.
    3.  **Proactive Information Gathering:** If a user's request is about a specific part of the script (e.g., "improve the intro," "make line X more sarcastic," "what's the theme of the 'Chapter 1' category?") and they haven't provided all necessary details, use your tools to get that information first. For example, if they mention a line key or category name, use that to query.
    4.  **Character Consistency:** The character description is vital. Always use `get_script_context` to understand the character when generating new lines or refining existing ones to ensure they are in character.
    5.  **Tool Usage:**
        *   Use `get_script_context` to fetch broader script details, category lines, or a line with its surroundings.
        *   Use `get_line_details` to get all attributes of a single, specific line if you have its ID.
        *   Use `propose_script_modification` to suggest concrete changes to lines or propose new lines. Remember to provide `suggested_line_key` and `suggested_order_index` when proposing new lines (e.g., for `NEW_LINE_IN_CATEGORY`, `INSERT_LINE_AFTER`, `INSERT_LINE_BEFORE`).
        *   Use `add_to_scratchpad` for saving general notes, ideas, or brainstorming that isn't a direct line edit.
    6.  **Interaction Style:** Be helpful, concise, and conversational. Ask clarifying questions if a request is ambiguous, but prefer to use your tools to find information first.

    Always aim to act like an intelligent assistant who can independently use the provided tools to gather necessary data to fulfill the user's request comprehensively.
""")

# --- Pydantic Models for Tools ---
class GetScriptContextParams(BaseModel):
    script_id: int
    category_id: Optional[int] = None
    line_id: Optional[int] = None
    include_surrounding_lines: Optional[int] = None

class LineDetail(BaseModel):
    id: int
    line_key: Optional[str] = None
    text: Optional[str] = None # VoScriptLine.generated_text
    order_index: Optional[int] = None
    vo_script_line_prompt_hint: Optional[str] = None # From VoScriptLine.prompt_hint
    template_line_prompt_hint: Optional[str] = None # From VoScriptLine.template_line.prompt_hint
    # Optionally, add category_id/name to each line if returning a flat list for the whole script
    category_id_for_line: Optional[int] = None 
    category_name_for_line: Optional[str] = None

class CategoryDetail(BaseModel):
    id: int
    name: str
    prompt_instructions: Optional[str] = None
    lines: List[LineDetail] # Lines within this category

class ScriptContextResponse(BaseModel):
    script_id: int
    script_name: Optional[str] = None
    character_description: Optional[str] = None
    template_global_hint: Optional[str] = None # From VoScript.template.prompt_hint
    
    # If a specific category is requested or relevant to a line:
    focused_category_details: Optional[CategoryDetail] = None 
    
    # If no specific category/line, or for overall context, list all lines (could be flat or grouped by unincluded category headers)
    all_script_lines: Optional[List[LineDetail]] = None 
    
    target_line: Optional[LineDetail] = None # Populated if line_id is given
    surrounding_before: Optional[List[LineDetail]] = None
    surrounding_after: Optional[List[LineDetail]] = None
    error: Optional[str] = None

# --- Tool Definition ---
@function_tool
def get_script_context(params: GetScriptContextParams) -> ScriptContextResponse:
    """
    Fetches context for a script. If category_id is given, focuses on that category.
    If line_id is given, focuses on that line and its surroundings within its category (if any).
    If only script_id is given, returns all lines and general script info.
    """
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)
    
    num_surrounding = params.include_surrounding_lines if params.include_surrounding_lines is not None else 3
    num_surrounding = max(0, min(num_surrounding, 10))

    response_kwargs = {"script_id": params.script_id}
    
    try:
        script = db.query(models.VoScript).options(joinedload(models.VoScript.template)).filter(models.VoScript.id == params.script_id).first()
        if not script:
            return ScriptContextResponse(script_id=params.script_id, error="Script not found.")
        
        response_kwargs["script_name"] = script.name
        response_kwargs["character_description"] = script.character_description
        if script.template:
            response_kwargs["template_global_hint"] = script.template.prompt_hint

        # Determine base query for lines
        lines_query = db.query(models.VoScriptLine).options(
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category)
        ).filter(models.VoScriptLine.vo_script_id == params.script_id)

        category_template_for_line_detail = None

        if params.category_id:
            category_template = db.query(models.VoScriptTemplateCategory).filter(models.VoScriptTemplateCategory.id == params.category_id).first()
            if not category_template or (script.template_id and category_template.template_id != script.template_id):
                return ScriptContextResponse(script_id=params.script_id, error=f"Category ID {params.category_id} not found or not part of script's template.")
            
            lines_in_category_db = lines_query.filter(models.VoScriptLine.category_id == params.category_id).order_by(models.VoScriptLine.order_index, models.VoScriptLine.id).all()
            line_details_for_category = [
                LineDetail(
                    id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None),
                    text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None),
                    vo_script_line_prompt_hint=l.prompt_hint,
                    template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None,
                    category_id_for_line=l.category_id,
                    category_name_for_line=category_template.name
                ) for l in lines_in_category_db
            ]
            response_kwargs["focused_category_details"] = CategoryDetail(
                id=category_template.id, name=category_template.name,
                prompt_instructions=category_template.prompt_instructions,
                lines=line_details_for_category
            )
            category_template_for_line_detail = category_template # For use if line_id is also specified
        
        if params.line_id:
            # If category_id was provided, lines_query is already filtered. Otherwise, it's all lines for the script.
            if params.category_id:
                 target_line_db_query = lines_query.filter(models.VoScriptLine.category_id == params.category_id, models.VoScriptLine.id == params.line_id)
            else: # Search line in any category if category_id is not specified
                 target_line_db_query = lines_query.filter(models.VoScriptLine.id == params.line_id)
            
            target_line_db = target_line_db_query.first()

            if not target_line_db:
                 return ScriptContextResponse(script_id=params.script_id, error=f"Line ID {params.line_id} not found within the specified scope.")

            # Determine category context for this specific line if not already set by category_id param
            current_line_category_template = category_template_for_line_detail
            if not current_line_category_template and target_line_db.category_id:
                 current_line_category_template = db.query(models.VoScriptTemplateCategory).filter(models.VoScriptTemplateCategory.id == target_line_db.category_id).first()
            
            response_kwargs["target_line"] = LineDetail(
                id=target_line_db.id, line_key=target_line_db.line_key or (target_line_db.template_line.line_key if target_line_db.template_line else None),
                text=target_line_db.generated_text, order_index=target_line_db.order_index or (target_line_db.template_line.order_index if target_line_db.template_line else None),
                vo_script_line_prompt_hint=target_line_db.prompt_hint,
                template_line_prompt_hint=target_line_db.template_line.prompt_hint if target_line_db.template_line else None,
                category_id_for_line=target_line_db.category_id,
                category_name_for_line=current_line_category_template.name if current_line_category_template else None
            )
            
            # If focused_category_details wasn't set by category_id param, set it now based on target_line's category
            if not response_kwargs.get("focused_category_details") and current_line_category_template:
                # We need all lines from this category to populate focused_category_details.lines correctly
                # This might be redundant if category_id was already processed, but good for line_id only case.
                lines_in_target_category_db = db.query(models.VoScriptLine).options(joinedload(models.VoScriptLine.template_line)).filter(
                    models.VoScriptLine.vo_script_id == params.script_id,
                    models.VoScriptLine.category_id == current_line_category_template.id
                ).order_by(models.VoScriptLine.order_index, models.VoScriptLine.id).all()
                
                line_details_for_target_cat = [
                    LineDetail(
                        id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None),
                        text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None),
                        vo_script_line_prompt_hint=l.prompt_hint,
                        template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None,
                        category_id_for_line=l.category_id,
                        category_name_for_line=current_line_category_template.name
                    ) for l in lines_in_target_category_db
                ]
                response_kwargs["focused_category_details"] = CategoryDetail(
                    id=current_line_category_template.id, name=current_line_category_template.name,
                    prompt_instructions=current_line_category_template.prompt_instructions,
                    lines=line_details_for_target_cat
                )

            if num_surrounding > 0 and target_line_db.order_index is not None:
                surrounding_query_base = db.query(models.VoScriptLine).options(joinedload(models.VoScriptLine.template_line)).filter(models.VoScriptLine.vo_script_id == params.script_id)
                # Filter by category if target line has one for surrounding lines
                if target_line_db.category_id:
                    surrounding_query_base = surrounding_query_base.filter(models.VoScriptLine.category_id == target_line_db.category_id)

                lines_before_db = surrounding_query_base.filter(models.VoScriptLine.order_index < target_line_db.order_index).order_by(models.VoScriptLine.order_index.desc()).limit(num_surrounding).all()
                response_kwargs["surrounding_before"] = [LineDetail(id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None), text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None), vo_script_line_prompt_hint=l.prompt_hint, template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None, category_id_for_line=l.category_id, category_name_for_line=current_line_category_template.name if current_line_category_template else None) for l in reversed(lines_before_db)]
                lines_after_db = surrounding_query_base.filter(models.VoScriptLine.order_index > target_line_db.order_index).order_by(models.VoScriptLine.order_index.asc()).limit(num_surrounding).all()
                response_kwargs["surrounding_after"] = [LineDetail(id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None), text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None), vo_script_line_prompt_hint=l.prompt_hint, template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None, category_id_for_line=l.category_id, category_name_for_line=current_line_category_template.name if current_line_category_template else None) for l in lines_after_db]
        
        elif not params.category_id: # Only script_id given, fetch all lines (flat list for now)
            all_lines_db = lines_query.order_by(models.VoScriptLine.category_id, models.VoScriptLine.order_index, models.VoScriptLine.id).all()
            # To get category name for each line, we might need a more complex query or iterate and fetch
            # For simplicity in this pass, category_name_for_line might be None if not easily available
            # TODO: Enhance this to efficiently fetch category names for all_script_lines
            response_kwargs["all_script_lines"] = [
                LineDetail(
                    id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None),
                    text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None),
                    vo_script_line_prompt_hint=l.prompt_hint,
                    template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None,
                    category_id_for_line=l.category_id,
                    category_name_for_line=l.template_line.category.name if (l.template_line and l.template_line.category) else None # Example
                ) for l in all_lines_db
            ]
            
        return ScriptContextResponse(**response_kwargs)
    except Exception as e:
        print(f"Error in get_script_context: {e}") 
        import traceback
        traceback.print_exc()
        return ScriptContextResponse(script_id=params.script_id, error=f"Error fetching script context: {str(e)}")
    finally:
        if db.is_active: db.close() # Close session from generator

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
    category_name: Optional[str] = None 
    category_prompt_instructions: Optional[str] = None
    line_key: Optional[str] = None
    order_index: Optional[int] = None
    prompt_hint: Optional[str] = None # This is VoScriptLine.prompt_hint (direct on the line)
    template_line_prompt_hint: Optional[str] = None # From VoScriptLine.template_line.prompt_hint
    generated_text: Optional[str] = None
    status: Optional[str] = None
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
    Fetches all details for a specific VO script line given its ID,
    including related template and category context.
    """
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)

    try:
        line_db = db.query(models.VoScriptLine).options(
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category) # Eager load template line and its category
        ).filter(models.VoScriptLine.id == params.line_id).first()

        if not line_db:
            return GetLineDetailsResponse(error=f"VoScriptLine with ID {params.line_id} not found.")

        category_name_val = None
        category_instructions_val = None
        template_line_hint_val = None

        if line_db.template_line:
            template_line_hint_val = line_db.template_line.prompt_hint
            if line_db.template_line.category:
                category_name_val = line_db.template_line.category.name
                category_instructions_val = line_db.template_line.category.prompt_instructions
        elif line_db.category_id: # If it's a custom line with a direct category_id
            category_db = db.query(models.VoScriptTemplateCategory).filter(models.VoScriptTemplateCategory.id == line_db.category_id).first()
            if category_db:
                category_name_val = category_db.name
                category_instructions_val = category_db.prompt_instructions

        line_detail_data = {
            "id": line_db.id,
            "vo_script_id": line_db.vo_script_id,
            "template_line_id": line_db.template_line_id,
            "category_id": line_db.category_id,
            "category_name": category_name_val,
            "category_prompt_instructions": category_instructions_val,
            "line_key": line_db.line_key,
            "order_index": line_db.order_index,
            "prompt_hint": line_db.prompt_hint, # This is VoScriptLine.prompt_hint
            "template_line_prompt_hint": template_line_hint_val,
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
        if db.is_active: db.close()

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
                add_to_scratchpad
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