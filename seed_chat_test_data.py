# seed_chat_test_data.py
from backend import models
from sqlalchemy.orm import Session
from datetime import datetime

def seed_data():
    db_session_gen = models.get_db()
    db: Session = next(db_session_gen)

    try:
        # 1. Create a VoScriptTemplate
        template = db.query(models.VoScriptTemplate).filter(models.VoScriptTemplate.name == "Chat Test Template").first()
        if not template:
            template = models.VoScriptTemplate(
                name="Chat Test Template",
                description="Template for testing AI Chat Collaborator features.",
                prompt_hint="General sci-fi theme."
            )
            db.add(template)
            db.commit()
            db.refresh(template)
            print(f"Created VoScriptTemplate: ID {template.id}, Name: {template.name}")
        else:
            print(f"Found existing VoScriptTemplate: ID {template.id}, Name: {template.name}")

        # 2. Create a VoScriptTemplateCategory
        category = db.query(models.VoScriptTemplateCategory).filter(
            models.VoScriptTemplateCategory.template_id == template.id,
            models.VoScriptTemplateCategory.name == "Chapter 1: Introductions"
        ).first()
        if not category:
            category = models.VoScriptTemplateCategory(
                template_id=template.id,
                name="Chapter 1: Introductions",
                prompt_instructions="Opening lines for the main character meeting an ally."
            )
            db.add(category)
            db.commit()
            db.refresh(category)
            print(f"Created VoScriptTemplateCategory: ID {category.id}, Name: {category.name}")
        else:
            print(f"Found existing VoScriptTemplateCategory: ID {category.id}, Name: {category.name}")

        # 3. Create a VoScript
        target_script_name = "AI Chat Test Script"
        script = db.query(models.VoScript).filter(models.VoScript.name == target_script_name).first()

        if not script:
            script = models.VoScript(
                template_id=template.id,
                name=target_script_name,
                character_description="A brave space explorer, curious and resourceful.",
                status="drafting"
            )
            db.add(script)
            db.commit()
            db.refresh(script)
            print(f"Created VoScript: ID {script.id}, Name: {script.name}")
        else:
            print(f"Found existing VoScript: ID {script.id}, Name: {script.name}")
        
        # Ensure script_id=1 exists or adjust message in agent test script
        # Forcing ID 1 can be problematic with auto-increment if table wasn't reset.
        # The test script should ideally fetch this script by name or use the ID it gets.
        # For now, we just print a warning if it's not 1.
        if script.id != 1:
            print(f"INFO: Created/found test script with ID {script.id} (test in agent uses ID 1 by default). You may need to adjust the test script or re-seed on a fresh DB for ID 1.")
        else:
            print(f"VoScript with ID 1 is '{script.name}'. Good for agent test script.")

        # 4. Create VoScriptLines, ensuring some are linked to the category
        existing_line_count = db.query(models.VoScriptLine).filter(
            models.VoScriptLine.vo_script_id == script.id,
            models.VoScriptLine.category_id == category.id # Only count lines for this specific category
        ).count()

        if existing_line_count == 0:
            lines_data = [
                {"line_key": "INTRO_001", "text": "Commander, we've arrived at the anomaly.", "order": 1, "category_id": category.id},
                {"line_key": "INTRO_002", "text": "Scanners are picking up strange energy readings.", "order": 2, "category_id": category.id},
                {"line_key": "INTRO_003", "text": "Let's proceed with caution. Any sign of hostiles?", "order": 3, "category_id": category.id},
                {"line_key": "INTRO_004", "text": "Not yet, but this silence is unsettling.", "order": 4, "category_id": category.id},
                # A line not in this category for testing scope (ensure category_id is None or different)
                {"line_key": "OTHER_001", "text": "Meanwhile, back at the ranch...", "order": 5, "category_id": None} 
            ]

            for i, line_data in enumerate(lines_data):
                vo_line = models.VoScriptLine(
                    vo_script_id=script.id,
                    category_id=line_data["category_id"],
                    line_key=line_data["line_key"],
                    generated_text=line_data["text"],
                    order_index=line_data["order"],
                    status="generated",
                    prompt_hint=f"Hint for {line_data['line_key']}"
                )
                db.add(vo_line)
            db.commit()
            print(f"Created {len(lines_data)} VoScriptLines for Script ID {script.id}.")
        else:
            print(f"Found {existing_line_count} existing lines for Script ID {script.id} and Category ID {category.id}. Skipping line creation.")

        print("Seeding complete.")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting data seeding for AI Chat Collaborator test...")
    seed_data()
    print("Data seeding script finished.") 