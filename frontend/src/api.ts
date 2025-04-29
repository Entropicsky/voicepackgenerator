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
  BatchListInfo,
  // Crop Take Types (assuming simple response for now)
  CropTakePayload,
  CropTakeResponse,
  VoScriptTemplateMetadata, // Import the type here
  VoScriptTemplate, // Import the VoScriptTemplate type
  VoScript, // Import the VoScript type
  VoScriptListItem, // Import VO Script List Item type
  DeleteResponse, // Import Delete Response type
  CreateVoScriptPayload, // Import Create Payload type
  VoScriptLineData, // Import line data type
  SubmitFeedbackPayload, // Import feedback payload type
  RunAgentPayload, // Import agent payload type
  JobSubmissionResponse, // Import agent response type
  // Add new types
  UpdateVoScriptPayload, 
  UpdateVoScriptTemplateCategoryPayload,
  VoScriptCategoryData, // Re-confirming import
  RefineLinePayload, // NEW
  RefineLineResponse, // NEW
  RefineCategoryPayload, // NEW
  RefineMultipleLinesResponse, // NEW
  RefineScriptPayload, // NEW
  AddVoScriptLinePayload, // Ensure this is imported
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

// --- NEW: VO Template/Script Types ---
// Representing the response from GET /api/vo-script-templates
export interface VoScriptTemplateCategory {
  id: number;
  template_id: number;
  name: string;
  prompt_instructions: string | null;
  created_at: string;
  updated_at: string;
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

  // --- Audio Cropping (NEW) --- //
  cropTake: async (batchPrefix: string, filename: string, startTime: number, endTime: number): Promise<CropTakeResponse> => {
    const encodedBatchPrefix = encodeURIComponent(batchPrefix);
    const encodedFilename = encodeURIComponent(filename);
    const url = `${API_BASE}/api/batch/${encodedBatchPrefix}/takes/${encodedFilename}/crop`;
    console.log(`[API cropTake] Cropping ${filename} in ${batchPrefix} from ${startTime} to ${endTime}. URL: ${url}`);
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ startTime, endTime }),
    });
    // Expects { data: { task_id: "...", message: "..." } } or error
    // Return the full response including task_id
    return handleApiResponse<CropTakeResponse>(response);
  },

  // --- NEW: Voice Preview --- 
  // Modified to accept optional settings
  async getVoicePreview(voiceId: string, settings?: { stability?: number, similarity?: number, style?: number, speed?: number }): Promise<Blob> {
    console.log(`[API] Fetching voice preview for: ${voiceId} with settings:`, settings);
    
    // Build query string if settings are provided
    const queryParams = new URLSearchParams();
    if (settings) {
      if (settings.stability !== undefined) queryParams.append('stability', settings.stability.toFixed(2));
      if (settings.similarity !== undefined) queryParams.append('similarity', settings.similarity.toFixed(2)); // Use 'similarity' for query param
      if (settings.style !== undefined) queryParams.append('style', settings.style.toFixed(2));
      if (settings.speed !== undefined) queryParams.append('speed', settings.speed.toFixed(2));
    }
    const queryString = queryParams.toString();
    const url = `${API_BASE}/api/voices/${voiceId}/preview${queryString ? '?' + queryString : ''}`;
    
    console.log(`[API] Requesting preview URL: ${url}`);
    const response = await fetch(url);
    if (!response.ok) {
        // Try to get error message from backend if possible
        let errorMsg = `Failed to fetch preview (status: ${response.status})`;
        try {
            const errorData = await response.json(); // Assuming backend sends JSON error on failure
            errorMsg = errorData.error || errorMsg; 
        } catch (e) {
            // Response was not JSON, use the default message
        }
        console.error(`[API] Error fetching preview for ${voiceId}: ${errorMsg}`);
        throw new Error(errorMsg);
    }
    // Return the audio data as a Blob
    const audioBlob = await response.blob();
    console.log(`[API] Received preview blob for ${voiceId}, size: ${audioBlob.size}`);
    return audioBlob;
  },

  // --- NEW: Endpoint for AI Text Optimization --- //
  optimizeLineText: async (lineText: string): Promise<{ optimized_text: string }> => {
      const url = `${API_BASE}/api/optimize-line-text`;
      console.log(`[API] Optimizing line text: "${lineText.substring(0, 50)}..."`);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({ line_text: lineText }),
      });
      // Expects { data: { optimized_text: "..." } }
      return handleApiResponse<{ optimized_text: string }>(response);
  },

  // --- NEW: VO Script Template API Functions --- //
  listVoScriptTemplates: async (): Promise<VoScriptTemplateMetadata[]> => {
      const url = `${API_BASE}/api/vo-script-templates`;
      console.log("[API] Listing VO Script Templates...");
      const response = await fetch(url);
      return handleApiResponse<VoScriptTemplateMetadata[]>(response);
  },

  createVoScriptTemplate: async (payload: { name: string; description?: string | null; prompt_hint?: string | null; }): Promise<VoScriptTemplateMetadata> => {
      const url = `${API_BASE}/api/vo-script-templates`;
      console.log("[API] Creating VO Script Template:", payload);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      // Backend returns the full created object, cast to Metadata for now
      return handleApiResponse<VoScriptTemplateMetadata>(response); 
  },
  
  getVoScriptTemplate: async (templateId: number): Promise<VoScriptTemplate> => {
    const url = `${API_BASE}/api/vo-script-templates/${templateId}`;
    console.log(`[API] Getting VO Script Template ${templateId}...`);
    const response = await fetch(url);
    // Assuming backend sends full template with nested categories/lines
    return handleApiResponse<VoScriptTemplate>(response); 
  },
  
  updateVoScriptTemplate: async (templateId: number, payload: { name?: string; description?: string | null; prompt_hint?: string | null; }): Promise<VoScriptTemplateMetadata> => {
    const url = `${API_BASE}/api/vo-script-templates/${templateId}`;
    console.log(`[API] Updating VO Script Template ${templateId}:`, payload);
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    return handleApiResponse<VoScriptTemplateMetadata>(response);
  },

  deleteVoScriptTemplate: async (templateId: number): Promise<{ message: string }> => {
      const url = `${API_BASE}/api/vo-script-templates/${templateId}`;
      console.log(`[API] Deleting VO Script Template ${templateId}...`);
      const response = await fetch(url, {
          method: 'DELETE',
      });
      return handleApiResponse<{ message: string }>(response);
  },
  
  // --- NEW: VoScriptTemplateCategory API Functions --- //
  listVoScriptTemplateCategories: async (templateId?: number): Promise<any[]> => {
    const queryParams = new URLSearchParams();
    if (templateId) {
        queryParams.append('template_id', String(templateId));
    }
    const queryString = queryParams.toString();
    const url = `${API_BASE}/api/vo-script-template-categories${queryString ? '?' + queryString : ''}`;
    console.log(`[API] Listing VO Script Template Categories (templateId: ${templateId})...`);
    const response = await fetch(url);
    return handleApiResponse<any[]>(response); // Use specific type later
  },

  createVoScriptTemplateCategory: async (payload: { template_id: number; name: string; prompt_instructions?: string | null; }): Promise<any> => {
      const url = `${API_BASE}/api/vo-script-template-categories`;
      console.log("[API] Creating VO Script Template Category:", payload);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      return handleApiResponse<any>(response);
  },
  
  getVoScriptTemplateCategory: async (categoryId: number): Promise<VoScriptCategoryData> => {
    const url = `${API_BASE}/api/vo-script-template-categories/${categoryId}`;
    console.log(`[API] Getting VO Script Template Category ${categoryId}...`);
    const response = await fetch(url);
    // Returns full category object including refinement_prompt
    return handleApiResponse<VoScriptCategoryData>(response); 
  },

  updateVoScriptTemplateCategory: async (categoryId: number, payload: UpdateVoScriptTemplateCategoryPayload): Promise<VoScriptCategoryData> => {
    const url = `${API_BASE}/api/vo-script-template-categories/${categoryId}`;
    console.log(`[API] Updating VO Script Template Category ${categoryId}:`, payload);
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    // Returns the updated category object
    return handleApiResponse<VoScriptCategoryData>(response);
  },

  deleteVoScriptTemplateCategory: async (categoryId: number): Promise<any> => {
      const url = `${API_BASE}/api/vo-script-template-categories/${categoryId}`;
      console.log(`[API] Deleting VO Script Template Category ${categoryId}...`);
      const response = await fetch(url, {
          method: 'DELETE',
      });
      return handleApiResponse<any>(response);
  },
  // --- END: VoScriptTemplateCategory API Functions --- //

  // --- NEW: VoScriptTemplateLine API Functions --- //
  listVoScriptTemplateLines: async (params?: { templateId?: number; categoryId?: number }): Promise<any[]> => {
    const queryParams = new URLSearchParams();
    if (params?.templateId) {
        queryParams.append('template_id', String(params.templateId));
    }
    if (params?.categoryId) {
        queryParams.append('category_id', String(params.categoryId));
    }
    const queryString = queryParams.toString();
    const url = `${API_BASE}/api/vo-script-template-lines${queryString ? '?' + queryString : ''}`;
    console.log(`[API] Listing VO Script Template Lines (params: ${JSON.stringify(params)})...`);
    const response = await fetch(url);
    return handleApiResponse<any[]>(response); // Use specific type later
  },

  createVoScriptTemplateLine: async (payload: { template_id: number; category_id: number; line_key: string; order_index: number; prompt_hint?: string | null; }): Promise<any> => {
      const url = `${API_BASE}/api/vo-script-template-lines`;
      console.log("[API] Creating VO Script Template Line:", payload);
      const response = await fetch(url, {
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
      });
      return handleApiResponse<any>(response);
  },

  getVoScriptTemplateLine: async (lineId: number): Promise<any> => {
    const url = `${API_BASE}/api/vo-script-template-lines/${lineId}`;
    console.log(`[API] Getting VO Script Template Line ${lineId}...`);
    const response = await fetch(url);
    return handleApiResponse<any>(response);
  },

  updateVoScriptTemplateLine: async (lineId: number, payload: { category_id?: number; line_key?: string; order_index?: number; prompt_hint?: string | null; }): Promise<any> => {
    const url = `${API_BASE}/api/vo-script-template-lines/${lineId}`;
    console.log(`[API] Updating VO Script Template Line ${lineId}:`, payload);
    const response = await fetch(url, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    return handleApiResponse<any>(response);
  },

  deleteVoScriptTemplateLine: async (lineId: number): Promise<any> => {
      const url = `${API_BASE}/api/vo-script-template-lines/${lineId}`;
      console.log(`[API] Deleting VO Script Template Line ${lineId}...`);
      const response = await fetch(url, {
          method: 'DELETE',
      });
      return handleApiResponse<any>(response);
  },
  // --- END: VoScriptTemplateLine API Functions --- //
  
  // --- NEW: VO Script API Functions --- //
  listVoScripts: async (): Promise<VoScriptListItem[]> => {
    const url = `${API_BASE}/api/vo-scripts`;
    console.log("[API] Listing VO Scripts...");
    const response = await fetch(url);
    // Uses the VoScriptListItem type defined in types.ts
    return handleApiResponse<VoScriptListItem[]>(response);
  },

  createVoScript: async (payload: CreateVoScriptPayload): Promise<VoScript> => {
    const url = `${API_BASE}/api/vo-scripts`;
    console.log("[API] Creating VO Script:", payload);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Backend returns the created script object (id, name, template_id, status, etc.)
    return handleApiResponse<VoScript>(response);
  },

  getVoScript: async (scriptId: number): Promise<VoScript> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}`;
    console.log(`[API] Getting VO Script details ${scriptId}...`);
    const response = await fetch(url);
    // Returns the detailed VoScript structure from types.ts (now includes prompts)
    return handleApiResponse<VoScript>(response);
  },

  updateVoScript: async (scriptId: number, payload: UpdateVoScriptPayload): Promise<VoScript> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}`;
    console.log(`[API] Updating VO Script ${scriptId}:`, payload);
    const response = await fetch(url, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Backend now returns the basic updated VoScript object
    return handleApiResponse<VoScript>(response); 
  },

  deleteVoScript: async (scriptId: number): Promise<DeleteResponse> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}`;
    console.log(`[API] Deleting VO Script ${scriptId}...`);
    const response = await fetch(url, {
      method: 'DELETE',
    });
    // Uses the DeleteResponse type
    return handleApiResponse<DeleteResponse>(response);
  },

  submitVoScriptFeedback: async (scriptId: number, payload: SubmitFeedbackPayload): Promise<VoScriptLineData> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/feedback`;
    console.log(`[API] Submitting feedback for script ${scriptId}, line ${payload.line_id}:`, payload.feedback_text);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Returns the updated VoScriptLineData object
    return handleApiResponse<VoScriptLineData>(response);
  },

  runVoScriptAgent: async (scriptId: number, payload: RunAgentPayload): Promise<JobSubmissionResponse> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/run-agent`;
    console.log(`[API] Running agent for script ${scriptId}:`, payload);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Returns { job_id, task_id }
    return handleApiResponse<JobSubmissionResponse>(response);
  },

  // --- NEW VO Script Refinement Functions --- //

  refineVoScriptLine: async (scriptId: number, lineId: number, payload: RefineLinePayload): Promise<RefineLineResponse> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}/refine`;
    console.log(`[API] Refining line ${lineId} for script ${scriptId}:`, payload);
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    // Expects { data: VoScriptLineData }
    return handleApiResponse<RefineLineResponse>(response);
  },

  // NEW: Generate Single Line
  generateVoScriptLine: async (scriptId: number, lineId: number): Promise<VoScriptLineData> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}/generate`;
    console.log(`[API] Generating line ${lineId} for script ${scriptId}...`);
    const response = await fetch(url, {
        method: 'POST',
        // No body needed for basic generation
    });
    // Expects { data: VoScriptLineData }
    return handleApiResponse<VoScriptLineData>(response);
  },
  
  refineVoScriptCategory: async (scriptId: number, payload: RefineCategoryPayload): Promise<RefineMultipleLinesResponse> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/categories/refine`;
    console.log(`[API] Refining category ${payload.category_name} for script ${scriptId}:`, payload);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Expects { message: string, data: VoScriptLineData[] }
    // handleApiResponse extracts the 'data' field, so we might need adjustment
    // Let's modify handleApiResponse or handle the structure here.
    // For now, assume handleApiResponse gives us the inner { message, data } object if wrapped
    // OR use a different handler if response structure is not { data: { message: ..., data: [...] } }
    
    // Assuming backend returns { message: "...", data: [...] } directly (not wrapped in another data key)
    if (!response.ok) {
      let errorMsg = `HTTP error! status: ${response.status}`;
      try {
        const errorBody = await response.json();
        errorMsg = errorBody.error || errorMsg;
      } catch (e) { /* Ignore */ }
      throw new Error(errorMsg);
    }
    // Directly return the JSON response as it matches the expected type
    return response.json(); 
  },

  refineVoScript: async (scriptId: number, payload: RefineScriptPayload): Promise<RefineMultipleLinesResponse> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/refine`;
    console.log(`[API] Refining script ${scriptId}:`, payload);
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    // Assuming backend returns { message: "...", data: [...] } directly
    if (!response.ok) {
      let errorMsg = `HTTP error! status: ${response.status}`;
      try {
        const errorBody = await response.json();
        errorMsg = errorBody.error || errorMsg;
      } catch (e) { /* Ignore */ }
      throw new Error(errorMsg);
    }
    return response.json(); 
  },
  // --- END NEW Refinement Functions --- //

  // --- NEW Line Action Functions --- //
  toggleLockVoScriptLine: async (scriptId: number, lineId: number): Promise<{ id: number; is_locked: boolean; updated_at: string | null; }> => {
      const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}/toggle-lock`;
      console.log(`[API] Toggling lock for line ${lineId}, script ${scriptId}...`);
      const response = await fetch(url, {
          method: 'PATCH',
          headers: {
              'Content-Type': 'application/json',
          },
          // No body needed for toggle
      });
      // Expects { data: { id, is_locked, updated_at } }
      // Use handleApiResponse as it expects a 'data' wrapper
      return handleApiResponse<{ id: number; is_locked: boolean; updated_at: string | null; }>(response);
  },

  updateLineText: async (scriptId: number, lineId: number, newText: string): Promise<VoScriptLineData> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}/update-text`;
    console.log(`[API] Updating text for line ${lineId}, script ${scriptId}...`);
    const response = await fetch(url, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ generated_text: newText }),
    });
    // Expects { data: VoScriptLineData }
    return handleApiResponse<VoScriptLineData>(response);
  },

  deleteVoScriptLine: async (scriptId: number, lineId: number): Promise<{ message: string }> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}`;
    console.log(`[API] Deleting line ${lineId}, script ${scriptId}...`);
    const response = await fetch(url, {
        method: 'DELETE',
    });
    // Expects { message: "..." } - NOT wrapped in data by backend
    if (!response.ok) {
      let errorMsg = `HTTP error! status: ${response.status}`;
      try {
        const errorBody = await response.json();
        errorMsg = errorBody.error || errorMsg;
      } catch (e) { /* Ignore */ }
      throw new Error(errorMsg);
    }
    return response.json(); 
  },

  // NEW Function to add a line
  addVoScriptLine: async (scriptId: number, payload: AddVoScriptLinePayload): Promise<VoScriptLineData> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines`;
    console.log(`[API] Adding line to script ${scriptId}:`, payload);
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    });
    // Expects { data: VoScriptLineData } (for the created line)
    return handleApiResponse<VoScriptLineData>(response);
  },

  // NEW: Accept Line Function
  acceptVoScriptLine: async (scriptId: number, lineId: number): Promise<VoScriptLineData> => {
    const url = `${API_BASE}/api/vo-scripts/${scriptId}/lines/${lineId}/accept`;
    console.log(`[API] Accepting line ${lineId} for script ${scriptId}...`);
    const response = await fetch(url, {
        method: 'PATCH',
        // No body needed
    });
    // Expects { data: VoScriptLineData }
    return handleApiResponse<VoScriptLineData>(response);
  },

};
