import json
import sys # For explicit stdout/stderr

try:
    import requests
except ImportError:
    print("ERROR: The 'requests' library is not installed. Please install it (e.g., pip install requests) and try again.", file=sys.stderr)
    sys.exit(1)

BASE_URL = "http://localhost:5001/api/vo-scripts"
TEST_SCRIPT_ID = 1
NON_EXISTENT_SCRIPT_ID = 9999
headers = {"Content-Type": "application/json"}

def print_response(label: str, response_obj):
    print(f"--- {label} ---START--- STATUS: {response_obj.status_code} ---", file=sys.stdout)
    try:
        print(f"RESPONSE BODY: {response_obj.json()}", file=sys.stdout)
    except requests.exceptions.JSONDecodeError:
        print(f"RESPONSE TEXT: {response_obj.text}", file=sys.stdout)
    except Exception as e_json:
        print(f"Error decoding JSON: {e_json}", file=sys.stderr)
        print(f"RESPONSE TEXT (fallback): {response_obj.text}", file=sys.stdout)
    print(f"--- {label} ---END--- ---", file=sys.stdout)
    sys.stdout.flush()

def run_test(label: str, method: str, url: str, payload_dict: dict = None, expected_status_code: int = 200):
    print(f"\nEXECUTING TEST: {label}", file=sys.stdout)
    print(f"URL: {method.upper()} {url}", file=sys.stdout)
    data_to_send = json.dumps(payload_dict) if payload_dict else None
    if payload_dict:
        print(f"PAYLOAD: {data_to_send}", file=sys.stdout)
    
    success = False
    try:
        if method.lower() == 'post':
            response = requests.post(url, headers=headers, data=data_to_send, timeout=10)
        elif method.lower() == 'get': # For future task status endpoint
            response = requests.get(url, headers=headers, timeout=10)
        else:
            print(f"Unsupported method: {method}", file=sys.stderr)
            return False
        
        print_response(label, response)
        
        if response.status_code == expected_status_code:
            if expected_status_code == 202: # Specifically for task dispatch
                if response.json().get("data", {}).get("task_id"):
                    print(f"SUCCESS: {label} - Task dispatched.", file=sys.stdout)
                    success = True
                else:
                    print(f"FAILURE: {label} - Expected 202 but no task_id in response data.", file=sys.stderr)
            else:
                print(f"SUCCESS: {label} - Status code {expected_status_code} matched.", file=sys.stdout)
                success = True
        else:
            print(f"FAILURE: {label} - Expected status {expected_status_code}, got {response.status_code}.", file=sys.stderr)
            
    except requests.exceptions.ConnectionError as e_conn:
        print(f"FAILURE: {label} - Connection Error. Is the backend server running at {BASE_URL}? Details: {e_conn}", file=sys.stderr)
    except requests.exceptions.Timeout as e_timeout:
        print(f"FAILURE: {label} - Request Timed Out. Details: {e_timeout}", file=sys.stderr)
    except requests.exceptions.RequestException as e_req:
        print(f"FAILURE: {label} - Generic Request Exception. Details: {e_req}", file=sys.stderr)
    except Exception as e_gen:
        print(f"FAILURE: {label} - An unexpected error occurred. Details: {e_gen}", file=sys.stderr)
    
    sys.stdout.flush()
    sys.stderr.flush()
    return success

if __name__ == "__main__":
    print("Starting API endpoint tests...\n", file=sys.stdout)
    
    task_id_for_status_check = None

    valid_payload_case1 = {
        "user_message": "Tell me about this script, please.",
        "initial_prompt_context_from_prior_sessions": [
            {"role": "user", "content": "Previously, we were discussing characters."}
        ],
        "current_context": {"category_id": 1}
    }
    print("\nEXECUTING TEST: Test Case 1: Valid Chat Request to get Task ID", file=sys.stdout)
    try:
        response_dispatch = requests.post(f"{BASE_URL}/{TEST_SCRIPT_ID}/chat", headers=headers, data=json.dumps(valid_payload_case1), timeout=10)
        print_response("Test Case 1: Valid Chat Request", response_dispatch)
        if response_dispatch.status_code == 202:
            response_json = response_dispatch.json()
            if response_json.get("data") and response_json["data"].get("task_id"):
                task_id_for_status_check = response_json["data"]["task_id"]
                print(f"SUCCESS: Task dispatched. Task ID: {task_id_for_status_check}", file=sys.stdout)
            else:
                print("FAILURE: Valid request did not return task_id in data.", file=sys.stderr)
        else:
            print(f"FAILURE: Valid request failed with status {response_dispatch.status_code}.", file=sys.stderr)
    except requests.exceptions.RequestException as e_req:
        print(f"FAILURE: Valid Chat Request - Request Exception. Details: {e_req}", file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()

    if task_id_for_status_check:
        print(f"\nWill attempt to check status for task: {task_id_for_status_check} in a few seconds...", file=sys.stdout)
        # Give Celery a moment to process
        import time
        time.sleep(10) # Wait 10 seconds for the task to (hopefully) complete
        
        status_url = f"http://localhost:5001/api/task/{task_id_for_status_check}/status"
        run_test(f"Test Case 1b: Check Task Status for {task_id_for_status_check}", 'get', status_url, expected_status_code=200)
        # Further checks inside run_test can be enhanced if needed to validate content of successful task.
    else:
        print("\nSKIPPING Test Case 1b: Check Task Status because no task_id was obtained.", file=sys.stderr)

    # Test Case 2: Invalid JSON Body - difficult to send truly malformed JSON string that requests lib won't try to fix or error on pre-send.
    # Instead, we test server's handling of non-JSON content type or unparsable body if it gets that far.
    # For now, let's send a valid structure but with a bad header later if needed, or rely on unit tests for Flask route for this.
    # Sending a string that is not JSON:
    print("\nEXECUTING TEST: Test Case 2: Malformed JSON string payload", file=sys.stdout)
    malformed_json_string = "{\"user_message\": \"Hi\" this is not valid JSON"
    try:
        response_malformed = requests.post(f"{BASE_URL}/{TEST_SCRIPT_ID}/chat", headers=headers, data=malformed_json_string, timeout=10)
        print_response("Test Case 2: Malformed JSON string payload", response_malformed)
        if response_malformed.status_code == 400:
            print("SUCCESS: Malformed JSON string payload - Status code 400 matched.", file=sys.stdout)
        else:
            print(f"FAILURE: Malformed JSON string payload - Expected status 400, got {response_malformed.status_code}.", file=sys.stderr)
    except requests.exceptions.RequestException as e_req:
        print(f"FAILURE: Test Case 2 - Request Exception. Details: {e_req}", file=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()

    missing_field_payload_case3 = {
        "initial_prompt_context_from_prior_sessions": []
    }
    run_test("Test Case 3: Missing required field (user_message)", 'post', f"{BASE_URL}/{TEST_SCRIPT_ID}/chat", missing_field_payload_case3, 400)

    run_test("Test Case 4: Non-existent script_id", 'post', f"{BASE_URL}/{NON_EXISTENT_SCRIPT_ID}/chat", valid_payload_case1, 404)

    print("\nAPI endpoint tests finished. Check backend and Celery worker logs for task processing details.", file=sys.stdout)
    sys.stdout.flush() 