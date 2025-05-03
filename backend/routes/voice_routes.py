# backend/routes/voice_routes.py
"""
Routes for voice-related operations.
"""
from flask import Blueprint, request, current_app
from backend import utils_elevenlabs
from backend.app import make_api_response

voice_bp = Blueprint('voice', __name__, url_prefix='/api')

# Standard preview text
VOICE_PREVIEW_TEXT = "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal."

@voice_bp.route('/voices', methods=['GET'])
def get_voices():
    """Endpoint to get available voices, supports filtering/sorting."""
    search = request.args.get('search', None)
    category = request.args.get('category', None)
    voice_type = request.args.get('voice_type', None)
    sort = request.args.get('sort', None)
    sort_direction = request.args.get('sort_direction', None)
    next_page_token = request.args.get('next_page_token', None)
    print(f"API Route /api/voices received search='{search}'")

    try:
        voices = utils_elevenlabs.get_available_voices(
            search=search,
            category=category,
            voice_type=voice_type,
            sort=sort,
            sort_direction=sort_direction,
            next_page_token=next_page_token
        )
        # V2 response includes more details, potentially filter/map here if needed
        # For now, return the full voice objects from V2
        return make_api_response(data=voices)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching voices via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/voices route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

@voice_bp.route('/models', methods=['GET'])
def get_models():
    """Endpoint to get available models, supports capability filtering."""
    capability = request.args.get('capability', None)
    require_sts = capability == 'sts'
    print(f"API Route /api/models received capability='{capability}', require_sts={require_sts}")
    
    try:
        models_list = utils_elevenlabs.get_available_models(require_sts=require_sts)
        
        model_options = [
            {"model_id": m.get('model_id'), "name": m.get('name')}
            for m in models_list if m.get('model_id') and m.get('name')
        ]
        return make_api_response(data=model_options)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"Error fetching models via API route: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        print(f"Unexpected error in /api/models route: {e}")
        return make_api_response(error="An unexpected error occurred", status_code=500)

@voice_bp.route('/voices/<string:voice_id>/preview', methods=['GET'])
def get_voice_preview(voice_id):
    """Generates and streams a short audio preview for a given voice ID."""
    from flask import Response
    import logging
    
    logging.info(f"Received preview request for voice_id: {voice_id}")
    
    # --- Get settings from query params --- 
    preview_settings = {}
    try:
        stability = request.args.get('stability', type=float)
        similarity = request.args.get('similarity', type=float)
        style = request.args.get('style', type=float)
        speed = request.args.get('speed', type=float)
        
        if stability is not None: preview_settings['stability'] = stability
        if similarity is not None: preview_settings['similarity_boost'] = similarity # Note key name difference
        if style is not None: preview_settings['style'] = style
        if speed is not None: preview_settings['speed'] = speed
        
        logging.info(f"Preview settings from query params: {preview_settings}")
    except Exception as parse_err:
        logging.warning(f"Could not parse preview settings from query params: {parse_err}")
        # Proceed without settings if parsing fails
        preview_settings = {}
    # --- End Get settings --- 
    
    try:
        # Use the new stream function from utils, passing settings
        preview_response = utils_elevenlabs.generate_preview_audio_stream(
            voice_id=voice_id,
            text=VOICE_PREVIEW_TEXT,
            # Pass parsed settings using dictionary unpacking
            **preview_settings 
        )
        
        # Check if the response has content before creating the Flask response
        if preview_response.content is None and preview_response.status_code != 200:
             # Handle case where the stream function failed gracefully but indicated an issue
             # Use the status code and potentially the content from the failed response
             logging.error(f"Preview generation failed upstream for {voice_id}. Status: {preview_response.status_code}")
             error_detail = "Preview generation failed."
             try: 
                 error_detail = preview_response.json().get('detail', error_detail)
             except: pass # Ignore if response isn't JSON
             return make_api_response(error=error_detail, status_code=preview_response.status_code)
        
        # Stream the audio content back
        # The iter_content chunk size can be adjusted
        def generate_chunks():
            try:
                for chunk in preview_response.iter_content(chunk_size=1024):
                    yield chunk
                logging.info(f"Finished streaming preview for {voice_id}")
            except Exception as stream_err:
                logging.error(f"Error during preview streaming for {voice_id}: {stream_err}")
                # Don't yield further, let the client handle the broken stream
            finally:
                 # Ensure the underlying connection is closed if the response object supports it
                if hasattr(preview_response, 'close'):
                     preview_response.close()

        logging.info(f"Streaming preview audio for {voice_id}...")
        return Response(generate_chunks(), mimetype='audio/mpeg')

    except utils_elevenlabs.ElevenLabsError as e:
        logging.error(f"ElevenLabsError generating preview for {voice_id}: {e}")
        return make_api_response(error=str(e), status_code=500)
    except Exception as e:
        logging.exception(f"Unexpected error generating preview for {voice_id}: {e}") # Log traceback
        return make_api_response(error="An unexpected server error occurred", status_code=500)

# --- Voice Design API Endpoints --- #
@voice_bp.route('/voice-design/previews', methods=['POST'])
def create_voice_design_previews():
    """Endpoint to generate voice previews based on description and settings."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    
    # Extract parameters from request data
    voice_description = data.get('voice_description')
    text = data.get('text') # Get the text (guaranteed by frontend now)
    # auto_generate_text = data.get('auto_generate_text', False) # No longer needed from frontend
    loudness = data.get('loudness')
    quality = data.get('quality')
    seed = data.get('seed')
    guidance_scale = data.get('guidance_scale')
    output_format = data.get('output_format', 'mp3_44100_128')

    if not voice_description:
         return make_api_response(error="Missing required field: voice_description", status_code=400)
    # Add a check for the text field coming from the frontend
    if not text:
         return make_api_response(error="Missing required field: text", status_code=400)

    try:
        # Always call the util with auto_generate_text=False
        previews, generated_text = utils_elevenlabs.create_voice_previews(
            voice_description=voice_description,
            text=text,
            auto_generate_text=False, # Always set to False now
            loudness=loudness,
            quality=quality,
            seed=seed,
            guidance_scale=guidance_scale,
            output_format=output_format
        )
        # generated_text from the util might be different if it *used* to auto-generate,
        # but now we mostly care about the previews based on the input text.
        return make_api_response(data={"previews": previews, "text": text}) # Return the input text
    except ValueError as ve:
        # Catch validation errors from the utility function
        print(f"Validation error creating voice previews: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error creating voice previews: {e}")
        # Determine appropriate status code based on error? (e.g., 422 for validation)
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error creating voice previews: {e}")
        return make_api_response(error="Failed to create voice previews", status_code=500)

@voice_bp.route('/voice-design/save', methods=['POST'])
def save_voice_design_preview():
    """Endpoint to save a selected voice preview to the library."""
    if not request.is_json:
        return make_api_response(error="Request must be JSON", status_code=400)

    data = request.get_json()
    generated_voice_id = data.get('generated_voice_id')
    voice_name = data.get('voice_name')
    voice_description = data.get('voice_description')
    labels = data.get('labels') # Optional

    if not all([generated_voice_id, voice_name, voice_description]):
        missing = [k for k, v in {'generated_voice_id': generated_voice_id, 'voice_name': voice_name, 'voice_description': voice_description}.items() if not v]
        return make_api_response(error=f"Missing required fields: {missing}", status_code=400)
        
    try:
        saved_voice_details = utils_elevenlabs.save_generated_voice(
            generated_voice_id=generated_voice_id,
            voice_name=voice_name,
            voice_description=voice_description,
            labels=labels
        )
        # Maybe map this response to our VoiceOption type before sending?
        # For now, just return the full details.
        return make_api_response(data=saved_voice_details)
    except ValueError as ve:
        print(f"Validation error saving voice: {ve}")
        return make_api_response(error=str(ve), status_code=400)
    except utils_elevenlabs.ElevenLabsError as e:
        print(f"ElevenLabs API error saving voice: {e}")
        status_code = 422 if "validation failed" in str(e).lower() else 500
        return make_api_response(error=str(e), status_code=status_code)
    except Exception as e:
        print(f"Unexpected error saving voice: {e}")
        return make_api_response(error="Failed to save voice", status_code=500) 