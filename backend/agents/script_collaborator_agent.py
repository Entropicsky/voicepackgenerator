from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid # For generating unique proposal IDs
from enum import Enum
from datetime import datetime # Ensure datetime is imported for Pydantic model
import json # For logging Pydantic model
import logging # Import standard logging

# Setup logger for this module
logger = logging.getLogger(__name__)
# You might want to configure its level if it's not inheriting from a root logger already set up in Flask
# For example, if Flask's root logger is set to INFO, this will also be INFO.
# If not, you might need: logger.setLevel(logging.INFO) or get it from Flask app config.

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
    **CONTEXT AWARENESS IS YOUR HIGHEST PRIORITY.**
    1.  **Identify the Script ID:** Look for a system message at the start of the conversation history like 'Current context is for Script ID: <ID>'. YOU MUST use this specific <ID> whenever you call a tool that requires a `script_id` parameter.
    2.  **Verify Context:** Before answering questions about script content or proposing modifications, YOU MUST use `get_script_context` (with the correct script ID) to fetch the most current script information, including character description, and a list of `available_categories` (each with `id`, `name`, `prompt_instructions`).
    3.  **Category-Specific Requests & Clarification:** If the user refers to a specific category by name (e.g., "add JOKE lines", "improve INTRO lines") OR if their request implies a category but doesn't explicitly state one (e.g., "add some taunts"): 
        a.  First, try to identify the target category. Use the `name` from the user's request (if provided) to find the corresponding category `id` from the `available_categories` list (fetched in step 2). 
        b.  **If the mentioned category name is ambiguous, not found in `available_categories`, or if no category is mentioned but seems implied, YOU MUST ask the user for clarification before proceeding with modifications.** For example, ask "Which category would you like to add those to? The available categories are: [list names from `available_categories`]." Do not assume or default to the first category.
        c.  Once a clear category target is established (either directly mentioned and found, or clarified by the user), if you need more details about that specific category (like its existing lines or specific prompt instructions), you can call `get_script_context` again, this time providing both the `script_id` AND the identified `category_id`.
        d.  When proposing new lines for this category using `propose_multiple_line_modifications`, ensure the `target_id` in your proposal is this identified `category_id`.
    4.  **Image Analysis Input:** If the user's message is prepended with "System Information: An image was uploaded...", this description is the result of an image analysis. You should:
        a.  Acknowledge this information.
        b.  Offer to help integrate relevant details into the *existing* character description (fetched via `get_script_context` with the correct script ID).
        c.  Formulate a new, combined character description.
        d.  Use `stage_character_description_update` to propose this new description.
    5.  **Ask Clarifying Questions:** If a user's request is vague, ambiguous, or could benefit from more detail for you to provide the best possible assistance (e.g., regarding tone, style, specific focus, or if a category is unclear), DO NOT HESITATE TO ASK FOLLOW-UP QUESTIONS before proceeding with tool use or generating content. This helps ensure your proposals and responses are well-aligned with their needs.

    You are an expert scriptwriting assistant, designed to be a highly capable and context-aware collaborator for game designers working on voice-over scripts. Your primary goal is to help them draft, refine, and brainstorm script content effectively, always using the correct script ID from the context.

    **Core Principles (Continued):**
    6.  **Informed Proposals:** When using `propose_script_modification` (for lines) or when suggesting a character description change, ensure your suggestions are based on the context you've actively fetched using the correct script ID.
    7.  **Proactive Information Gathering:** If a user's request is about a specific part of the script or character, use your tools (with the correct script ID) to get that information first.
    8.  **Character Consistency & Evolution:** The character description is vital. 
        *   Always use `get_script_context` (with the correct script ID) to understand the current character description when generating new lines or refining existing ones.
        *   If the user wishes to update the character description, or if through collaboration you arrive at a refined description (including after an image analysis), YOU SHOULD PREFER to use the `stage_character_description_update` tool. This allows the user to review your proposed description before it's saved.
        *   Only use the `update_character_description` tool for direct updates if the user explicitly bypasses the staging/review step or if they are confirming a previously staged update that you are now re-confirming for some reason (though this latter case should be rare).
    9.  **Tool Usage & Change Workflow:**
        *   `get_script_context`: Fetches script details, including `available_categories`. Args: `script_id`, optional `category_id`, `line_id`.
        *   `get_line_details`: Fetches details for a single line. Args: `line_id`.
        *   `propose_multiple_line_modifications`: For multiple lines. Args: `script_id`, `proposals` list. For `NEW_LINE_IN_CATEGORY`, `target_id` MUST be the **category ID**.
        *   `propose_script_modification`: For single line. Args: `script_id`, etc. For `NEW_LINE_IN_CATEGORY`, `target_id` MUST be the **category ID**.
        
        **Proposing Line Changes/Additions:**
        *   **Trigger:** User asks to change/add lines, possibly mentioning a category name.
        *   **Action:** 
            1. Use `get_script_context` (with script ID) to get `available_categories` and current lines/character description.
            2. If a category name is mentioned by the user, find its `id` from `available_categories`. If not found, ask for clarification or list available categories.
            3. If adding to a specific category, use its `id` as `target_id` for `NEW_LINE_IN_CATEGORY` proposals.
            4. Formulate `new_text`, `suggested_line_key`, `suggested_order_index`.
            5. Use `propose_multiple_line_modifications`.
            6. DO NOT ask for confirmation.
            
        *   `add_to_scratchpad`: Saves **freeform text notes, ideas, or brainstorming snippets** related to the script, lines, or categories. This does NOT change the official script content itself. Arguments MUST be in a `params` object, e.g., `{"params": {"script_id": <script_id>, "text_to_save": "My note", "related_entity_type": "line", "related_entity_id": <line_id>}}`.
        *   `stage_character_description_update`: Use this ONLY when proposing a change to the **official character description** field of the script, for user review and commitment. Arguments MUST be in a `params` object.
        *   `update_character_description`: Directly updates the official character description in the database. Arguments MUST be in a `params` object. Use this cautiously.
        *   **Important Distinction:** Do not use `stage_character_description_update` or `update_character_description` to save general character ideas or notes; use `add_to_scratchpad` for that purpose.
    10. **Interaction Style:**
        *   When you formulate a new character description, use `stage_character_description_update` to present it for user review.
        *   When the user requests line changes or additions, formulate them and **IMMEDIATELY use the appropriate proposal tool (`propose_multiple_line_modifications` or `propose_script_modification`) for all changes/additions.**
        *   If the user asks you to save a note or idea, use the `add_to_scratchpad` tool.

    **VERY IMPORTANT:** When calling *any* tool that requires a `script_id` or `category_id`, **always** use the correct ID derived from the conversation context or the `available_categories` list. Do not assume default IDs.

    Always aim to act like an intelligent assistant who can independently use the provided tools to gather necessary data and submit concrete, actionable changes for the user's review to fulfill their request comprehensively.
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
    available_categories: Optional[List[Dict[str, Any]]] = None # NEW: To list all category names and IDs
    
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
    # --- ADDED: Log received parameters --- 
    logger.info(f"[get_script_context] TOOL CALLED. Received params: {params}")
    # --- END ADDED --- 
    
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)
    
    num_surrounding = params.include_surrounding_lines if params.include_surrounding_lines is not None else 3
    num_surrounding = max(0, min(num_surrounding, 10))

    response_kwargs = {"script_id": params.script_id, "error": None, "available_categories": []} # Initialize new field
    final_response_obj = None
    try:
        script = db.query(models.VoScript).options(joinedload(models.VoScript.template)).filter(models.VoScript.id == params.script_id).first()
        if not script:
            return ScriptContextResponse(script_id=params.script_id, error="Script not found.")
        
        response_kwargs["script_name"] = script.name
        response_kwargs["character_description"] = script.character_description
        if script.template:
            response_kwargs["template_global_hint"] = script.template.prompt_hint

        # Populate available_categories if no specific category/line is focused
        if not params.category_id and not params.line_id and script.template_id:
            # Fetch all categories associated with the script's template
            categories_db = db.query(models.VoScriptTemplateCategory).filter(
                models.VoScriptTemplateCategory.template_id == script.template_id,
                models.VoScriptTemplateCategory.is_deleted == False # Assuming you only want active categories
            ).order_by(models.VoScriptTemplateCategory.name).all()
            
            if categories_db:
                response_kwargs["available_categories"] = [
                    {"id": cat.id, "name": cat.name, "prompt_instructions": cat.prompt_instructions} 
                    for cat in categories_db
                ]
            logger.info(f"[get_script_context] Populated available_categories with {len(response_kwargs['available_categories'])} items for script {params.script_id}")

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
            # Ensure category names are efficiently fetched for all_script_lines
            # This part might be simplified if available_categories is primary source for category listing
            # We can pre-fetch all category names for the script's template
            category_names_map = {cat["id"]: cat["name"] for cat in response_kwargs.get("available_categories", [])}

            response_kwargs["all_script_lines"] = [
                LineDetail(
                    id=l.id, line_key=l.line_key or (l.template_line.line_key if l.template_line else None),
                    text=l.generated_text, order_index=l.order_index or (l.template_line.order_index if l.template_line else None),
                    vo_script_line_prompt_hint=l.prompt_hint,
                    template_line_prompt_hint=l.template_line.prompt_hint if l.template_line else None,
                    category_id_for_line=l.category_id,
                    category_name_for_line=category_names_map.get(l.category_id) if l.category_id else (l.template_line.category.name if (l.template_line and l.template_line.category) else None)
                ) for l in all_lines_db
            ]
            # If available_categories is empty but all_lines_db has lines with category_ids, populate available_categories from all_lines_db unique categories
            if not response_kwargs.get("available_categories") and all_lines_db:
                unique_cats = {}
                for l_detail in response_kwargs["all_script_lines"]:
                    if l_detail.category_id_for_line and l_detail.category_name_for_line:
                        unique_cats[l_detail.category_id_for_line] = l_detail.category_name_for_line
                if unique_cats:
                    response_kwargs["available_categories"] = [{"id": cat_id, "name": cat_name} for cat_id, cat_name in unique_cats.items()]
                    logger.info(f"[get_script_context] Populated available_categories from distinct line categories, found {len(response_kwargs['available_categories'])}.")

        # --- Add detailed logging before returning --- 
        logger.info(f"[get_script_context] Raw response_kwargs before creating ScriptContextResponse: {response_kwargs}")
        final_response_obj = ScriptContextResponse(**response_kwargs)
        try:
            logger.info(f"[get_script_context] Attempting to return ScriptContextResponse (JSON): {final_response_obj.model_dump_json(indent=2)}")
        except Exception as serialization_exc:
            logger.error(f"[get_script_context] Error serializing ScriptContextResponse for logging: {serialization_exc}")
            logger.info(f"[get_script_context] Returning ScriptContextResponse (object form): {final_response_obj}")
        return final_response_obj
    except Exception as e:
        logger.error(f"[get_script_context] Unhandled error: {e}", exc_info=True)
        # Construct a clear error response if one wasn't already formed
        error_response = ScriptContextResponse(
            script_id=params.script_id, 
            error=f"Unhandled error in get_script_context: {str(e)}"
        )
        try:
            logger.info(f"[get_script_context] Attempting to return ERROR ScriptContextResponse (JSON): {error_response.model_dump_json(indent=2)}")
        except Exception as serialization_exc_err:
            logger.error(f"[get_script_context] Error serializing ERROR ScriptContextResponse for logging: {serialization_exc_err}")
            logger.info(f"[get_script_context] Returning ERROR ScriptContextResponse (object form): {error_response}")
        return error_response
    finally:
        if db.is_active: db.close() # Close session from generator

# --- Pydantic Models for propose_script_modification Tool (Single - To be Deprecated/Refocused) ---
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

# --- Tool Definition for propose_script_modification (Single) ---
@function_tool
def propose_script_modification(params: ProposeScriptModificationParams) -> ProposedModificationResponse:
    """
    (Less Preferred) Proposes a modification for **only one** script line. Use propose_multiple_line_modifications for multiple lines.
    Returns a structured proposal for user review. Does not write to the database.
    Arguments MUST be in a `params` object.
    """
    # ... (existing implementation for single proposal) ...
    try:
        # Add logger info
        logger.info(f"Processing SINGLE proposal via propose_script_modification. Type: {params.modification_type}, Target: {params.target_id}")
        if params.modification_type in [ModificationType.REPLACE_LINE, ModificationType.NEW_LINE_IN_CATEGORY, ModificationType.INSERT_LINE_AFTER, ModificationType.INSERT_LINE_BEFORE] and not params.new_text:
            return ProposedModificationResponse(error=f"New text is required for modification type {params.modification_type.value}. Use propose_multiple_line_modifications for batch proposals.")

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
        logger.error(f"Error in single propose_script_modification: {e}", exc_info=True)
        return ProposedModificationResponse(error=f"Error creating single proposal: {str(e)}")

# --- Pydantic Models for BATCH propose_multiple_line_modifications Tool --- #
class LineModificationProposalInput(BaseModel):
    # Fields needed for a single proposal, EXCLUDING script_id (passed once)
    modification_type: ModificationType
    target_id: int 
    new_text: Optional[str] = None
    reasoning: Optional[str] = None
    suggested_line_key: Optional[str] = None
    suggested_order_index: Optional[int] = None
    # character_id, metadata_notes could be added if needed per-line

class ProposeMultipleModificationsParams(BaseModel):
    script_id: int = Field(..., description="The ID of the VO Script these proposals belong to.")
    proposals: List[LineModificationProposalInput] = Field(..., description="A list of line modification proposals.")

class ProposeMultipleModificationsResponse(BaseModel):
    proposals_staged: List[ProposedModificationDetail] = [] # Returns full details needed by frontend
    success_count: int = 0
    failed_count: int = 0
    message: str # e.g., "Staged 3 proposals for review (1 failed validation)."
    error: Optional[str] = None # For total tool failure

# --- Tool Definition for BATCH propose_multiple_line_modifications --- #
@function_tool
def propose_multiple_line_modifications(params: ProposeMultipleModificationsParams) -> ProposeMultipleModificationsResponse:
    """ (Preferred) Stages multiple script line modification proposals for user review in a single batch. Does not write to the database. Arguments MUST be in a `params` object. """
    logger.info(f"Processing BATCH proposal via propose_multiple_line_modifications for script {params.script_id}. Count: {len(params.proposals)}")
    
    staged_proposals = []
    success_count = 0
    failed_count = 0
    failure_reasons = []

    for i, proposal_input in enumerate(params.proposals):
        try:
            # Validation (Example: check for new_text if required)
            if proposal_input.modification_type in [ModificationType.REPLACE_LINE, ModificationType.NEW_LINE_IN_CATEGORY, ModificationType.INSERT_LINE_AFTER, ModificationType.INSERT_LINE_BEFORE] and not proposal_input.new_text:
                raise ValueError(f"New text is required for modification type {proposal_input.modification_type.value}")

            # Generate proposal ID and create the full detail object
            proposal_id = str(uuid.uuid4())
            proposal_detail = ProposedModificationDetail(
                proposal_id=proposal_id,
                script_id=params.script_id, # Add script_id back in
                modification_type=proposal_input.modification_type,
                target_id=proposal_input.target_id,
                new_text=proposal_input.new_text,
                reasoning=proposal_input.reasoning,
                suggested_line_key=proposal_input.suggested_line_key,
                suggested_order_index=proposal_input.suggested_order_index,
                # Set others to None if not included in input model
                character_id=None, 
                metadata_notes=None 
            )
            staged_proposals.append(proposal_detail)
            success_count += 1
        except Exception as e:
            failed_count += 1
            fail_msg = f"Proposal {i+1} (TargetID: {proposal_input.target_id}, Type: {proposal_input.modification_type}) failed validation: {str(e)}"
            logger.warning(f"[Batch Proposal] {fail_msg}")
            failure_reasons.append(fail_msg)

    final_message = f"Staged {success_count} proposals for review."
    if failed_count > 0:
        final_message += f" ({failed_count} failed validation: {'; '.join(failure_reasons[:2])}...)."
        
    return ProposeMultipleModificationsResponse(
        proposals_staged=staged_proposals,
        success_count=success_count,
        failed_count=failed_count,
        message=final_message
    )

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

# --- Pydantic Models for update_character_description Tool (Direct Update - may be deprecated/refactored later) ---
class UpdateCharacterDescriptionParams(BaseModel):
    script_id: int = Field(..., description="The ID of the VO Script whose character description should be updated.")
    new_description: str = Field(..., description="The new character description text.")
    reasoning: Optional[str] = Field(None, description="Optional reason why the description is being updated.")

class UpdateCharacterDescriptionResponse(BaseModel):
    success: bool
    message: str
    updated_description: Optional[str] = None

# --- Tool Definition for update_character_description (Direct Update) ---
@function_tool
def update_character_description(params: UpdateCharacterDescriptionParams) -> UpdateCharacterDescriptionResponse:
    db_session_gen = get_db_session()
    db: Session = next(db_session_gen)
    try:
        script = db.query(models.VoScript).filter(models.VoScript.id == params.script_id).first()
        if not script:
            return UpdateCharacterDescriptionResponse(success=False, message=f"Script ID {params.script_id} not found.")

        script.character_description = params.new_description
        db.commit()
        db.refresh(script)
        logger.info(f"Character description for script {params.script_id} updated directly. Reasoning: {params.reasoning}")
        return UpdateCharacterDescriptionResponse(
            success=True, 
            message="Character description updated successfully (direct update).",
            updated_description=script.character_description
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error in direct update_character_description for script {params.script_id}: {e}", exc_info=True)
        return UpdateCharacterDescriptionResponse(success=False, message=f"Failed to directly update character description: {str(e)}")
    finally:
        if db.is_active: db.close()

# --- Pydantic Models for STAGING Character Description Update Tool ---
class StageCharacterDescriptionParams(BaseModel):
    script_id: int = Field(..., description="The ID of the VO Script for which the description update is being staged.")
    new_description: str = Field(..., description="The proposed new character description text.")
    reasoning: Optional[str] = Field(None, description="The agent's reasoning for proposing this change.")

class StagedCharacterDescriptionData(BaseModel):
    script_id: int # Keep script_id for context if needed by frontend
    new_description: str
    reasoning: Optional[str] = None

class StageCharacterDescriptionToolResponse(BaseModel):
    staged_update: Optional[StagedCharacterDescriptionData] = None
    message: str # e.g., "Character description staged for review."
    error: Optional[str] = None

# --- Tool Definition for STAGING Character Description Update ---
@function_tool
def stage_character_description_update(params: StageCharacterDescriptionParams) -> StageCharacterDescriptionToolResponse:
    """Stages a proposed update to a character description for user review. Does not write to the database directly."""
    logger.info(f"Staging character description update for script ID: {params.script_id}. Reasoning: {params.reasoning}")
    # Basic validation (further validation could be added if needed)
    if not params.new_description or len(params.new_description) < 5: # Arbitrary min length
        return StageCharacterDescriptionToolResponse(
            error="New description is too short or empty.",
            message="Failed to stage character description: Text too short."
        )
    
    staged_data = StagedCharacterDescriptionData(
        script_id=params.script_id,
        new_description=params.new_description,
        reasoning=params.reasoning
    )
    return StageCharacterDescriptionToolResponse(
        staged_update=staged_data,
        message="Character description update has been staged for your review."
    )

class ScriptCollaboratorAgent(Agent):
    def __init__(self, **kwargs):
        super().__init__(
            name="ScriptCollaboratorAgent",
            instructions=AGENT_INSTRUCTIONS,
            model=OPENAI_AGENT_MODEL,
            tools=[
                get_script_context, 
                propose_multiple_line_modifications,
                get_line_details,
                add_to_scratchpad,
                update_character_description,
                stage_character_description_update
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