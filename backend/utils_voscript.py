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

def get_sibling_lines_in_category(db: Session, script_id: int, line_id: int, category_name: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Fetches sibling lines in the same category as the specified line.
    
    If category_name is provided, uses that to find siblings.
    Otherwise, determines the category from the specified line.
    
    Args:
        db: The database session.
        script_id: The ID of the parent VoScript.
        line_id: The ID of the line whose siblings to find.
        category_name: Optional name of the category to search in.
        limit: Maximum number of sibling lines to return.
        
    Returns:
        A list of sibling lines with their key details (line_key, text).
    """
    siblings = []
    try:
        # Determine the category if not provided
        if not category_name:
            line_context = get_line_context(db, line_id)
            if not line_context:
                logging.warning(f"get_sibling_lines_in_category: Line {line_id} not found.")
                return []
            category_name = line_context.get("category_name")
            if not category_name:
                logging.warning(f"get_sibling_lines_in_category: Line {line_id} has no category.")
                return []
        
        # Query lines in the same category, excluding the current line
        query = db.query(models.VoScriptLine).options(
            joinedload(models.VoScriptLine.template_line)
        ).filter(
            models.VoScriptLine.vo_script_id == script_id,
            models.VoScriptLine.id != line_id,
            models.VoScriptLine.generated_text != None,  # Exclude lines without generated text
            models.VoScriptLine.generated_text != ""     # Exclude empty strings
        ).join(
            models.VoScriptLine.template_line
        ).join(
            models.VoScriptTemplateLine.category
        ).filter(
            models.VoScriptTemplateCategory.name == category_name
        ).order_by(
            asc(models.VoScriptTemplateLine.order_index),
            asc(models.VoScriptLine.id)
        ).limit(limit)
        
        sibling_lines = query.all()
        
        # Format the results
        for line in sibling_lines:
            line_key = line.template_line.line_key if line.template_line else f"line_{line.id}"
            siblings.append({
                "line_id": line.id,
                "line_key": line_key,
                "text": line.generated_text
            })
            
        logging.info(f"get_sibling_lines_in_category: Found {len(siblings)} siblings for line {line_id} in category '{category_name}'.")
        return siblings
    
    except Exception as e:
        logging.exception(f"Error fetching sibling lines for line {line_id} in category '{category_name}': {e}")
        return []

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
             
        # MODIFIED: Don't use stored refinement_prompt
        script_refinement_prompt = None  # Set to None regardless of what's stored in DB

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
                "line_id": line.id,
                "is_locked": line.is_locked,
                "current_text": line.generated_text,
                "status": line.status,
                "latest_feedback": line.latest_feedback,
                "line_key": None,
                "line_template_hint": None,
                "category_name": None,
                "category_instructions": None,
                "script_name": parent_script.name,
                "character_description": parent_script.character_description,
                "template_name": parent_script.template.name if parent_script.template else None,
                "template_hint": parent_script.template.prompt_hint if parent_script.template else None,
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
             
        # MODIFIED: Don't use stored refinement_prompt
        script_refinement_prompt = None  # Set to None regardless of what's stored in DB
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
                "is_locked": line.is_locked,
                "current_text": line.generated_text,
                "status": line.status,
                "latest_feedback": line.latest_feedback,
                "line_key": None,
                "line_template_hint": None,
                "category_name": None,
                "category_instructions": None,
                "category_refinement_prompt": None, # MODIFIED: Always set to None
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
                    # MODIFIED: Don't use stored category.refinement_prompt
                    context["category_refinement_prompt"] = None
            
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
        line = db.query(models.VoScriptLine).options(
            joinedload(models.VoScriptLine.template_line)
        ).get(line_id)
        
        if not line:
            logging.warning(f"update_line_in_db: Line {line_id} not found for update.")
            return None

        # Update main fields
        line.generated_text = new_text
        line.status = new_status
        
        # Copy the line_key from template_line if it's not already set
        if line.line_key is None and line.template_line and line.template_line.line_key:
            line.line_key = line.template_line.line_key
            logging.info(f"Copying line_key '{line.template_line.line_key}' from template to line {line_id}")

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

def analyze_category_variety(db: Session, script_id: int, category_name: str) -> dict:
    """Analyzes the variety of lines in a category to identify potential repetition/similarity issues.
    
    Args:
        db: The database session
        script_id: The script ID to analyze
        category_name: The category name to analyze
        
    Returns:
        A dictionary with analysis results, including:
        - repeat_patterns: Common repeated patterns/phrases
        - similar_openings: Lines with similar opening words
        - overall_variety_score: 0-100 score of line variety
        - total_lines: Number of lines analyzed
        - improvement_suggestions: List of suggested improvements
    """
    try:
        # Get all lines in the category
        lines_to_analyze = get_category_lines_context(db, script_id, category_name)
        
        # Filter to only include lines with text
        lines_with_text = [line for line in lines_to_analyze if line.get('current_text')]
        
        if not lines_with_text:
            return {
                "total_lines": 0,
                "message": f"No lines with text found in category '{category_name}'",
                "variety_score": 0,
                "repeat_patterns": [],
                "similar_openings": [],
                "improvement_suggestions": []
            }
            
        # Extract just the text for analysis
        texts = [line.get('current_text', '') for line in lines_with_text]
        
        # Basic analysis
        total_lines = len(texts)
        
        # 1. Check for similar openings (first 3 words)
        openings = {}
        for text in texts:
            words = text.split()
            if len(words) >= 2:
                opening = ' '.join(words[:2]).lower()
                if opening in openings:
                    openings[opening].append(text)
                else:
                    openings[opening] = [text]
        
        repeated_openings = {k: v for k, v in openings.items() if len(v) > 1}
        
        # 2. Find common phrases (3+ words that appear multiple times)
        import re
        from collections import Counter
        
        # Extract 3-grams from all texts
        phrases = []
        for text in texts:
            # Clean text a bit
            clean_text = re.sub(r'[,.!?;:"]', '', text.lower())
            words = clean_text.split()
            if len(words) >= 3:
                for i in range(len(words) - 2):
                    phrase = ' '.join(words[i:i+3])
                    phrases.append(phrase)
        
        # Count occurrences
        phrase_counter = Counter(phrases)
        repeated_phrases = {phrase: count for phrase, count in phrase_counter.items() if count > 1}
        
        # 3. Measure vocabulary diversity
        all_words = []
        for text in texts:
            clean_text = re.sub(r'[,.!?;:"]', '', text.lower())
            all_words.extend(clean_text.split())
            
        unique_words = set(all_words)
        vocabulary_ratio = len(unique_words) / len(all_words) if all_words else 0
        
        # 4. Calculate an overall variety score (0-100)
        # Higher is better (more variety)
        opening_penalty = min(30, len(repeated_openings) * 10)
        phrase_penalty = min(30, sum(repeated_phrases.values()) * 5)
        vocab_score = min(40, int(vocabulary_ratio * 100))
        
        variety_score = max(0, 100 - opening_penalty - phrase_penalty + vocab_score)
        
        # 5. Generate improvement suggestions
        suggestions = []
        
        if repeated_openings:
            suggestions.append(f"Vary the opening words of lines. {len(repeated_openings)} different openings are used multiple times.")
            
        if repeated_phrases:
            suggestions.append(f"Avoid repeating common phrases. Found {len(repeated_phrases)} phrases used multiple times.")
            
        if vocabulary_ratio < 0.7:
            suggestions.append("Use more diverse vocabulary across lines.")
            
        # Add specific suggestions if score is low
        if variety_score < 50:
            suggestions.append("Consider regenerating some lines with more variety instruction.")
            
        # Return the analysis results
        return {
            "total_lines": total_lines,
            "variety_score": variety_score,
            "repeat_patterns": [{"phrase": k, "count": v} for k, v in repeated_phrases.items()],
            "similar_openings": [{"opening": k, "lines": v} for k, v in repeated_openings.items()],
            "vocabulary_ratio": round(vocabulary_ratio, 2),
            "improvement_suggestions": suggestions
        }
        
    except Exception as e:
        logging.exception(f"Error analyzing category variety for script {script_id}, category '{category_name}': {e}")
        return {
            "error": f"Failed to analyze category: {str(e)}",
            "variety_score": 0
        } 