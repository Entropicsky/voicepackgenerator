// frontend/src/api.ts
import {
  VoiceOption,
  GenerationConfig,
  GenerationStartResponse,
  TaskStatus,
  BatchMetadata,
  GenerationJob,
  ModelOption,
  SpeechToSpeechPayload,
  Take,
  // NEW: Import Voice Design types
  CreateVoicePreviewPayload,
  CreateVoicePreviewResponse,
  SaveVoicePayload,
  // NEW: Import Script types (define these in types.ts next)
  ScriptMetadata, 
  Script, 
  ScriptLineCreateOrUpdate,
  // Import the RegenerateLinePayload interface from types.ts
  RegenerateLinePayload,
  BatchListInfo
} from './types';

// Define options for filtering/sorting voices
interface GetVoicesOptions {
    search?: string;
    category?: string;
    voice_type?: string;
    sort?: 'name' | 'created_at_unix';
    sort_direction?: 'asc' | 'desc';
    page_size?: number;
    next_page_token?: string;
}

// NEW: Options for getModels
interface GetModelsOptions {
    capability?: 'tts' | 'sts';
}

// NEW: Payload for creating a script
interface CreateScriptPayload {
    name: string;
    description?: string | null;
    csv_content?: string | null; // For importing
}

// NEW: Payload for updating a script
interface UpdateScriptPayload {
    name?: string;
    description?: string | null;
    lines?: ScriptLineCreateOrUpdate[]; // Array of lines to replace existing
}

// Helper to handle API responses and errors
async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMsg = `HTTP error! status: ${response.status}`;
    try {
      const errorBody = await response.json();
      errorMsg = errorBody.error || errorMsg; // Use backend error message if available
    } catch (e) {
      // Ignore if response body is not JSON
    }
    throw new Error(errorMsg);
  }
  const jsonResponse = await response.json();
  // Assuming backend wraps successful responses in a "data" field
  if (jsonResponse && typeof jsonResponse === 'object' && 'data' in jsonResponse) {
       return jsonResponse.data as T;
  } else {
      // Handle cases where backend might not wrap data (adjust as needed)
      console.warn("API response did not have expected 'data' wrapper:", jsonResponse);
      return jsonResponse as T; // Return the raw JSON if no data wrapper
  }
}

const API_BASE = ''; // Using Vite proxy, so relative path works

export const api = {
  // --- Generation & Jobs --- //
  getVoices: async (options?: GetVoicesOptions): Promise<VoiceOption[]> => {
    const queryParams = new URLSearchParams();
    if (options) {
        if (options.search) queryParams.append('search', options.search);
        if (options.category) queryParams.append('category', options.category);
        if (options.voice_type) queryParams.append('voice_type', options.voice_type);
        if (options.sort) queryParams.append('sort', options.sort);
        if (options.sort_direction) queryParams.append('sort_direction', options.sort_direction);
        if (options.page_size) queryParams.append('page_size', String(options.page_size));
        if (options.next_page_token) queryParams.append('next_page_token', options.next_page_token);
    }
    const queryString = queryParams.toString();
    const url = `${API_BASE}/api/voices${queryString ? '?' + queryString : ''}`;
    console.log("Fetching voices from URL:", url); // Debugging

    const response = await fetch(url);
    // V2 returns full voice objects, ensure VoiceOption type matches or adjust mapping
    return handleApiResponse<VoiceOption[]>(response);
  },

  // Updated getModels to accept options
  getModels: async (options?: GetModelsOptions): Promise<ModelOption[]> => {
      const queryParams = new URLSearchParams();
      if (options?.capability) {
          queryParams.append('capability', options.capability);
      }
      const queryString = queryParams.toString();
      const url = `${API_BASE}/api/models${queryString ? '?' + queryString : ''}`; 
      console.log("Fetching models from URL:", url); // Debugging
      const response = await fetch(url);
      return handleApiResponse<ModelOption[]>(response);
  },

  // Returns { task_id, job_id } now
  startGeneration: async (config: GenerationConfig): Promise<GenerationStartResponse> => {
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    return handleApiResponse<GenerationStartResponse>(response);
  },

  // Kept for optional live polling, but DB is primary source
  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const response = await fetch(`${API_BASE}/api/generate/${taskId}/status`);
    // Expects { data: { task_id: "...", status: "...", info: ... } }
    return handleApiResponse<TaskStatus>(response);
  },

  // New endpoint for getting job history
  getJobs: async (): Promise<GenerationJob[]> => {
      const response = await fetch(`${API_BASE}/api/jobs`);
      return handleApiResponse<GenerationJob[]>(response);
  },

  // New endpoint for regenerating line takes
  regenerateLineTakes: async (batchId: string, payload: RegenerateLinePayload): Promise<GenerationStartResponse> => {
      // Encode the batchId (which is the prefix) before inserting into URL
      console.log(`[API regenerateLineTakes] Received batchId: ${batchId}`);
      const encodedBatchId = encodeURIComponent(batchId);
      const url = `${API_BASE}/api/batch/${encodedBatchId}/regenerate_line`;
      console.log(`[API] Regenerating line ${payload.line_key} for prefix ${batchId}, URL: ${url}`);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      // Returns { task_id, job_id }
      return handleApiResponse<GenerationStartResponse>(response);
  },

  // New function for starting STS job
  startSpeechToSpeech: async (batchId: string, payload: SpeechToSpeechPayload): Promise<GenerationStartResponse> => {
      // Encode the batchId (which is the prefix) before inserting into URL
      console.log(`[API startSpeechToSpeech] Received batchId: ${batchId}`);
      const encodedBatchId = encodeURIComponent(batchId);
      const url = `${API_BASE}/api/batch/${encodedBatchId}/speech_to_speech`;
      console.log(`[API] Starting STS for prefix ${batchId}, URL: ${url}`);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      // Returns { task_id, job_id }
      return handleApiResponse<GenerationStartResponse>(response);
  },

  // --- Ranking --- //
  listBatches: async (): Promise<BatchListInfo[]> => {
    const response = await fetch(`${API_BASE}/api/batches`);
    return handleApiResponse<BatchListInfo[]>(response);
  },

  getBatchMetadata: async (batchId: string): Promise<BatchMetadata> => {
    // Encode the batchId (prefix) 
    const encodedBatchId = encodeURIComponent(batchId);
    const response = await fetch(`${API_BASE}/api/batch/${encodedBatchId}`);
    return handleApiResponse<BatchMetadata>(response);
  },

  updateTakeRank: async (batchId: string, filename: string, rank: number | null): Promise<void> => {
    // Encode the batchId (prefix) and filename
    const encodedBatchId = encodeURIComponent(batchId);
    const encodedFilename = encodeURIComponent(filename);
    const response = await fetch(`${API_BASE}/api/batch/${encodedBatchId}/take/${encodedFilename}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ rank }),
    });
    // Expects { data: { status: "...", updated_take: {...} } } or error
    await handleApiResponse<any>(response); 
  },

  // NEW: Endpoint to get takes for a specific line
  getLineTakes: async (batchId: string, lineKey: string): Promise<Take[]> => {
    console.log(`[API Placeholder] Fetching takes for batch ${batchId}, line ${lineKey}`);
    // Temporarily refetch all metadata and filter - replace with dedicated API call
    const metadata = await api.getBatchMetadata(batchId); // Uses the already updated getBatchMetadata
    return metadata.takes.filter(take => take.line === lineKey);
  },

  // --- NEW: Script Management --- //
  listScripts: async (includeArchived: boolean = false): Promise<ScriptMetadata[]> => {
    // **** ADDING DETAILED LOG HERE ****
    console.log(`[API listScripts ENTRY] Received includeArchived =`, includeArchived, `(Type: ${typeof includeArchived})`);
    // --- REVERT DEBUGGING --- 
    // console.log(`[API listScripts] Type of includeArchived param: ${typeof includeArchived}`, includeArchived);
    
    // --- Restore Original URLSearchParams logic --- 
    const queryParams = new URLSearchParams();
    queryParams.append('include_archived', String(includeArchived));
    const queryString = queryParams.toString();
    const url = `${API_BASE}/api/scripts${queryString ? '?' + queryString : ''}`;
    console.log("[API] Listing scripts from URL:", url); // Restore original log
    // --- End Restore --- 

    const response = await fetch(url); 
    return handleApiResponse<ScriptMetadata[]>(response);
  },

  getScriptDetails: async (scriptId: number): Promise<Script> => {
      const url = `${API_BASE}/api/scripts/${scriptId}`;
      console.log(`[API] Getting script details for ID: ${scriptId}`);
      const response = await fetch(url);
      return handleApiResponse<Script>(response);
  },

  createScript: async (payload: CreateScriptPayload): Promise<ScriptMetadata> => {
      const url = `${API_BASE}/api/scripts`;
      console.log("[API] Creating script with payload:", payload);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      // Backend returns { id, name, description, created_at, updated_at, line_count }
      return handleApiResponse<ScriptMetadata>(response);
  },

  updateScript: async (scriptId: number, payload: UpdateScriptPayload): Promise<ScriptMetadata> => {
      const url = `${API_BASE}/api/scripts/${scriptId}`;
      console.log(`[API] Updating script ID ${scriptId} with payload:`, payload);
      const response = await fetch(url, {
          method: 'PUT',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
       // Backend returns { id, name, description, created_at, updated_at }
      return handleApiResponse<ScriptMetadata>(response);
  },

  deleteScript: async (scriptId: number): Promise<{ message: string }> => {
      const url = `${API_BASE}/api/scripts/${scriptId}`;
      console.log(`[API] Deleting script ID: ${scriptId}`);
      const response = await fetch(url, {
          method: 'DELETE',
      });
      // Backend returns { message: "..." }
      return handleApiResponse<{ message: string }>(response);
  },
  // --- End Script Management --- //

  // --- NEW: Voice Design --- //
  createVoicePreviews: async (payload: CreateVoicePreviewPayload): Promise<CreateVoicePreviewResponse> => {
    const url = `${API_BASE}/api/voice-design/previews`;
    console.log("[API] Creating voice previews with payload:", payload);
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    // Expects { data: { previews: [...], text: "..." } }
    return handleApiResponse<CreateVoicePreviewResponse>(response); 
  },
  
  saveVoiceFromPreview: async (payload: SaveVoicePayload): Promise<VoiceOption> => {
      const url = `${API_BASE}/api/voice-design/save`;
      console.log("[API] Saving voice from preview with payload:", payload);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      // Backend returns the full saved voice details. 
      // We'll map it to VoiceOption for consistency with the rest of the UI for now.
      // Might need a more detailed type later if more fields are needed.
      const fullVoiceDetails = await handleApiResponse<any>(response);
      console.log("[API] Received saved voice details:", fullVoiceDetails);
      // Map the relevant fields to VoiceOption
      return {
          voice_id: fullVoiceDetails.voice_id,
          name: fullVoiceDetails.name,
          category: fullVoiceDetails.category, // Add other fields if needed/available
          labels: fullVoiceDetails.labels 
      };
  },

  // --- Audio --- //
  getAudioUrl: (relpath: string): string => {
    // Construct the URL for the audio endpoint
    // Ensure relpath doesn't start with / if API_BASE is involved
    const cleanRelPath = relpath.startsWith('/') ? relpath.substring(1) : relpath;
    return `${API_BASE}/audio/${cleanRelPath}`;
  },

  // NEW: Toggle Archive Status
  toggleScriptArchive: async (scriptId: number, archive: boolean): Promise<ScriptMetadata> => {
    const url = `${API_BASE}/api/scripts/${scriptId}/archive`;
    const response = await fetch(url, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ archive }),
    });
    return handleApiResponse<ScriptMetadata>(response);
  },
}; 