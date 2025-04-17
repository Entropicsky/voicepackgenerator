// frontend/src/api.ts
import {
  VoiceOption,
  GenerationConfig,
  GenerationStartResponse,
  TaskStatus,
  BatchInfo,
  BatchMetadata,
  GenerationJob,
  BatchDetailInfo
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

  // --- Ranking --- //
  listBatches: async (): Promise<BatchDetailInfo[]> => {
    const response = await fetch(`${API_BASE}/api/batches`);
    return handleApiResponse<BatchDetailInfo[]>(response);
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