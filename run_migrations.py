#!/usr/bin/env python
import os
import subprocess
import sys

def run_migrations():
    """
    Runs database migrations using alembic directly
    This script should be used in the Heroku release phase
    """
    print("Starting database migrations...")
    
    try:
        # Change to directory containing migrations
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Run alembic upgrade command directly
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=current_dir,
            capture_output=True,
            text=True
        )
        
        # Print output
        print("STDOUT:", result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        # Check return code
        if result.returncode == 0:
            print("Migrations completed successfully!")
            return 0
        else:
            print(f"Migration failed with exit code {result.returncode}")
            return result.returncode
            
    except Exception as e:
        print(f"Error running migrations: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations()) 