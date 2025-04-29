#!/usr/bin/env python3
# Temporary script to check the schema of the vo_scripts table

import os
import sys
import subprocess

# PostgreSQL container ID
container_id = "5fd04d578325"

# Define the SQL command to get all column names
sql_cmd = """
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'vo_scripts'
ORDER BY ordinal_position;
"""

try:
    # Execute SQL command
    cmd = ["docker", "exec", container_id, "psql", "-U", "postgres", "-d", "app", "-t", "-c", sql_cmd]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    rows = [line.strip().split('|') for line in result.stdout.strip().split('\n') if line.strip()]
    
    if not rows:
        print("No columns found for vo_scripts table")
        sys.exit(1)
    
    print(f"\nColumns in vo_scripts table:\n")
    print(f"{'Column Name':<30} | {'Data Type':<20}")
    print(f"{'-'*30}-|-{'-'*20}")
    
    for row in rows:
        if len(row) >= 2:
            column_name = row[0].strip()
            data_type = row[1].strip()
            print(f"{column_name:<30} | {data_type:<20}")
            
except subprocess.CalledProcessError as e:
    print(f"Error executing command: {e}")
    print(f"Error output: {e.stderr}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {str(e)}")
    sys.exit(1) 