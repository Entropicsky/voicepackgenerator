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
  taskId: string; // Celery Task ID
  jobId: number;  // Database Job ID
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
  taskId: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED' | 'FETCH_ERROR' | 'PROGRESS' | string; // Added PROGRESS
  info?: { // Made info optional and more specific
    status_message?: string; // For PROGRESS state
    error?: string; // For FAILURE state
    message?: string; // General message, sometimes used by backend for failure
    // For SUCCESS, info will be ChatTaskResult, but we cast it later
    // For other states, it might be other structured data or simple messages
    [key: string]: any; // Allow other arbitrary keys from Celery meta
  } | ChatTaskResult | null; // Allow ChatTaskResult for SUCCESS, or null
}

// This interface defines the config received from the /api/generate endpoint
// AND the settings used for regeneration (potentially subset via Partial)
export interface GenerationConfig {
  skin_name: string;
  voice_ids: string[];
  vo_script_id: number;
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
    settings: GenerationSettings; // Re-use generation settings type
    replace_existing: boolean;
    update_script?: boolean; // Optional: Update script DB
}

// Response from starting any async job (generate, regenerate, STS)
export interface JobSubmissionResponse {
  taskId: string | null; // USE camelCase to match frontend convention
  jobId: number;        // USE camelCase to match frontend convention
}

// Represents detailed batch info from the LIST endpoint /api/batches
// This is now based on GenerationJob results and R2 prefix structure
export interface BatchListInfo {
  batch_prefix: string; // The full R2 prefix (e.g., skin/voice/batch-id)
  skin_name: string;
  voice_name: string; // The voice folder name (e.g., VoiceName-voiceID)
  id: string; // The original batch ID part (e.g., 20250420-025342-AYEw)
  generated_at_utc: string | null; // Not currently available from list endpoint
  // Add placeholder sort key if needed by the table, or remove columns
  created_at_sortkey?: number; 
}

// Remove or comment out the old BatchDetailInfo if no longer used
// export interface BatchDetailInfo {
//   batch_id: string;
//   skin: string;
//   voice: string;
//   num_lines: number;
//   takes_per_line: number; 
//   num_takes: number; 
//   created_at: string | null; 
//   created_at_sortkey: number; 
//   status: 'Locked' | 'Unlocked';
// }

// ... Take, BatchMetadata ...

// Add back missing definitions
// Define GenerationSettings type first
export interface GenerationSettings {
  stability?: number | null;
  similarity_boost?: number | null;
  style?: number | null;
  speed?: number | null;
  use_speaker_boost?: boolean | null;
}

export interface Take {
  file: string;
  line: string;
  take_number: number;
  script_text: string | null;
  rank: number | null;
  ranked_at: string | null; // ISO string timestamp
  // Add generation_settings
  generation_settings?: GenerationSettings | null;
  r2_key?: string; // Add r2_key if it exists in metadata
}

export interface BatchMetadata {
  batch_id: string;
  batch_prefix?: string;
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
    source_audio_data: string; // Base64 encoded audio data URI
    num_new_takes: number;
    target_voice_id: string;
    model_id: string;
    settings: StsSettings; // Specific settings for STS
    replace_existing: boolean;
}

export interface StsSettings {
    stability?: number | null;
    similarity_boost?: number | null;
}

// --- NEW: Audio Cropping Types --- //
// Payload sent from frontend
export interface CropTakePayload {
    startTime: number; // seconds
    endTime: number;   // seconds
}

// Response received from backend (includes Celery task ID)
export interface CropTakeResponse {
    taskId: string;
    message: string;
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
    // NEW: Add state for AI Wizard per line
    isOptimizing?: boolean;
    optimizeError?: string | null;
}

// --- END Script Management Types ---

// --- NEW: VO Template/Script Types ---
// Representing the response from GET /api/vo-script-templates
export interface VoScriptTemplateMetadata {
  id: number;
  name: string;
  description: string | null;
  prompt_hint: string | null; 
}

// Add more specific types for Category, Line, VO Script as needed
export interface VoScriptTemplateCategory {
  id: number;
  template_id: number;
  name: string;
  prompt_instructions: string | null;
  refinement_prompt: string | null;
  created_at: string;
  updated_at: string;
  // is_deleted: boolean; // Add if needed by frontend logic
}

export interface VoScriptTemplateLine {
  id: number;
  template_id: number;
  category_id?: number | null;
  line_key: string;
  order_index: number;
  prompt_hint?: string | null;
  static_text?: string | null; // Added based on backend model
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  // category?: VoScriptTemplateCategory; // If it has nested category object
}

// Represents a full VO Script Template including categories and lines
// This is the expected return type for GET /api/vo-script-templates/:id
export interface VoScriptTemplate extends VoScriptTemplateMetadata {
   created_at: string;
   updated_at: string;
   categories: VoScriptTemplateCategory[]; // Array of associated categories
   template_lines: VoScriptTemplateLine[]; // Array of associated lines
}

export interface VoScript {
  id: number;
  template_id: number;
  name: string;
  character_description: string;
  refinement_prompt: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  template_name?: string;
  template_description?: string;
  template_prompt_hint?: string;
  categories?: VoScriptCategoryData[];
}

// --- Payload Type for Creating VO Script --- //
export interface CreateVoScriptPayload {
    name: string;
    template_id: number;
    character_description: string;
}

// Represents a generated line linked to a template line
export interface VoScriptLineData {
  id: number;
  template_line_id?: number;
  category_id?: number; 
  line_key?: string;
  generated_text: string | null;
  status: string;
  latest_feedback: string | null;
  generation_history?: any[]; 
  order_index?: number;
  template_prompt_hint?: string; 
  is_locked?: boolean; 
  created_at?: string | null; // Add created_at
  updated_at?: string | null; // Add updated_at
}

// Represents a category containing lines for the detail view
export interface VoScriptCategoryData {
    id: number | null; // Added ID (nullable if uncategorized)
    name: string;
    instructions: string | null;
    refinement_prompt: string | null; // Added
    lines: VoScriptLineData[];
}

// Payload for submitting feedback
export interface SubmitFeedbackPayload {
    line_id: number;
    feedback_text: string;
}

// Payload for running the agent task
export interface RunAgentPayload {
    task_type: 'generate_draft' | 'refine_feedback' | 'refine_category';
    feedback?: any; // Type depends on task
    category_name?: string;
}

// Response from agent task submission
export interface JobSubmissionResponse {
  jobId: number;
  taskId: string | null; // Celery Task ID (can be null if submit fails)
}

// Added: Type for the items returned by GET /api/vo-scripts list endpoint
export interface VoScriptListItem {
  id: number;
  name: string;
  template_id: number;
  template_name: string | null;
  status: string;
  character_description?: string;
  created_at: string;
  updated_at: string;
}

// Added: Expected response type for DELETE operations
export interface DeleteResponse {
    message: string;
}

// --- END VO Template/Script Types ---

// --- Payload Types --- //

// Payload for updating a VO Script
export interface UpdateVoScriptPayload {
    name?: string;
    character_description?: string;
    status?: string;
    refinement_prompt?: string | null;
}

// Payload for updating a VO Script Template Category
export interface UpdateVoScriptTemplateCategoryPayload {
    name?: string;
    prompt_instructions?: string | null;
    refinement_prompt?: string | null;
}

// --- NEW Types for Refinement API Calls --- //

// Payload for refining a single line
export interface RefineLinePayload {
  line_prompt: string;
  model?: string; // Optional model override
  apply_best_practices?: boolean; // NEW
}

// Response for single line refinement (returns the updated line)
export interface RefineLineResponse extends VoScriptLineData {}

// Payload for refining a category
export interface RefineCategoryPayload {
  category_name: string;
  category_prompt: string;
  // line_prompts?: Record<number, string>; // Optional: { lineId: promptText }
  model?: string; // Optional model override
  apply_best_practices?: boolean; // NEW
}

// Response for category/script refinement (returns list of updated lines)
export interface RefineMultipleLinesResponse {
  message: string; // e.g., "Category refinement completed successfully."
  data: VoScriptLineData[]; // List of lines that were updated
}

// Payload for refining the whole script
export interface RefineScriptPayload {
  global_prompt: string;
  // category_prompts?: Record<string, string>; // Optional: { categoryName: promptText }
  // line_prompts?: Record<number, string>; // Optional: { lineId: promptText }
  model?: string; // Optional model override
  apply_best_practices?: boolean; // NEW
}

// --- END NEW Types --- //

// NEW: Add AddVoScriptLinePayload here
export interface AddVoScriptLinePayload {
  line_key: string;
  category_name: string;
  order_index: number;
  initial_text?: string | null;
  prompt_hint?: string | null;
}

// --- NEW TYPES FOR CHAT FEATURE ---
export interface ChatMessageContext {
    role: 'user' | 'assistant';
    content: string;
}

export interface ChatRequestContext { 
    category_id?: number | null;
    line_id?: number | null;
}

export interface InitiateChatPayload {
    user_message: string;
    initial_prompt_context_from_prior_sessions?: ChatMessageContext[];
    current_context?: ChatRequestContext;
}

export interface InitiateChatResponseData { // What the backend {data: HERE} contains
    task_id: string;
}

// --- NEW OR UPDATED TYPES FOR CHAT PROPOSAL HANDLING ---

// Matches the backend Enum for modification types
export enum ModificationType {
    REPLACE_LINE = "REPLACE_LINE",
    INSERT_LINE_AFTER = "INSERT_LINE_AFTER",
    INSERT_LINE_BEFORE = "INSERT_LINE_BEFORE",
    NEW_LINE_IN_CATEGORY = "NEW_LINE_IN_CATEGORY",
}

export interface ProposedModificationDetail {
    proposal_id: string; 
    script_id: number;
    modification_type: ModificationType;
    target_id: number; 
    new_text?: string | null;
    character_id?: number | null;
    metadata_notes?: string | null;
    reasoning?: string | null;
    suggested_line_key?: string | null;
    suggested_order_index?: number | null;
}

// --- ADDED Type for Staged Description Update --- //
export interface StagedCharacterDescriptionData {
    script_id: number;
    new_description: string;
    reasoning?: string | null;
}

// Update existing ChatTaskResult
export interface ChatTaskResult { // The 'info' field of a successful chat task
    ai_response_text: string;
    proposed_modifications: ProposedModificationDetail[];
    scratchpad_updates: any[];   
    staged_description_update?: StagedCharacterDescriptionData | null; // ADDED optional field
}

// ChatTaskStatusData already uses ChatTaskResult, so it will benefit from this update.

// --- ADDED Type for Chat History Items ---
export interface ChatHistoryItem {
    role: string;
    content: string;
    timestamp: string; // Use string for ISO date format from backend
}

// --- END NEW TYPES FOR CHAT FEATURE ---