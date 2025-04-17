// frontend/src/api.ts
import {
  VoiceOption,
  GenerationConfig,
  GenerationStartResponse,
  TaskStatus,
  BatchInfo,
  BatchMetadata
} from './types';

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
  // --- Generation --- //
  getVoices: async (): Promise<VoiceOption[]> => {
    const response = await fetch(`${API_BASE}/api/voices`);
    return handleApiResponse<VoiceOption[]>(response);
  },

  startGeneration: async (config: GenerationConfig): Promise<GenerationStartResponse> => {
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    // Expects { data: { task_id: "..." } }
    return handleApiResponse<GenerationStartResponse>(response);
  },

  getTaskStatus: async (taskId: string): Promise<TaskStatus> => {
    const response = await fetch(`${API_BASE}/api/generate/${taskId}/status`);
    // Expects { data: { task_id: "...", status: "...", info: ... } }
    return handleApiResponse<TaskStatus>(response);
  },

  // --- Ranking --- //
  listBatches: async (): Promise<BatchInfo[]> => {
    const response = await fetch(`${API_BASE}/api/batches`);
    return handleApiResponse<BatchInfo[]>(response);
  },

  getBatchMetadata: async (batchId: string): Promise<BatchMetadata> => {
    const response = await fetch(`${API_BASE}/api/batch/${batchId}`);
    return handleApiResponse<BatchMetadata>(response);
  },

  updateTakeRank: async (batchId: string, filename: string, rank: number | null): Promise<void> => {
    const response = await fetch(`${API_BASE}/api/batch/${batchId}/take/${filename}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ rank }),
    });
    // Expects { data: { status: "..." } } or error
    await handleApiResponse<any>(response); // Don't need specific return type
  },

  lockBatch: async (batchId: string): Promise<{ locked: boolean }> => {
    const response = await fetch(`${API_BASE}/api/batch/${batchId}/lock`, {
      method: 'POST',
    });
    // Expects { data: { locked: true, message?: "..." } }
    return handleApiResponse<{ locked: boolean }>(response);
  },

  // --- Audio --- //
  getAudioUrl: (relpath: string): string => {
    // Construct the URL for the audio endpoint
    // Ensure relpath doesn't start with / if API_BASE is involved
    const cleanRelPath = relpath.startsWith('/') ? relpath.substring(1) : relpath;
    return `${API_BASE}/audio/${cleanRelPath}`;
  }
}; 