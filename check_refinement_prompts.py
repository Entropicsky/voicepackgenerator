#!/usr/bin/env python3
# Temporary script to check refinement prompts in vo_scripts

import os
import sys
import subprocess
import json

# PostgreSQL container ID
container_id = "5fd04d578325"

# Define the SQL command to execute
sql_cmd = """
SELECT column_name 
FROM information_schema.columns 
WHERE table_name = 'vo_scripts' 
AND column_name LIKE '%refine%prompt%';
"""

try:
    # Execute SQL command to get column name
    cmd = ["docker", "exec", container_id, "psql", "-U", "postgres", "-d", "postgres", "-t", "-c", sql_cmd]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    column_name = result.stdout.strip()
    
    if not column_name:
        print("No column found with name like 'refine...prompt' in vo_scripts table")
        sys.exit(1)
    
    print(f"Found column name: {column_name}")
    
    # Query all prompts
    sql_query = f"SELECT id, {column_name} FROM vo_scripts ORDER BY id;"
    cmd = ["docker", "exec", container_id, "psql", "-U", "postgres", "-d", "postgres", "-t", "-c", sql_query]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    rows = [line.strip().split('|') for line in result.stdout.strip().split('\n') if line.strip()]
    
    if not rows:
        print("No rows found in vo_scripts table")
        sys.exit(0)
    
    print(f"\nRefinement prompts in vo_scripts table:\n")
    print(f"{'ID':<5} | {'Refinement Prompt'}")
    print(f"{'-'*5}-|-{'-'*70}")
    
    for row in rows:
        if len(row) >= 2:
            script_id = row[0].strip()
            prompt = row[1].strip() if row[1].strip() else "NULL"
            # Truncate long prompts
            if prompt != "NULL" and len(prompt) > 70:
                prompt = prompt[:67] + "..."
            print(f"{script_id:<5} | {prompt}")
            
except subprocess.CalledProcessError as e:
    print(f"Error executing command: {e}")
    print(f"Error output: {e.stderr}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1) 