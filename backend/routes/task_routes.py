"""
Routes for Celery task status checking.
"""
from flask import Blueprint
from celery.result import AsyncResult
from backend.utils.response_utils import make_api_response
from backend.celery_app import celery
import logging

task_bp = Blueprint('task', __name__, url_prefix='/api')

@task_bp.route('/task/<task_id>/status', methods=['GET'])
def get_task_status(task_id):
    """Endpoint to check the status of any Celery task by its ID."""
    try:
        # Use the celery instance imported from the module
        task_result = AsyncResult(task_id, app=celery)

        # --- ADDED DEBUG LOGGING for raw metadata --- #
        raw_meta = None
        try:
             raw_meta = task_result.backend.get_task_meta(task_id)
             # Log the raw metadata BEFORE attempting to decode/process it
             logging.debug(f"Raw task meta for {task_id} from backend: {raw_meta}") 
        except Exception as meta_exc:
             logging.error(f"Error fetching raw task meta for {task_id}: {meta_exc}")
             # If we can't even get the meta, return an error state directly
             return make_api_response(data={
                 'task_id': task_id,
                 'status': 'FETCH_ERROR',
                 'info': {'error': f'Failed to fetch task metadata: {meta_exc}'}
             })
        # --- END ADDED DEBUG LOGGING --- #

        # FIX: Try getting state directly from backend to potentially avoid result decoding
        # current_status = task_result.backend.get_state(task_id) # This might implicitly use get_task_meta
        # Get status preferably from the raw_meta if available
        current_status = raw_meta.get('status') if raw_meta else task_result.state
        
        # If backend doesn't support it or fails, fallback (though unlikely needed)
        if current_status is None:
             logging.warning(f"Could not determine status for {task_id} from metadata or state, falling back to task_result.state")
             current_status = task_result.state

        response_data = {
            'task_id': task_id,
            'status': current_status, 
            'info': None
        }

        # Safely try to get task info, handling potential decoding errors
        task_info = None
        if current_status != 'FETCH_ERROR': # Only try to get info if metadata fetch succeeded
            try:
                # Accessing .info can trigger the backend decoding based on status
                # If status is FAILURE, Celery's info property might try to decode the problematic 'result'
                if current_status == 'FAILURE':
                    # Attempt to get traceback if available from raw meta
                    traceback = raw_meta.get('traceback')
                    # Try to safely get the potentially problematic result
                    error_result = raw_meta.get('result') 
                    logging.warning(f"Task {task_id} status is FAILURE. Raw result: {error_result}, Traceback: {traceback}")
                    # Construct info manually to avoid Celery's potentially broken exception_to_python
                    response_data['info'] = {'error': f"Task failed (raw result: {error_result})", 'traceback': traceback}
                else:
                    # For other statuses, accessing info might be safer or might return the raw meta's result
                    task_info = task_result.info # This might still fail if the result payload itself is corrupt
                    logging.debug(f"Task {task_id} info retrieved: {task_info}")
                    # Fallback processing if task_info is still None or unexpected type
                    if task_info is None:
                         response_data['info'] = raw_meta.get('result', {'status': 'Info unavailable'}) if raw_meta else {'status': 'Info unavailable'}
                    else:
                         response_data['info'] = task_info
                 
            except ValueError as decode_error:
                # Handle the specific error we saw in the logs
                logging.warning(f"Could not decode task result info for {task_id} (status: {current_status}): {decode_error}. Setting info to error message.")
                response_data['info'] = {'error': f'Failed to decode task result: {decode_error}', 'traceback': raw_meta.get('traceback') if raw_meta else None}
            except Exception as e:
                # Catch other potential errors during info access
                logging.error(f"Unexpected error accessing/processing task info for {task_id} (status: {current_status}): {e}")
                response_data['info'] = {'error': f'Error processing task info: {e}', 'traceback': raw_meta.get('traceback') if raw_meta else None}
        
        # --- Refined info processing based on status --- #
        # Check if info was already populated due to FAILURE or error handling
        if response_data.get('info') is None and current_status != 'FETCH_ERROR':
            if current_status == 'PENDING':
                response_data['info'] = {'status': 'Task is waiting to be processed.'}
            elif current_status == 'SUCCESS':
                # Use the task_info retrieved earlier (which might be the raw result)
                response_data['info'] = task_info if task_info is not None else (raw_meta.get('result') if raw_meta else {'status': 'Completed'}) 
            else: # STARTED, RETRY, custom states
                if isinstance(task_info, dict):
                    response_data['info'] = task_info
                elif task_info is not None:
                     response_data['info'] = {'status': str(task_info)}
                else:
                    # Fallback using raw meta if task_info was None
                    response_data['info'] = raw_meta.get('result', {'status': 'Processing...'}) if raw_meta else {'status': 'Processing...'}

        return make_api_response(data=response_data)

    except Exception as e:
        # Catch errors in the overall endpoint logic (e.g., creating AsyncResult)
        logging.exception(f"Error checking task status for {task_id}: {e}")
        # Return 500 if the endpoint itself fails critically 
        return make_api_response(error="Failed to retrieve task status", status_code=500) 