// frontend/src/api.ts
import axios, { AxiosResponse } from 'axios';
import {
    VoiceOption, ModelOption, GenerationJob,
    Script, ScriptLine, VoScriptTemplate, VoScriptTemplateCategory, SubmitFeedbackPayload,
    VoScript, VoScriptLineData, RunAgentPayload, UpdateVoScriptPayload, RefineLinePayload,
    RefineLineResponse, UpdateVoScriptTemplateCategoryPayload, RefineCategoryPayload,
    RefineMultipleLinesResponse, RefineScriptPayload, DeleteResponse, AddVoScriptLinePayload,
    JobSubmissionResponse
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
    const response = await apiClient.get<{ data: GenerationJob[] }>('/generation-jobs');
    return handleApiResponse(response);
};

const getGenerationJob = async (jobId: number): Promise<GenerationJob> => {
    const response = await apiClient.get<{ data: GenerationJob }>(`/generation-jobs/${jobId}`);
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
        `/vo-scripts/${scriptId}/categories/${encodeURIComponent(categoryName)}/generate-batch`, 
        payload
    );
    return handleApiResponse(response);
};

// --- Consolidate into single export --- //
// Group functions logically
export const api = {
    // Generic
    getVoices,
    getModels,
    // Jobs
    listGenerationJobs,
    getGenerationJob,
    // Legacy Scripts
    getScript,
    submitScriptFeedback,
    runScriptAgent,
    createScript,
    deleteScript,
    // VO Script Templates
    fetchVoScriptTemplates,
    listVoScriptTemplates,
    getVoScriptTemplate,
    createVoScriptTemplate,
    deleteVoScriptTemplate,
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
};
