# backend/utils_voscript.py
# This file will contain reusable database interaction logic specific to VO Scripts.

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload, selectinload # Import necessary loaders
from sqlalchemy import asc # Import asc for ordering
from backend import models
from datetime import datetime, timezone # Add datetime, timezone
import os # Need os for model name logging
from sqlalchemy.orm.attributes import flag_modified # Import flag_modified

# TODO: Implement DB utility functions (get_line_context, get_category_lines_context, get_script_lines_context, update_line_in_db)

def get_line_context(db: Session, line_id: int) -> Optional[Dict[str, Any]]:
    """Fetches comprehensive context for a single VO Script Line.

    Includes details from the line itself, its template line, template category,
    parent script, and parent template.

    Args:
        db: The database session.
        line_id: The ID of the VoScriptLine to fetch.

    Returns:
        A dictionary containing the context, or None if the line is not found.
    """
    try:
        line = db.query(models.VoScriptLine).options(
            # Eager load relationships needed for context
            joinedload(models.VoScriptLine.vo_script).joinedload(models.VoScript.template),
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category),
            # Ensure template_line's template is also loaded if accessing template hints directly from there
            # Redundant if accessing via vo_script.template, but safe to include
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.template) 
        ).filter(models.VoScriptLine.id == line_id).first()

        if not line:
            logging.warning(f"get_line_context: VoScriptLine with ID {line_id} not found.")
            return None

        # Build the context dictionary safely, handling potentially missing relations
        context = {
            "line_id": line.id,
            "current_text": line.generated_text,
            "status": line.status,
            "latest_feedback": line.latest_feedback,
            "line_key": None,
            "line_template_hint": None,
            "category_name": None,
            "category_instructions": None,
            "script_name": None,
            "character_description": None,
            "template_name": None,
            "template_hint": None,
        }

        if line.template_line:
            context["line_key"] = line.template_line.line_key
            context["line_template_hint"] = line.template_line.prompt_hint
            if line.template_line.category:
                context["category_name"] = line.template_line.category.name
                context["category_instructions"] = line.template_line.category.prompt_instructions
        
        # Get script and template info (prefer via vo_script relationship)
        script = line.vo_script
        template = script.template if script else None

        if script:
            context["script_name"] = script.name
            context["character_description"] = script.character_description
        
        if template:
             context["template_name"] = template.name
             context["template_hint"] = template.prompt_hint

        return context

    except Exception as e:
        logging.exception(f"Error fetching context for line {line_id}: {e}")
        return None 

def get_category_lines_context(db: Session, script_id: int, category_name: str) -> List[Dict[str, Any]]:
    """Fetches comprehensive context for all VO Script Lines within a specific category 
       for a given script, including the script's refinement prompt.

    Args:
        db: The database session.
        script_id: The ID of the parent VoScript.
        category_name: The name of the category to filter by.

    Returns:
        A list of context dictionaries for each line found, sorted by template order index.
    """
    lines_context = []
    try:
        # Fetch the parent script first to get its refinement prompt
        parent_script = db.query(models.VoScript).options(
            joinedload(models.VoScript.template) # Still need template info for lines later
        ).get(script_id)
        if not parent_script:
             logging.warning(f"get_category_lines_context: Parent script {script_id} not found.")
             return []
             
        script_refinement_prompt = parent_script.refinement_prompt

        # Now query the lines
        query = db.query(models.VoScriptLine).options(
            # Eager load needed relationships (vo_script relationship is already loaded implicitly 
            # via filter, but joinedload here ensures access via line.vo_script is efficient if needed,
            # although we primarily use parent_script now)
            joinedload(models.VoScriptLine.vo_script).joinedload(models.VoScript.template),
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category),
            joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.template)
        ).filter(
            models.VoScriptLine.vo_script_id == script_id
        ).join(
            models.VoScriptLine.template_line 
        ).join(
            models.VoScriptTemplateLine.category
        ).filter(
            models.VoScriptTemplateCategory.name == category_name
        ).order_by(
            asc(models.VoScriptTemplateLine.order_index),
            asc(models.VoScriptLine.id)
        )

        lines = query.all()

        if not lines:
            logging.info(f"get_category_lines_context: No lines found for script {script_id}, category '{category_name}'.")
            return []

        # Process each line found
        for line in lines:
            # Reuse get_line_context logic or replicate - replicating for clarity here
            context = {
                # ... basic line fields ...
                "line_id": line.id,
                "current_text": line.generated_text,
                "status": line.status,
                "latest_feedback": line.latest_feedback,
                "line_key": None,
                "line_template_hint": None,
                "category_name": None,
                "category_instructions": None,
                # Use parent_script object directly for script/template info
                "script_name": parent_script.name,
                "character_description": parent_script.character_description,
                "template_name": parent_script.template.name if parent_script.template else None,
                "template_hint": parent_script.template.prompt_hint if parent_script.template else None,
                # ADD SCRIPT PROMPT
                "script_refinement_prompt": script_refinement_prompt 
            }
            if line.template_line:
                context["line_key"] = line.template_line.line_key
                context["line_template_hint"] = line.template_line.prompt_hint
                if line.template_line.category:
                    context["category_name"] = line.template_line.category.name
                    context["category_instructions"] = line.template_line.category.prompt_instructions
            
            lines_context.append(context)

        logging.info(f"get_category_lines_context: Found {len(lines_context)} lines for script {script_id}, category '{category_name}'.")
        return lines_context

    except Exception as e:
        logging.exception(f"Error fetching context for script {script_id}, category '{category_name}': {e}")
        return [] # Return empty list on error

def get_script_lines_context(db: Session, script_id: int) -> List[Dict[str, Any]]:
    """Fetches comprehensive context for all VO Script Lines for a given script,
       including category refinement prompts.

    Args:
        db: The database session.
        script_id: The ID of the parent VoScript.

    Returns:
        A list of context dictionaries for each line found, sorted by template order index.
    """
    lines_context = []
    try:
        # Fetch the parent script first to get its refinement prompt and template info
        parent_script = db.query(models.VoScript).options(
            joinedload(models.VoScript.template).selectinload(models.VoScriptTemplate.categories) # Load template and its categories
        ).get(script_id)
        if not parent_script:
             logging.warning(f"get_script_lines_context: Parent script {script_id} not found.")
             return []
             
        script_refinement_prompt = parent_script.refinement_prompt
        template_categories = {c.id: c for c in parent_script.template.categories} if parent_script.template else {}

        # Now query the lines
        query = db.query(models.VoScriptLine).options(
            # Eager load relationships not already covered by parent_script load
            joinedload(models.VoScriptLine.template_line) # Need template line details
            # joinedload(models.VoScriptLine.template_line).joinedload(models.VoScriptTemplateLine.category), # Category info comes from parent_script now
            # joinedload(models.VoScriptLine.vo_script), # Parent script info comes from parent_script
        ).filter(
            models.VoScriptLine.vo_script_id == script_id
        ).join(
            models.VoScriptLine.template_line 
        ).order_by(
            asc(models.VoScriptTemplateLine.order_index),
            asc(models.VoScriptLine.id)
        )

        lines = query.all()

        if not lines:
            logging.info(f"get_script_lines_context: No lines found for script {script_id}.")
            return []

        # Process each line found
        for line in lines:
            context = {
                "line_id": line.id,
                "current_text": line.generated_text,
                "status": line.status,
                "latest_feedback": line.latest_feedback,
                "line_key": None,
                "line_template_hint": None,
                "category_name": None,
                "category_instructions": None,
                "category_refinement_prompt": None, # Add new field
                "script_name": parent_script.name,
                "character_description": parent_script.character_description,
                "template_name": parent_script.template.name if parent_script.template else None,
                "template_hint": parent_script.template.prompt_hint if parent_script.template else None,
                "script_refinement_prompt": script_refinement_prompt
            }
            if line.template_line:
                context["line_key"] = line.template_line.line_key
                context["line_template_hint"] = line.template_line.prompt_hint
                # Get category info from the pre-fetched template_categories dict
                category_id = line.template_line.category_id
                category = template_categories.get(category_id) if category_id else None
                if category:
                    context["category_name"] = category.name
                    context["category_instructions"] = category.prompt_instructions
                    context["category_refinement_prompt"] = category.refinement_prompt # Add category prompt
            
            lines_context.append(context)

        logging.info(f"get_script_lines_context: Found {len(lines_context)} lines for script {script_id}.")
        return lines_context

    except Exception as e:
        logging.exception(f"Error fetching context for script {script_id}: {e}")
        return [] # Return empty list on error

def update_line_in_db(db: Session, line_id: int, new_text: str, new_status: str, model_name: str) -> Optional[models.VoScriptLine]:
    """Updates the generated text and status for a specific VO Script Line,
       appending the change to its history.

    Args:
        db: The database session.
        line_id: The ID of the VoScriptLine to update.
        new_text: The new generated text.
        new_status: The new status for the line.
        model_name: The name of the model that generated/refined the text.

    Returns:
        The updated VoScriptLine object if successful, otherwise None.
    """
    try:
        line = db.query(models.VoScriptLine).get(line_id)
        if not line:
            logging.warning(f"update_line_in_db: Line {line_id} not found for update.")
            return None

        # Update main fields
        line.generated_text = new_text
        line.status = new_status

        # Update history
        current_history = line.generation_history if isinstance(line.generation_history, list) else []
        history_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "generation", # TODO: Maybe refine type based on context?
            "text": new_text,
            "model": model_name
        }
        current_history.append(history_entry)
        line.generation_history = current_history
        # Explicitly flag the JSONB field as modified for SQLAlchemy
        flag_modified(line, "generation_history")

        db.commit()
        logging.info(f"Successfully updated line {line_id} with status {new_status}.")
        return line
    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating line {line_id}: {e}")
        return None 