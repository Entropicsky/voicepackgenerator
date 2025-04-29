#!/usr/bin/env python3

import subprocess

# Container ID for the PostgreSQL container
container_id = "5fd04d578325"  # Update this if needed

# SQL command to get all refinement_prompt values from vo_script_template_categories
sql_command = """
SELECT 
    c.id, 
    c.name, 
    c.refinement_prompt,
    t.name as template_name
FROM 
    vo_script_template_categories c
JOIN 
    vo_script_templates t ON c.template_id = t.id
ORDER BY 
    t.name, c.id;
"""

try:
    # Run the SQL command in the PostgreSQL container
    result = subprocess.run(
        ["docker", "exec", container_id, "psql", "-U", "postgres", "-d", "app", "-c", sql_command],
        capture_output=True,
        text=True,
        check=True
    )
    
    # Get the output
    output = result.stdout.strip()
    
    # Print header
    print("\nCategory ID | Name                | Template Name        | Refinement Prompt")
    print("-" * 100)
    
    # Parse and print the results
    lines = output.split('\n')
    data_lines = lines[2:-2]  # Skip header and footer
    
    for line in data_lines:
        parts = line.split('|')
        if len(parts) >= 4:
            category_id = parts[0].strip()
            name = parts[1].strip()
            refinement_prompt = parts[2].strip()
            template_name = parts[3].strip()
            
            # Print the data
            if refinement_prompt and len(refinement_prompt) > 40:
                truncated_prompt = refinement_prompt[:37] + '...'
                print(f"{category_id:<11} | {name:<20} | {template_name:<20} | {truncated_prompt}")
            else:
                print(f"{category_id:<11} | {name:<20} | {template_name:<20} | {refinement_prompt or 'NULL'}")
            
            # Print full content for categories with non-empty refinement prompts
            if refinement_prompt:
                print("\nFULL CONTENT OF REFINEMENT_PROMPT FOR CATEGORY:", name)
                print("-" * 80)
                print(refinement_prompt)
                print("-" * 80)
    
except subprocess.CalledProcessError as e:
    print(f"Error executing SQL command: {e}")
    print(f"Error output: {e.stderr}")
except Exception as e:
    print(f"An error occurred: {e}") 