# backend/routes/vo_template_routes.py

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging

# Assuming models and helpers are accessible, adjust imports as necessary
# Might need to adjust relative paths depending on final structure
from backend import models
from backend.models import get_db # Import get_db specifically
from backend.app import make_api_response, model_to_dict # Example: Import helpers from app

vo_template_bp = Blueprint('vo_template_api', __name__, url_prefix='/api')

# Routes will be moved here...
@vo_template_bp.route('/vo-script-templates', methods=['GET'])
def list_vo_script_templates():
    """Lists all VO script templates."""
    db: Session = None
    try:
        db = next(get_db()) # Use imported get_db
        templates = db.query(models.VoScriptTemplate).order_by(models.VoScriptTemplate.name).all()
        # Use helper to convert list of models to list of dicts, selecting specific keys
        template_list = [model_to_dict(t, ['id', 'name', 'description']) for t in templates]
        logging.info(f"Returning {len(template_list)} VO script templates.")
        return make_api_response(data=template_list)
    except Exception as e:
        logging.exception(f"Error listing VO script templates: {e}")
        return make_api_response(error="Failed to list VO script templates", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-templates', methods=['POST'])
def create_vo_script_template():
    """Creates a new VO script template."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    prompt_hint = data.get('prompt_hint')

    if not name:
        return make_api_response(error="Missing required field: name", status_code=400)

    db: Session = None
    try:
        db = next(get_db()) # Use imported get_db
        new_template = models.VoScriptTemplate(
            name=name,
            description=description,
            prompt_hint=prompt_hint
        )
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        logging.info(f"Created VO script template ID {new_template.id} with name '{name}'")
        # Use helper to convert the newly created object to a dict for the response
        return make_api_response(data=model_to_dict(new_template), status_code=201)
    except IntegrityError as e:
        db.rollback()
        # Check if it's a unique constraint violation for the name
        # Need to check specific database error details which might vary
        err_str = str(e.orig).lower()
        # Broad check for unique violation related to the name key
        if "unique constraint" in err_str and (
            "vo_script_templates_name_key" in err_str or 
            "vo_script_templates.name" in err_str # Added check for SQLite-style message
        ):
             logging.warning(f"Attempted to create template with duplicate name: {name}")
             return make_api_response(error=f"Template name '{name}' already exists.", status_code=409)
        else:
             # Log other integrity errors
             logging.exception(f"Database integrity error creating template: {e}")
             return make_api_response(error="Database error creating template.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error creating VO script template: {e}")
        return make_api_response(error="Failed to create VO script template", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-templates/<int:template_id>', methods=['GET'])
def get_vo_script_template(template_id):
    """Gets details for a specific VO script template."""
    db: Session = None
    try:
        db = next(get_db())
        template = db.query(models.VoScriptTemplate).get(template_id)
        if template is None:
            return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)
        # Return all fields for the specific template
        return make_api_response(data=model_to_dict(template))
    except Exception as e:
        logging.exception(f"Error getting VO script template {template_id}: {e}")
        return make_api_response(error="Failed to get VO script template", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-templates/<int:template_id>', methods=['PUT'])
def update_vo_script_template(template_id):
    """Updates an existing VO script template."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    
    db: Session = None
    try:
        db = next(get_db())
        template = db.query(models.VoScriptTemplate).get(template_id)
        if template is None:
            return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)

        updated = False
        # Update fields only if they are present in the request data
        if 'name' in data:
            new_name = data['name']
            if not new_name:
                 return make_api_response(error="Name cannot be empty", status_code=400)
            if new_name != template.name:
                 template.name = new_name
                 updated = True
        if 'description' in data:
            if data['description'] != template.description:
                template.description = data['description']
                updated = True
        if 'prompt_hint' in data:
             if data['prompt_hint'] != template.prompt_hint:
                template.prompt_hint = data['prompt_hint']
                updated = True

        if not updated:
            return make_api_response(data=model_to_dict(template)) # Return current data if no changes

        db.commit()
        db.refresh(template)
        logging.info(f"Updated VO script template ID {template.id}")
        return make_api_response(data=model_to_dict(template))
    
    except IntegrityError as e:
        db.rollback()
        err_str = str(e.orig).lower()
        if "unique constraint" in err_str and (
            "vo_script_templates_name_key" in err_str or 
            "vo_script_templates.name" in err_str
        ):
             # Use the name from the request data for the error message
             failed_name = data.get('name', '(unknown)') 
             logging.warning(f"Attempted to update template {template_id} with duplicate name: {failed_name}")
             return make_api_response(error=f"Template name '{failed_name}' already exists.", status_code=409)
        else:
             logging.exception(f"Database integrity error updating template {template_id}: {e}")
             return make_api_response(error="Database error updating template.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating VO script template {template_id}: {e}")
        return make_api_response(error="Failed to update VO script template", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-templates/<int:template_id>', methods=['DELETE'])
def delete_vo_script_template(template_id):
    """Deletes a VO script template."""
    db: Session = None
    try:
        db = next(get_db())
        template = db.query(models.VoScriptTemplate).get(template_id)
        if template is None:
            return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)
        
        template_name = template.name # Get name for logging before deleting
        db.delete(template)
        db.commit()
        logging.info(f"Deleted VO script template ID {template_id} (Name: '{template_name}')")
        return make_api_response(data={"message": f"Template '{template_name}' deleted successfully"})
    except Exception as e:
        db.rollback()
        logging.exception(f"Error deleting VO script template {template_id}: {e}")
        return make_api_response(error="Failed to delete VO script template", status_code=500)
    finally:
        if db and db.is_active: db.close()

# --- VoScriptTemplateCategory Routes --- #

@vo_template_bp.route('/vo-script-template-categories', methods=['GET'])
def list_vo_script_template_categories():
    """Lists all VO script template categories, optionally filtered by template_id."""
    template_id_filter = request.args.get('template_id', type=int)
    db: Session = None
    try:
        db = next(get_db())
        query = db.query(models.VoScriptTemplateCategory)
        if template_id_filter:
            # Verify template exists
            template = db.query(models.VoScriptTemplate).get(template_id_filter)
            if not template:
                 return make_api_response(error=f"Template with ID {template_id_filter} not found", status_code=404)
            query = query.filter(models.VoScriptTemplateCategory.template_id == template_id_filter)
            
        categories = query.order_by(models.VoScriptTemplateCategory.template_id, models.VoScriptTemplateCategory.name).all()
        category_list = [model_to_dict(c, ['id', 'template_id', 'name']) for c in categories]
        logging.info(f"Returning {len(category_list)} VO script template categories.")
        return make_api_response(data=category_list)
    except Exception as e:
        logging.exception(f"Error listing VO script template categories: {e}")
        return make_api_response(error="Failed to list VO script template categories", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-categories', methods=['POST'])
def create_vo_script_template_category():
    """Creates a new VO script template category."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    template_id = data.get('template_id')
    name = data.get('name')
    prompt_instructions = data.get('prompt_instructions')

    if not template_id or not name:
        return make_api_response(error="Missing required fields: template_id and name", status_code=400)
    
    try:
         # Validate template_id is int
        template_id = int(template_id)
    except (ValueError, TypeError):
        return make_api_response(error="Invalid template_id format, must be an integer.", status_code=400)

    db: Session = None
    try:
        db = next(get_db())
        # Verify parent template exists
        template = db.query(models.VoScriptTemplate).get(template_id)
        if not template:
            return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)
        
        new_category = models.VoScriptTemplateCategory(
            template_id=template_id,
            name=name,
            prompt_instructions=prompt_instructions
        )
        db.add(new_category)
        db.commit()
        db.refresh(new_category)
        logging.info(f"Created VO script category ID {new_category.id} ('{name}') for template ID {template_id}")
        return make_api_response(data=model_to_dict(new_category), status_code=201)
    except IntegrityError as e:
        db.rollback()
        err_str = str(e.orig).lower()
        # Check for unique constraint violation on (template_id, name)
        if "unique constraint" in err_str and "uq_category_template_name" in err_str:
             logging.warning(f"Attempted to create category with duplicate name '{name}' for template ID {template_id}")
             return make_api_response(error=f"Category name '{name}' already exists for this template.", status_code=409)
        # Check for foreign key violation (less likely due to check above, but good practice)
        elif "foreign key constraint" in err_str:
             logging.error(f"Foreign key violation creating category for template ID {template_id}: {e}")
             return make_api_response(error=f"Template with ID {template_id} not found or other FK issue.", status_code=404) 
        else:
             logging.exception(f"Database integrity error creating category: {e}")
             return make_api_response(error="Database error creating category.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error creating VO script template category: {e}")
        return make_api_response(error="Failed to create VO script template category", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-categories/<int:category_id>', methods=['GET'])
def get_vo_script_template_category(category_id):
    """Gets details for a specific VO script template category."""
    db: Session = None
    try:
        db = next(get_db())
        category = db.query(models.VoScriptTemplateCategory).get(category_id)
        if category is None:
            return make_api_response(error=f"Category with ID {category_id} not found", status_code=404)
        # Return all fields for the specific category
        return make_api_response(data=model_to_dict(category))
    except Exception as e:
        logging.exception(f"Error getting VO script template category {category_id}: {e}")
        return make_api_response(error="Failed to get VO script template category", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-categories/<int:category_id>', methods=['PUT'])
def update_vo_script_template_category(category_id):
    """Updates an existing VO script template category."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    
    db: Session = None
    try:
        db = next(get_db())
        category = db.query(models.VoScriptTemplateCategory).get(category_id)
        if category is None:
            return make_api_response(error=f"Category with ID {category_id} not found", status_code=404)

        updated = False
        original_name = category.name # Store original name for potential unique check
        
        if 'name' in data:
            new_name = data['name']
            if not new_name:
                 return make_api_response(error="Name cannot be empty", status_code=400)
            if new_name != category.name:
                 category.name = new_name
                 updated = True
                 
        if 'prompt_instructions' in data:
            if data['prompt_instructions'] != category.prompt_instructions:
                category.prompt_instructions = data['prompt_instructions']
                updated = True

        if not updated:
            return make_api_response(data=model_to_dict(category)) # Return current data if no changes

        db.commit()
        db.refresh(category)
        logging.info(f"Updated VO script category ID {category.id} for template ID {category.template_id}")
        return make_api_response(data=model_to_dict(category))
    
    except IntegrityError as e:
        db.rollback()
        err_str = str(e.orig).lower()
        if "unique constraint" in err_str and "uq_category_template_name" in err_str:
             failed_name = data.get('name', original_name) # Use new name if provided, else original
             logging.warning(f"Attempted to update category {category_id} with duplicate name: {failed_name} for template ID {category.template_id}")
             return make_api_response(error=f"Category name '{failed_name}' already exists for this template.", status_code=409)
        else:
             logging.exception(f"Database integrity error updating category {category_id}: {e}")
             return make_api_response(error="Database error updating category.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating VO script template category {category_id}: {e}")
        return make_api_response(error="Failed to update VO script template category", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-categories/<int:category_id>', methods=['DELETE'])
def delete_vo_script_template_category(category_id):
    """Deletes a VO script template category."""
    db: Session = None
    try:
        db = next(get_db())
        category = db.query(models.VoScriptTemplateCategory).get(category_id)
        if category is None:
            return make_api_response(error=f"Category with ID {category_id} not found", status_code=404)
        
        category_name = category.name # Get name for logging before deleting
        template_id = category.template_id
        db.delete(category)
        db.commit()
        logging.info(f"Deleted VO script category ID {category_id} (Name: '{category_name}') from template ID {template_id}")
        return make_api_response(data={"message": f"Category '{category_name}' deleted successfully"})
    except Exception as e:
        db.rollback()
        # Add specific check for foreign key violation if lines depend on this category
        if isinstance(e, IntegrityError) and "foreign key constraint" in str(e.orig).lower():
             logging.warning(f"Attempted to delete category {category_id} which is still referenced by template lines.")
             return make_api_response(error=f"Cannot delete category '{category.name}' because it still has lines associated with it.", status_code=409)
        
        logging.exception(f"Error deleting VO script template category {category_id}: {e}")
        return make_api_response(error="Failed to delete VO script template category", status_code=500)
    finally:
        if db and db.is_active: db.close()

# --- VoScriptTemplateLine Routes --- #

@vo_template_bp.route('/vo-script-template-lines', methods=['GET'])
def list_vo_script_template_lines():
    """Lists all VO script template lines, optionally filtered by template_id or category_id."""
    template_id_filter = request.args.get('template_id', type=int)
    category_id_filter = request.args.get('category_id', type=int)
    db: Session = None
    try:
        db = next(get_db())
        query = db.query(models.VoScriptTemplateLine)
        
        # Validate filters exist before applying them
        if template_id_filter:
            # Corrected: Query the full class to use .get()
            template = db.query(models.VoScriptTemplate).get(template_id_filter)
            if not template:
                 return make_api_response(error=f"Template with ID {template_id_filter} not found", status_code=404)
            query = query.filter(models.VoScriptTemplateLine.template_id == template_id_filter)
        
        if category_id_filter:
            # Corrected: Query the full class to use .get()
            category = db.query(models.VoScriptTemplateCategory).get(category_id_filter)
            if not category:
                 return make_api_response(error=f"Category with ID {category_id_filter} not found", status_code=404)
            # Ensure category belongs to the specified template if both filters are used
            if template_id_filter and category.template_id != template_id_filter:
                return make_api_response(error=f"Category ID {category_id_filter} does not belong to Template ID {template_id_filter}", status_code=400)
            query = query.filter(models.VoScriptTemplateLine.category_id == category_id_filter)
            
        lines = query.order_by(models.VoScriptTemplateLine.template_id, models.VoScriptTemplateLine.order_index).all()
        line_list = [model_to_dict(l, ['id', 'template_id', 'category_id', 'line_key', 'order_index']) for l in lines]
        logging.info(f"Returning {len(line_list)} VO script template lines.")
        return make_api_response(data=line_list)
    except Exception as e:
        logging.exception(f"Error listing VO script template lines: {e}")
        return make_api_response(error="Failed to list VO script template lines", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-lines', methods=['POST'])
def create_vo_script_template_line():
    """Creates a new VO script template line."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    template_id = data.get('template_id')
    category_id = data.get('category_id')
    line_key = data.get('line_key')
    prompt_hint = data.get('prompt_hint')
    order_index = data.get('order_index')

    if not all([template_id, category_id, line_key, order_index is not None]):
        return make_api_response(error="Missing required fields: template_id, category_id, line_key, order_index", status_code=400)

    try:
        template_id = int(template_id)
        category_id = int(category_id)
        order_index = int(order_index)
    except (ValueError, TypeError):
        return make_api_response(error="template_id, category_id, and order_index must be integers.", status_code=400)

    db: Session = None
    try:
        db = next(get_db())
        # Verify parent template and category exist and are linked
        category = db.query(models.VoScriptTemplateCategory).filter(
            models.VoScriptTemplateCategory.id == category_id,
            models.VoScriptTemplateCategory.template_id == template_id
        ).first()
        if not category:
            # Check if template exists at all to give a better error
            template_exists = db.query(models.VoScriptTemplate.id).get(template_id)
            if not template_exists:
                return make_api_response(error=f"Template with ID {template_id} not found", status_code=404)
            else:
                return make_api_response(error=f"Category with ID {category_id} not found or does not belong to template ID {template_id}", status_code=404)
        
        new_line = models.VoScriptTemplateLine(
            template_id=template_id,
            category_id=category_id,
            line_key=line_key,
            prompt_hint=prompt_hint,
            order_index=order_index
        )
        db.add(new_line)
        db.commit()
        db.refresh(new_line)
        logging.info(f"Created VO script line ID {new_line.id} ('{line_key}') for template ID {template_id}")
        return make_api_response(data=model_to_dict(new_line), status_code=201)
    except IntegrityError as e:
        db.rollback()
        err_str = str(e.orig).lower()
        if "unique constraint" in err_str and "uq_template_line_key" in err_str:
             logging.warning(f"Attempted to create line with duplicate key '{line_key}' for template ID {template_id}")
             return make_api_response(error=f"Line key '{line_key}' already exists for this template.", status_code=409)
        elif "foreign key constraint" in err_str:
             logging.error(f"Foreign key violation creating line for template ID {template_id} / category ID {category_id}: {e}")
             # Re-check existence for better error message
             if not db.query(models.VoScriptTemplate).get(template_id):
                  return make_api_response(error=f"Template with ID {template_id} not found.", status_code=404)
             if not db.query(models.VoScriptTemplateCategory).get(category_id):
                  return make_api_response(error=f"Category with ID {category_id} not found.", status_code=404)
             # If both exist, the category likely doesn't belong to the template (checked before commit, but double-checking)
             return make_api_response(error=f"Category ID {category_id} may not belong to Template ID {template_id}.", status_code=400)
        else:
             logging.exception(f"Database integrity error creating line: {e}")
             return make_api_response(error="Database error creating line.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error creating VO script template line: {e}")
        return make_api_response(error="Failed to create VO script template line", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-lines/<int:line_id>', methods=['GET'])
def get_vo_script_template_line(line_id):
    """Gets details for a specific VO script template line."""
    db: Session = None
    try:
        db = next(get_db())
        line = db.query(models.VoScriptTemplateLine).get(line_id)
        if line is None:
            return make_api_response(error=f"Template line with ID {line_id} not found", status_code=404)
        return make_api_response(data=model_to_dict(line))
    except Exception as e:
        logging.exception(f"Error getting VO script template line {line_id}: {e}")
        return make_api_response(error="Failed to get VO script template line", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-lines/<int:line_id>', methods=['PUT'])
def update_vo_script_template_line(line_id):
    """Updates an existing VO script template line."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)
    data = request.get_json()
    
    db: Session = None
    try:
        db = next(get_db())
        line = db.query(models.VoScriptTemplateLine).get(line_id)
        if line is None:
            return make_api_response(error=f"Template line with ID {line_id} not found", status_code=404)

        updated = False
        original_line_key = line.line_key
        original_category_id = line.category_id
        
        # Validate and update fields if present in request
        if 'category_id' in data:
            try:
                new_category_id = int(data['category_id'])
                # Verify category exists and belongs to the same template
                category = db.query(models.VoScriptTemplateCategory).filter(
                    models.VoScriptTemplateCategory.id == new_category_id,
                    models.VoScriptTemplateCategory.template_id == line.template_id
                ).first()
                if not category:
                    return make_api_response(error=f"Category ID {new_category_id} not found or does not belong to template ID {line.template_id}", status_code=400)
                if new_category_id != line.category_id:
                    line.category_id = new_category_id
                    updated = True
            except (ValueError, TypeError):
                 return make_api_response(error="Invalid category_id format, must be an integer.", status_code=400)
                 
        if 'line_key' in data:
            new_line_key = data['line_key']
            if not new_line_key:
                 return make_api_response(error="Line key cannot be empty", status_code=400)
            if new_line_key != line.line_key:
                 line.line_key = new_line_key
                 updated = True
                 
        if 'prompt_hint' in data:
            if data['prompt_hint'] != line.prompt_hint:
                line.prompt_hint = data['prompt_hint']
                updated = True
                
        if 'order_index' in data:
            try:
                new_order_index = int(data['order_index'])
                if new_order_index != line.order_index:
                    line.order_index = new_order_index
                    updated = True
            except (ValueError, TypeError):
                 return make_api_response(error="Invalid order_index format, must be an integer.", status_code=400)

        if not updated:
            return make_api_response(data=model_to_dict(line)) # Return current data

        db.commit()
        db.refresh(line)
        logging.info(f"Updated VO script template line ID {line.id}")
        return make_api_response(data=model_to_dict(line))
    
    except IntegrityError as e:
        db.rollback()
        err_str = str(e.orig).lower()
        if "unique constraint" in err_str and "uq_template_line_key" in err_str:
             failed_key = data.get('line_key', original_line_key)
             logging.warning(f"Attempted to update line {line_id} with duplicate key '{failed_key}' for template ID {line.template_id}")
             return make_api_response(error=f"Line key '{failed_key}' already exists for this template.", status_code=409)
        elif "foreign key constraint" in err_str:
             failed_category_id = data.get('category_id', original_category_id)
             logging.error(f"Foreign key violation updating line {line_id} with category ID {failed_category_id}: {e}")
             # Should have been caught by checks above, but handle defensively
             return make_api_response(error=f"Invalid Category ID {failed_category_id}.", status_code=400)
        else:
             logging.exception(f"Database integrity error updating line {line_id}: {e}")
             return make_api_response(error="Database error updating line.", status_code=500)
    except Exception as e:
        db.rollback()
        logging.exception(f"Error updating VO script template line {line_id}: {e}")
        return make_api_response(error="Failed to update VO script template line", status_code=500)
    finally:
        if db and db.is_active: db.close()

@vo_template_bp.route('/vo-script-template-lines/<int:line_id>', methods=['DELETE'])
def delete_vo_script_template_line(line_id):
    """Deletes a VO script template line."""
    db: Session = None
    try:
        db = next(get_db())
        line = db.query(models.VoScriptTemplateLine).get(line_id)
        if line is None:
            return make_api_response(error=f"Template line with ID {line_id} not found", status_code=404)
        
        line_key = line.line_key # Get key for logging before deleting
        template_id = line.template_id
        db.delete(line)
        db.commit()
        logging.info(f"Deleted VO script template line ID {line_id} (Key: '{line_key}') from template ID {template_id}")
        return make_api_response(data={"message": f"Template line '{line_key}' deleted successfully"})
    except Exception as e:
        db.rollback()
        # Note: Deleting a line shouldn't typically cause IntegrityError unless referenced elsewhere unexpectedly
        logging.exception(f"Error deleting VO script template line {line_id}: {e}")
        return make_api_response(error="Failed to delete VO script template line", status_code=500)
    finally:
        if db and db.is_active: db.close() 