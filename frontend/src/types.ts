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
}

// ... BatchInfo, Take, BatchMetadata ...

// Ensure TaskStatus is exported
export interface TaskStatus {
  task_id: string;
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED' | 'FETCH_ERROR' | string; // Added FETCH_ERROR
  info: any;
}

export interface GenerationConfig {
  skin_name: string;
  voice_ids: string[];
  script_csv_content: string;
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