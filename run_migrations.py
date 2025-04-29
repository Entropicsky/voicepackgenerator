#!/usr/bin/env python
import os
import sys
from flask import Flask

def run_migrations():
    """
    Runs database migrations using Flask-Migrate
    This script should be used in the Heroku release phase
    """
    print("Starting database migrations...")
    
    try:
        # Import the required modules from our app
        print("Initializing Flask app...")
        from backend.app import app
        
        # Create application context
        print("Creating application context...")
        with app.app_context():
            print("Running migrations in app context...")
            from flask_migrate import upgrade as db_upgrade
            
            # Get migrations directory path
            migrations_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")
            print(f"Using migrations directory: {migrations_dir}")
            
            # Run migrations
            print("Running database upgrade...")
            db_upgrade(directory=migrations_dir)
            
            print("Migrations completed successfully!")
        
        return 0
            
    except Exception as e:
        print(f"Error running migrations: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_migrations()) 