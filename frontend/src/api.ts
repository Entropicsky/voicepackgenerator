// frontend/src/api.ts
import axios, { AxiosResponse } from 'axios';
import {
    VoiceOption, ModelOption, GenerationJob,
    Script, ScriptLine, VoScriptTemplate, VoScriptTemplateCategory, SubmitFeedbackPayload,
    VoScript, VoScriptLineData, RunAgentPayload, UpdateVoScriptPayload, RefineLinePayload,
    RefineLineResponse, UpdateVoScriptTemplateCategoryPayload, RefineCategoryPayload,
    RefineMultipleLinesResponse, RefineScriptPayload, DeleteResponse, AddVoScriptLinePayload,
    JobSubmissionResponse,
    VoScriptTemplateLine
} from './types'; // Ensure all necessary types are imported

// Define these types if they don't exist in types.ts
interface GetVoicesOptions {
    [key: string]: any;
}

interface GetModelsOptions {
    [key: string]: any;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''; // Fallback to relative path

// Create an Axios instance for API calls
const apiClient = axios.create({
  baseURL: API_BASE + '/api',
  timeout: 90000, // Increased timeout (90 seconds) for longer operations like refinement
  headers: {
    'Content-Type': 'application/json',
  }
});

// --- API Response Handler --- //
// Generic handler to extract data from successful responses or throw structured errors
const handleApiResponse = <T,>(response: AxiosResponse<{ data: T } | { error: string } | T>): T => {
    if (response.status >= 200 && response.status < 300) {
        // Check if response.data exists and is an object
        if (response.data && typeof response.data === 'object') {
            // If backend consistently wraps success in { data: T }
            if ('data' in response.data) {
                return (response.data as { data: T }).data;
            }
            // If backend might return T directly on success (e.g., simple messages)
            // We assume if it's not wrapped in 'data', the data *is* T
            // This requires careful backend consistency or more specific handlers per endpoint
            // console.warn('API success response missing expected \'data\' field, returning raw data:', response.data);
            return response.data as T;
        } else {
            // Handle cases like empty responses (e.g., 204 No Content) or non-object data
            return response.data as T; // Return whatever was received
        }
    } else {
        // This case might not be reached if axios throws for non-2xx status codes by default
        // Handle based on Axios error handling if needed
        const errorData = response.data as { error: string };
        throw new Error(errorData?.error || `Request failed with status ${response.status}`);
    }
};

// --- Specific API Function Definitions --- //

// Voices
const getVoices = async (options?: GetVoicesOptions): Promise<VoiceOption[]> => {
    const response = await apiClient.get<{ data: VoiceOption[] }>('/voices', { params: options });
    return handleApiResponse(response);
};

// Models
const getModels = async (options?: GetModelsOptions): Promise<ModelOption[]> => {
    const response = await apiClient.get<{ data: ModelOption[] }>('/models', { params: options });
    return handleApiResponse(response);
};

// Generation Jobs
const listGenerationJobs = async (): Promise<GenerationJob[]> => {
    const response = await apiClient.get<{ data: GenerationJob[] }>('/jobs');
    return handleApiResponse(response);
};

const getGenerationJob = async (jobId: number): Promise<GenerationJob> => {
    const response = await apiClient.get<{ data: GenerationJob }>(`/jobs/${jobId}`);
    return handleApiResponse(response);
};

// Generic Scripts (Legacy?)
const getScript = async (scriptId: number): Promise<Script> => {
    const response = await apiClient.get<{ data: Script }>(`/scripts/${scriptId}`);
    return handleApiResponse(response);
};

const submitScriptFeedback = async (scriptId: number, feedback: Record<string, string>): Promise<any> => {
    const response = await apiClient.post(`/scripts/${scriptId}/feedback`, feedback);
    return handleApiResponse(response);
};

const runScriptAgent = async (scriptId: number, taskType: string, feedbackData?: any): Promise<JobSubmissionResponse> => {
    const response = await apiClient.post<{ data: JobSubmissionResponse }>(`/scripts/${scriptId}/run-agent`, { task_type: taskType, feedback: feedbackData });
    return handleApiResponse(response);
};

const createScript = async (name: string, characterDescription: string, prompt: string): Promise<Script> => {
    const response = await apiClient.post<{ data: Script }>('/scripts', { name, character_description: characterDescription, prompt });
    return handleApiResponse(response);
};

const deleteScript = async (scriptId: number): Promise<any> => {
    const response = await apiClient.delete(`/scripts/${scriptId}`);
    return handleApiResponse(response);
};

// Add missing listScripts function
// Define necessary types inline if not in types.ts
interface ScriptMetadata { // TODO: Replace with more specific type if available
    id: number;
    name: string;
    description?: string;
    is_archived: boolean;
    created_at: string;
    updated_at: string;
    line_count?: number; // May not be present in all contexts
}
const listScripts = async (includeArchived: boolean = false): Promise<ScriptMetadata[]> => {
    const response = await apiClient.get<{ data: ScriptMetadata[] }>('/scripts', { params: { include_archived: includeArchived } });
    return handleApiResponse(response);
};

// Add missing updateScript function
// Define necessary types inline if not in types.ts
interface UpdateScriptPayload { 
    name?: string;
    description?: string;
    // Add other potential fields based on legacy script structure
}
const updateScript = async (scriptId: number, payload: UpdateScriptPayload): Promise<ScriptMetadata> => {
    const response = await apiClient.put<{ data: ScriptMetadata }>(`/scripts/${scriptId}`, payload);
    return handleApiResponse(response);
};

// --- VO Script Template Functions --- //
const fetchVoScriptTemplates = async (): Promise<VoScriptTemplate[]> => {
  const response = await apiClient.get<{ data: VoScriptTemplate[] }>('/vo-script-templates');
  return handleApiResponse(response);
};

// Alias for fetchVoScriptTemplates - for backward compatibility
const listVoScriptTemplates = fetchVoScriptTemplates;

const getVoScriptTemplate = async (templateId: number): Promise<VoScriptTemplate> => {
    const response = await apiClient.get<{ data: VoScriptTemplate }>(`/vo-script-templates/${templateId}`);
    return handleApiResponse(response);
};

const createVoScriptTemplate = async (payload: { name: string; description?: string; prompt_hint?: string }): Promise<VoScriptTemplate> => {
    const response = await apiClient.post<{ data: VoScriptTemplate }>('/vo-script-templates', payload);
    return handleApiResponse(response);
};

const deleteVoScriptTemplate = async (templateId: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ data: { message: string } }>(`/vo-script-templates/${templateId}`);
    return handleApiResponse(response);
};

// Add the missing update template function
const updateVoScriptTemplate = async (templateId: number, payload: { name?: string; description?: string | null; prompt_hint?: string | null; }): Promise<VoScriptTemplate> => {
    const response = await apiClient.put<{ data: VoScriptTemplate }>(`/vo-script-templates/${templateId}`, payload);
    return handleApiResponse(response);
};

// Add the missing function
const updateVoScriptTemplateLine = async (lineId: number, payload: any): Promise<any> => { // TODO: Replace 'any' with specific VoScriptTemplateLine type if available
    const response = await apiClient.put<{ data: any }>(`/vo-script-template-lines/${lineId}`, payload); // Assuming PUT /api/vo-script-template-lines/<line_id>
    return handleApiResponse(response);
};

// Add missing Category and Line CRUD functions
const createVoScriptTemplateCategory = async (payload: { template_id: number; name: string; prompt_instructions?: string | null; }): Promise<any> => { // TODO: Define Category type
    const response = await apiClient.post<{ data: any }>(`/vo-script-template-categories`, payload);
    return handleApiResponse(response);
};

const updateVoScriptTemplateCategory = async (categoryId: number, payload: { name?: string; prompt_instructions?: string | null; }): Promise<any> => { // TODO: Define Category type
    const response = await apiClient.put<{ data: any }>(`/vo-script-template-categories/${categoryId}`, payload);
    return handleApiResponse(response);
};

const deleteVoScriptTemplateCategory = async (categoryId: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ data: { message: string } }>(`/vo-script-template-categories/${categoryId}`);
    return handleApiResponse(response);
};

const createVoScriptTemplateLine = async (payload: { template_id: number; category_id: number; line_key: string; order_index: number; prompt_hint?: string | null; static_text?: string | null }): Promise<any> => { // TODO: Define Line type
    const response = await apiClient.post<{ data: any }>(`/vo-script-template-lines`, payload);
    return handleApiResponse(response);
};

const deleteVoScriptTemplateLine = async (lineId: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ data: { message: string } }>(`/vo-script-template-lines/${lineId}`);
    return handleApiResponse(response);
};

// --- VO Script Functions --- //
const createVoScript = async (payload: { name: string; template_id: number; character_description: string }): Promise<VoScript> => {
  const response = await apiClient.post<{ data: VoScript }>('/vo-scripts', payload);
  return handleApiResponse(response);
};

const listVoScripts = async (): Promise<VoScript[]> => {
  const response = await apiClient.get<{ data: VoScript[] }>('/vo-scripts');
  return handleApiResponse(response);
};

const getVoScript = async (scriptId: number): Promise<VoScript> => {
    const response = await apiClient.get<{ data: VoScript }>(`/vo-scripts/${scriptId}`);
    return handleApiResponse(response);
};

const updateVoScript = async (scriptId: number, payload: UpdateVoScriptPayload): Promise<VoScript> => {
    const response = await apiClient.put<{ data: VoScript }>(`/vo-scripts/${scriptId}`, payload);
    return handleApiResponse(response);
};

const deleteVoScript = async (scriptId: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ data: { message: string } }>(`/vo-scripts/${scriptId}`);
    return handleApiResponse(response);
};

// --- VO Script Actions --- //
const runVoScriptAgentAction = async (scriptId: number, payload: RunAgentPayload): Promise<JobSubmissionResponse> => {
  // Renamed to avoid conflict with legacy runScriptAgent
  const response = await apiClient.post<{ data: JobSubmissionResponse }>(`/vo-scripts/${scriptId}/run-agent`, payload);
  return handleApiResponse(response);
};

const submitVoScriptFeedback = async (scriptId: number, payload: SubmitFeedbackPayload): Promise<VoScriptLineData> => {
  const response = await apiClient.post<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/feedback`, payload);
  return handleApiResponse(response);
};

const refineVoScriptLine = async (scriptId: number, lineId: number, payload: RefineLinePayload): Promise<VoScriptLineData> => {
  const response = await apiClient.post<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/lines/${lineId}/refine`, payload);
  return handleApiResponse(response);
};

const refineVoScriptCategory = async (scriptId: number, payload: RefineCategoryPayload): Promise<RefineMultipleLinesResponse> => {
    const response = await apiClient.post<{ data: RefineMultipleLinesResponse }>(`/vo-scripts/${scriptId}/categories/refine`, payload);
    return handleApiResponse(response);
};

const refineVoScript = async (scriptId: number, payload: RefineScriptPayload): Promise<RefineMultipleLinesResponse> => {
    const response = await apiClient.post<{ data: RefineMultipleLinesResponse }>(`/vo-scripts/${scriptId}/refine`, payload);
    return handleApiResponse(response);
};

const toggleLockVoScriptLine = async (scriptId: number, lineId: number): Promise<{ id: number; is_locked: boolean; updated_at: string | null; }> => {
    const response = await apiClient.patch<{ data: { id: number; is_locked: boolean; updated_at: string | null; } }>(`/vo-scripts/${scriptId}/lines/${lineId}/toggle-lock`);
    return handleApiResponse(response);
};

const updateLineText = async (scriptId: number, lineId: number, newText: string): Promise<VoScriptLineData> => {
    const response = await apiClient.patch<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/lines/${lineId}/update-text`, { generated_text: newText });
    return handleApiResponse(response);
};

const deleteVoScriptLine = async (scriptId: number, lineId: number): Promise<DeleteResponse> => {
    const response = await apiClient.delete<{ data: DeleteResponse }>(`/vo-scripts/${scriptId}/lines/${lineId}`);
    return handleApiResponse(response);
};

const addVoScriptLine = async (scriptId: number, payload: AddVoScriptLinePayload): Promise<VoScriptLineData> => {
    const response = await apiClient.post<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/lines`, payload);
    return handleApiResponse(response);
};

const generateVoScriptLine = async (scriptId: number, lineId: number): Promise<VoScriptLineData> => {
    const response = await apiClient.post<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/lines/${lineId}/generate`);
    return handleApiResponse(response);
};

const acceptVoScriptLine = async (scriptId: number, lineId: number): Promise<VoScriptLineData> => {
    const response = await apiClient.patch<{ data: VoScriptLineData }>(`/vo-scripts/${scriptId}/lines/${lineId}/accept`);
    return handleApiResponse(response);
};

const instantiateTargetLines = async (scriptId: number, payload: any): Promise<{ message: string, lines_added_count: number }> => {
    const response = await apiClient.post<{ data: { message: string, lines_added_count: number } }>(`/vo-scripts/${scriptId}/instantiate-lines`, payload);
    return handleApiResponse(response);
};

// Add generateCategoryBatch function
const generateCategoryBatch = async (scriptId: number, categoryName: string, model?: string): Promise<RefineMultipleLinesResponse> => {
    const payload = model ? { model } : {};
    const response = await apiClient.post<{ data: RefineMultipleLinesResponse }>(
        `/vo-scripts/${scriptId}/categories/${encodeURIComponent(categoryName)}/generate-batch-task`, 
        payload
    );
    return handleApiResponse(response);
};

// --- Voice Design --- //
// Define necessary types inline if not in types.ts
interface CreateVoicePreviewPayload { 
    text: string; 
    voice_id?: string; 
    voice_settings?: object; 
    generation_config?: object; 
}
interface CreateVoicePreviewResponse { previews: any[], text: string } // TODO: Define specific preview type

const createVoicePreviews = async (payload: CreateVoicePreviewPayload): Promise<CreateVoicePreviewResponse> => {
    const response = await apiClient.post<{ data: CreateVoicePreviewResponse }>('/voice-design/previews', payload);
    return handleApiResponse(response);
};

interface SaveVoicePayload { 
    preview_id: string; // Assuming preview ID is used to link to saved settings/audio
    name: string;
    description?: string;
    labels?: { [key: string]: string };
}

const saveVoiceFromPreview = async (payload: SaveVoicePayload): Promise<VoiceOption> => {
    const response = await apiClient.post<{ data: any }>('/voice-design/save', payload);
    // Assuming backend returns full voice details, map to VoiceOption
    const fullVoiceDetails = handleApiResponse<any>(response); 
     return {
          voice_id: fullVoiceDetails.voice_id,
          name: fullVoiceDetails.name,
          category: fullVoiceDetails.category,
          labels: fullVoiceDetails.labels 
      };
};

// --- Generation --- //
// Define necessary types inline if not in types.ts
interface GenerationConfig { 
    // TODO: Define specific properties based on backend expectation
    [key: string]: any; 
}
interface GenerationStartResponse { taskId: string; jobId: number } // TODO: Verify response structure

const startGeneration = async (config: GenerationConfig): Promise<GenerationStartResponse> => {
    const response = await apiClient.post<{ data: GenerationStartResponse }>('/generate', config);
    return handleApiResponse(response);
};

// Add missing toggleScriptArchive function
const toggleScriptArchive = async (scriptId: number, archive: boolean): Promise<ScriptMetadata> => {
    const response = await apiClient.patch<{ data: ScriptMetadata }>(`/scripts/${scriptId}/archive`, { archive });
    return handleApiResponse(response);
};

// --- Batches --- //
// Define necessary types inline if not in types.ts
interface BatchListInfo { // TODO: Define specific properties based on backend
    prefix: string;
    created_at: string;
    // ... other potential fields
}

const listBatches = async (): Promise<BatchListInfo[]> => {
    const response = await apiClient.get<{ data: BatchListInfo[] }>('/batches');
    return handleApiResponse(response);
};

// Add missing getBatchMetadata function
// Define necessary types inline if not in types.ts
interface Take { /* ... properties ... */ id: number; line: string; /* ... */ }
interface BatchMetadata { 
    batch_prefix: string; 
    script_name?: string; 
    character_description?: string;
    voice_name?: string;
    takes: Take[]; // Define Take type more accurately if possible
    // ... other potential fields
}
const getBatchMetadata = async (batchPrefix: string): Promise<BatchMetadata> => {
    // Ensure batchPrefix is properly encoded for the URL path
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const response = await apiClient.get<{ data: BatchMetadata }>(`/batch/${encodedPrefix}`);
    return handleApiResponse(response);
};

// Add missing updateTakeRank function
const updateTakeRank = async (batchPrefix: string, filename: string, rank: number | null): Promise<void> => {
    // Ensure batchPrefix and filename are properly encoded for the URL path
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const encodedFilename = encodeURIComponent(filename);
    const response = await apiClient.patch(`/batch/${encodedPrefix}/take/${encodedFilename}`, { rank });
    // We don't expect specific data back, just handle potential errors
    handleApiResponse<any>(response); // Use generic type for response handling
};

// Add missing getLineTakes function
const getLineTakes = async (batchPrefix: string, lineKey: string): Promise<Take[]> => {
    // Ensure batchPrefix and lineKey are properly encoded for the URL path
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const encodedLineKey = encodeURIComponent(lineKey);
    // NOTE: Endpoint path needs confirmation from backend route definition
    const response = await apiClient.get<{ data: Take[] }>(`/batch/${encodedPrefix}/line/${encodedLineKey}/takes`); 
    return handleApiResponse(response);
};

// Add missing regenerateLineTakes function
// Define necessary types inline if not in types.ts
interface RegenerateLinePayload {
    line_key: string;
    line_text: string;
    num_new_takes: number;
    settings: any; // Define more specific type? e.g., VoiceSettingRanges
    replace_existing: boolean;
    update_script?: boolean;
}
const regenerateLineTakes = async (batchPrefix: string, payload: RegenerateLinePayload): Promise<GenerationStartResponse> => {
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const response = await apiClient.post<{ data: GenerationStartResponse }>(`/batch/${encodedPrefix}/regenerate_line`, payload);
    return handleApiResponse(response);
};

// --- Audio Cropping --- //
// Define necessary types inline if not in types.ts
interface CropTakePayload { startTime: number; endTime: number }
interface CropTakeResponse { task_id: string; message: string }

const cropTake = async (batchPrefix: string, filename: string, startTime: number, endTime: number): Promise<CropTakeResponse> => {
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const encodedFilename = encodeURIComponent(filename);
    const response = await apiClient.post<{ data: CropTakeResponse }>(`/batch/${encodedPrefix}/takes/${encodedFilename}/crop`, { startTime, endTime });
    return handleApiResponse(response);
};

// --- Task Status --- //
// Define necessary types inline if not in types.ts
interface TaskStatus {
    task_id: string;
    status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY' | 'REVOKED' | string; // Allow other statuses
    info?: any; // Or define more specifically if possible
}
const getTaskStatus = async (taskId: string): Promise<TaskStatus> => {
    // Use a generic task status endpoint
    const response = await apiClient.get<{ data: TaskStatus }>(`/task/${taskId}/status`);
    return handleApiResponse(response);
};

// --- Audio URL Helper --- //
const getAudioUrl = (relpath: string): string => {
    // Construct the URL for the audio endpoint
    // Ensure relpath doesn't start with / if API_BASE is involved
    const cleanRelPath = relpath.startsWith('/') ? relpath.substring(1) : relpath;
    return `${API_BASE}/audio/${cleanRelPath}`;
};

// Add missing startSpeechToSpeech function
// Define necessary types inline if not in types.ts
interface SpeechToSpeechPayload {
    line_key: string;
    source_audio_data: string; // Assuming base64 string
    num_new_takes: number;
    target_voice_id: string;
    model_id: string;
    settings: any; // Define more specific type? e.g., VoiceSettings
    replace_existing: boolean;
}
const startSpeechToSpeech = async (batchPrefix: string, payload: SpeechToSpeechPayload): Promise<GenerationStartResponse> => {
    const encodedPrefix = batchPrefix.split('/').map(encodeURIComponent).join('/');
    const response = await apiClient.post<{ data: GenerationStartResponse }>(`/batch/${encodedPrefix}/speech_to_speech`, payload);
    return handleApiResponse(response);
};

// Add missing getVoicePreview function
interface VoicePreviewSettings {
    stability?: number;
    similarity?: number;
    style?: number;
    speed?: number;
}
const getVoicePreview = async (voiceId: string, settings?: VoicePreviewSettings): Promise<Blob> => {
    // Use apiClient.get with responseType: 'blob' and handle potential errors
    try {
        const response = await apiClient.get(`/voices/${voiceId}/preview`, {
            params: settings,
            responseType: 'blob', // Important for file/blob responses
        });
        return response.data; // Axios wraps blob in data
    } catch (error: any) {
        // Attempt to extract error message if it's a structured error
        let errorMsg = `Failed to fetch preview for ${voiceId}`; 
        if (error.response && error.response.data) {
             // If the response was JSON error from backend (less likely for blob endpoint but possible)
             try {
                 const errorData = JSON.parse(await (error.response.data as Blob).text());
                 errorMsg = errorData.error || errorMsg;
             } catch (parseError) { 
                 // If reading blob as text fails, stick to generic axios error
                 errorMsg = error.message || errorMsg;
             }
        } else {
            errorMsg = error.message || errorMsg;
        }
        console.error(`[API] Error fetching preview for ${voiceId}: ${errorMsg}`);
        throw new Error(errorMsg);
    }
};

// Add missing optimizeLineText function
// Define necessary types inline if not in types.ts
interface OptimizeLineTextPayload { line_text: string }
interface OptimizeLineTextResponse { optimized_text: string }
const optimizeLineText = async (lineText: string): Promise<OptimizeLineTextResponse> => {
    const response = await apiClient.post<{ data: OptimizeLineTextResponse }>('/optimize-line-text', { line_text: lineText });
    return handleApiResponse(response);
};

// --- Lower Priority Template Functions (May be redundant) --- //

// List Categories (Potentially redundant if always fetched with template)
const listVoScriptTemplateCategories = async (templateId?: number): Promise<VoScriptTemplateCategory[]> => {
    const response = await apiClient.get<{ data: VoScriptTemplateCategory[] }>('/vo-script-template-categories', { params: { template_id: templateId } });
    return handleApiResponse(response);
};

// Get Single Category (Potentially redundant if always fetched with template)
const getVoScriptTemplateCategory = async (categoryId: number): Promise<VoScriptTemplateCategory> => {
    const response = await apiClient.get<{ data: VoScriptTemplateCategory }>(`/vo-script-template-categories/${categoryId}`);
    return handleApiResponse(response);
};

// List Lines (Potentially redundant if always fetched with template)
const listVoScriptTemplateLines = async (params?: { templateId?: number; categoryId?: number }): Promise<VoScriptTemplateLine[]> => {
    const response = await apiClient.get<{ data: VoScriptTemplateLine[] }>('/vo-script-template-lines', { params });
    return handleApiResponse(response);
};

// Get Single Line (Potentially redundant if always fetched with template)
const getVoScriptTemplateLine = async (lineId: number): Promise<VoScriptTemplateLine> => {
    const response = await apiClient.get<{ data: VoScriptTemplateLine }>(`/vo-script-template-lines/${lineId}`);
    return handleApiResponse(response);
};

// --- Consolidate into single export --- //
// Group functions logically
export const api = {
    // Generic
    getVoices,
    getModels,
    // --- Add Generation functions --- //
    startGeneration,
    // Jobs
    listGenerationJobs,
    getGenerationJob,
    // Add Task Status endpoint
    getTaskStatus,
    // Legacy Scripts
    getScript,
    submitScriptFeedback,
    runScriptAgent,
    createScript,
    deleteScript,
    // Add missing listScripts export
    listScripts,
    // Add missing updateScript export
    updateScript,
    // VO Script Templates
    fetchVoScriptTemplates,
    listVoScriptTemplates,
    getVoScriptTemplate,
    createVoScriptTemplate,
    deleteVoScriptTemplate,
    // Add the missing update template function to exports
    updateVoScriptTemplate,
    // Add the new function to exports
    updateVoScriptTemplateLine,
    // Add missing category/line CRUD functions to exports
    createVoScriptTemplateCategory,
    updateVoScriptTemplateCategory,
    deleteVoScriptTemplateCategory,
    // Add potentially redundant list/get exports for categories/lines
    listVoScriptTemplateCategories,
    getVoScriptTemplateCategory,
    createVoScriptTemplateLine,
    listVoScriptTemplateLines,
    getVoScriptTemplateLine,
    deleteVoScriptTemplateLine,
    // VO Scripts (CRUD)
    createVoScript,
    listVoScripts,
    getVoScript,
    updateVoScript,
    deleteVoScript,
    // VO Script Actions
    runVoScriptAgent: runVoScriptAgentAction, // Use renamed function
    submitVoScriptFeedback,
    refineVoScriptLine,
    refineVoScriptCategory,
    refineVoScript,
    toggleLockVoScriptLine,
    updateLineText,
    deleteVoScriptLine,
    addVoScriptLine,
    generateVoScriptLine,
    acceptVoScriptLine,
    instantiateTargetLines,
    // Add the new function
    generateCategoryBatch,
    // --- Add Voice Design functions --- //
    createVoicePreviews,
    saveVoiceFromPreview,
    // Add missing toggleScriptArchive export
    toggleScriptArchive,
    // Add missing listBatches export
    listBatches,
    // Add missing getBatchMetadata export
    getBatchMetadata,
    // Add missing updateTakeRank export
    updateTakeRank,
    // Add missing getLineTakes export
    getLineTakes,
    // Add missing regenerateLineTakes export
    regenerateLineTakes,
    // Add missing startSpeechToSpeech export
    startSpeechToSpeech,
    // Add missing cropTake export
    cropTake,
    // Add Audio URL Helper
    getAudioUrl,
    // Add missing getVoicePreview export
    getVoicePreview,
    // Add missing optimizeLineText export
    optimizeLineText,
};
