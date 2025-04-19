// frontend/src/types.ts

// Represents a voice option from the backend (reflecting V2 API structure)
export interface VoiceOption {
  voice_id: string; // Renamed from id for consistency with API
  name: string;
  category?: 'premade' | 'cloned' | 'generated' | 'professional' | string; // Allow other potential strings
  labels?: Record<string, string>; // e.g., { "accent": "American", "gender": "female" }
  // Add other potentially useful fields from V2 response if needed later:
  description?: string;
  // is_owner?: boolean; // If API provides this
  // created_at_unix?: number; // If API provides this
}

// Represents a TTS model option
export interface ModelOption {
  model_id: string;
  name: string;
}

// ... other types (GenerationConfig, TaskStatus, etc.) ... 

// UPDATED: Response from starting generation now includes DB job ID
export interface GenerationStartResponse {
  task_id: string; // Celery Task ID
  job_id: number;  // Database Job ID
}

// ... TaskStatus (can be kept for live polling if desired, but DB is primary source now) ...

// NEW: Represents a job fetched from the /api/jobs endpoint
export interface GenerationJob {
    id: number;
    celery_task_id: string | null;
    status: string; // PENDING, STARTED, SUCCESS, FAILURE, SUBMIT_FAILED
    submitted_at: string | null;
    started_at: string | null;
    completed_at: string | null;
    parameters_json: string | null; // JSON string of GenerationConfig
    result_message: string | null;
    result_batch_ids_json: string | null; // JSON string array of batch IDs
    job_type?: 'full_batch' | 'line_regen' | string; // Allow string for flexibility
    target_batch_id?: string | null;
    target_line_key?: string | null;
}

// ... BatchInfo, Take, BatchMetadata ...

// Ensure TaskStatus is exported
export interface TaskStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED' | 'FETCH_ERROR' | string; // Added FETCH_ERROR
  info: any;
}

// This interface defines the config received from the /api/generate endpoint
// AND the settings used for regeneration (potentially subset via Partial)
export interface GenerationConfig {
  skin_name: string;
  voice_ids: string[];
  script_csv_content?: string; // Make CSV optional
  script_id?: number; // Add optional script ID
  variants_per_line: number;
  model_id?: string;
  // Use RANGES for randomization settings
  stability_range?: [number, number]; // [min, max]
  similarity_boost_range?: [number, number]; // [min, max]
  style_range?: [number, number]; // [min, max] (Style Exaggeration)
  speed_range?: [number, number]; // [min, max]
  // Keep speaker boost as a single boolean
  use_speaker_boost?: boolean;
}

// Type for the payload sent when regenerating a line
// Uses Partial<GenerationConfig> to send only relevant range settings
export interface RegenerateLinePayload {
    line_key: string;
    line_text: string;
    num_new_takes: number;
    settings: Partial<GenerationConfig>; // Send relevant ranges
    replace_existing: boolean;
    update_script?: boolean;
}

// Response from starting any async job (generate, regenerate, STS)
export interface JobSubmissionResponse {
  task_id: string | null; // Celery Task ID (can be null if submit fails)
  job_id: number;        // Database Job ID
}

// Represents detailed batch info from the enhanced /api/batches endpoint
export interface BatchDetailInfo {
  batch_id: string;
  skin: string;
  voice: string;
  num_lines: number;
  takes_per_line: number; // Max/Configured takes per line
  num_takes: number; // Total actual takes found in metadata
  created_at: string | null; // ISO string
  created_at_sortkey: number; // Timestamp for sorting
  status: 'Locked' | 'Unlocked';
}

// Remove old BatchInfo if it exists
// export interface BatchInfo { ... }

// ... Take, BatchMetadata ...

// Add back missing definitions
export interface Take {
  file: string;
  line: string;
  take_number: number;
  script_text: string | null;
  rank: number | null;
  ranked_at: string | null; // ISO string timestamp
  // Add other fields if needed based on metadata.json structure
}

export interface BatchMetadata {
  batch_id: string;
  skin_name: string;
  voice_name: string;
  generated_at_utc: string; // ISO string timestamp
  ranked_at_utc: string | null; // ISO string timestamp or null
  takes: Take[];
  // Include generation_params if needed
  generation_params?: any; // Use a more specific type if available
}

// Payload for STS request
export interface SpeechToSpeechPayload {
    line_key: string;
    source_audio_b64: string; // data:audio/...;base64,... string
    num_new_takes: number;
    target_voice_id: string;
    model_id: string;
    settings: { // Specific STS settings
        stability?: number;
        similarity_boost?: number;
    };
    replace_existing: boolean;
}

// --- NEW: Voice Design Types --- //

// Payload for creating voice previews
export interface CreateVoicePreviewPayload {
  voice_description: string; // Required (20-1000 chars)
  text?: string; // Optional (100-1000 chars) - required if auto_generate_text is false
  auto_generate_text?: boolean; // Optional (defaults to false)
  loudness?: number; // Optional (-1 to 1)
  quality?: number; // Optional (-1 to 1)
  seed?: number; // Optional (integer >= 0)
  guidance_scale?: number; // Optional (0-100)
  output_format?: string; // Optional (defaults mp3_44100_128)
}

// Structure of a single preview returned by the API
export interface VoicePreview {
  audio_base_64: string;
  generated_voice_id: string;
  media_type?: string; // e.g., "audio/mpeg"
  duration_secs?: number;
  // Add other fields if the API returns more useful info
}

// NEW: Extended preview type to include the description that generated it
export interface RichVoicePreview extends VoicePreview {
  originalDescription: string;
}

// Response structure from the create previews endpoint
export interface CreateVoicePreviewResponse {
  previews: VoicePreview[];
  text: string; // The text used for generation (either provided or auto-generated)
}

// Payload for saving a selected voice preview
export interface SaveVoicePayload {
  generated_voice_id: string; // Required
  voice_name: string; // Required
  voice_description: string; // Required (20-1000 chars)
  labels?: Record<string, string>; // Optional
}

// NOTE: The response from saving a voice (`/api/voice-design/save`)
// returns the full ElevenLabs voice object structure.
// We can either create a detailed interface for this (`DesignedVoiceDetail`?)
// or potentially map the necessary fields (like `voice_id`, `name`) 
// to our existing `VoiceOption` type if sufficient.
// For now, the `api.saveVoiceFromPreview` function can return `VoiceOption` or `any`.

// --- Script Management Types ---

export interface ScriptLine {
  id: number;
  script_id: number;
  line_key: string;
  text: string;
  order_index: number;
}

// Represents a Script with its lines included
export interface Script {
  id: number;
  name: string;
  description: string | null;
  created_at: string; // ISO 8601 format
  updated_at: string; // ISO 8601 format
  lines: ScriptLine[];
}

// Represents the metadata returned by listScripts or after create/update
export interface ScriptMetadata {
  id: number;
  name: string;
  description: string | null;
  line_count: number;
  is_archived: boolean;
  created_at: string; // ISO 8601 format
  updated_at: string; // ISO 8601 format
}

// Type for creating/updating lines via PUT /api/scripts/:id
// Note: Does not include `id` or `script_id` as these are implicit or handled by backend
export interface ScriptLineCreateOrUpdate {
    line_key: string;
    text: string;
    order_index: number;
}

// --- END Script Management Types ---