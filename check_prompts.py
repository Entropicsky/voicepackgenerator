#!/usr/bin/env python3
# Script to check refinement_prompt values in vo_scripts table

import subprocess

# PostgreSQL container ID
container_id = "5fd04d578325"

# SQL query to get script ID, name, and refinement_prompt
sql_cmd = """
SELECT id, name, refinement_prompt 
FROM vo_scripts
ORDER BY id;
"""

try:
    # Execute SQL command
    cmd = ["docker", "exec", container_id, "psql", "-U", "postgres", "-d", "app", "-t", "-c", sql_cmd]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    # Process and print the results
    print("\nScript ID | Name | Refinement Prompt")
    print("-" * 80)
    
    for line in result.stdout.strip().split('\n'):
        if not line.strip():
            continue
            
        parts = line.split('|')
        if len(parts) >= 3:
            script_id = parts[0].strip()
            name = parts[1].strip()
            prompt = parts[2].strip() if parts[2].strip() else "NULL"
            
            # For display purposes, truncate long prompts but show more content
            if prompt != "NULL" and len(prompt) > 40:
                display_prompt = prompt[:40] + "..."
            else:
                display_prompt = prompt
                
            print(f"{script_id:<9} | {name[:20]:<20} | {display_prompt}")
            
            # If script ID is 6 (the one with issues), show the full prompt
            if script_id.strip() == "6":
                print("\nFULL CONTENT OF REFINEMENT_PROMPT FOR SCRIPT ID 6:")
                print("-" * 80)
                print(prompt)
                print("-" * 80)
    
except subprocess.CalledProcessError as e:
    print(f"Error executing command: {e}")
    print(f"Error output: {e.stderr}")
except Exception as e:
    print(f"Error: {str(e)}") 