import time
from backend.celery_app import celery # To get the task object
from backend.tasks import run_script_collaborator_chat_task # Import the task function directly for testing

if __name__ == "__main__":
    print("Attempting to trigger run_script_collaborator_chat_task...")

    # Mock data for the task
    test_script_id = 123 # Example script ID
    test_user_message = "Can you help me brainstorm some cool names for a fantasy character?"
    test_initial_context = [
        {"role": "user", "content": "Last time we talked about elves."},
        {"role": "assistant", "content": "Yes, and I suggested some elven city names."}
    ]
    test_current_focus = {"category_id": "cat_abc", "line_id": "line_123"}

    # Two ways to test a Celery task:
    # 1. Call the task function directly (useful for debugging the task logic without Celery worker overhead)
    print("\n--- Testing task function directly ---")
    try:
        direct_result = run_script_collaborator_chat_task(
            script_id=test_script_id,
            user_message=test_user_message,
            initial_prompt_context_from_prior_sessions=test_initial_context,
            current_context=test_current_focus
        )
        print(f"Direct call result: {direct_result}")
    except Exception as e:
        print(f"Error during direct task call: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Testing task via Celery .delay() (requires Celery worker to be running) ---")
    # 2. Send the task to the Celery worker using .delay() or .apply_async()
    # This requires your Celery worker to be running and configured to pick up this task.
    try:
        # Get the task from the Celery app instance by its registered name
        # The name is specified in @celery.task(name="run_script_collaborator_chat")
        task_instance = celery.signature("run_script_collaborator_chat")
        
        async_result = task_instance.delay(
            script_id=test_script_id,
            user_message=test_user_message,
            initial_prompt_context_from_prior_sessions=test_initial_context,
            current_context=test_current_focus
        )
        print(f"Task sent to Celery. Task ID: {async_result.id}")
        print("Waiting for result (up to 30 seconds)...")
        
        # Wait for the result with a timeout
        # Note: .get() is blocking. In a real app, you wouldn't block like this in main thread.
        try:
            result_from_worker = async_result.get(timeout=30) # Timeout after 30 seconds
            print(f"Result from Celery worker: {result_from_worker}")
            if async_result.successful():
                print("Task reported as successful by Celery.")
            else:
                print("Task reported as failed by Celery.")
                if async_result.traceback:
                    print("Celery task traceback:")
                    print(async_result.traceback)
        except TimeoutError:
            print("Timed out waiting for Celery task result. Ensure worker is running and picking up tasks.")
        except Exception as e_celery_get:
            print(f"Error getting result from Celery: {e_celery_get}")

    except Exception as e_celery_send:
        print(f"Error sending task to Celery: {e_celery_send}")
        import traceback
        traceback.print_exc()

    print("\nTest script finished.") 