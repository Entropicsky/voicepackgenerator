// frontend/src/services/apiService.ts

const API_BASE_URL = '/api'; // Use relative path for proxy

// Define a custom error class for API errors
export class APIError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data: any) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

// Generic fetch function
async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const config: RequestInit = {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  // Add body for methods that allow it
  if (options.body && (config.method === 'POST' || config.method === 'PUT' || config.method === 'PATCH')) {
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, config);

  let responseData: any;
  try {
    responseData = await response.json();
  } catch (error) {
    // Handle cases where response might not be JSON (e.g., 204 No Content)
    if (!response.ok) {
       throw new APIError(response.statusText || 'HTTP error', response.status, null);
    }
    return null as T; // Or handle as appropriate for non-JSON responses
  }
  
  if (!response.ok) {
    const message = responseData.error || responseData.message || `HTTP error! status: ${response.status}`;
    throw new APIError(message, response.status, responseData);
  }

  // Assuming successful responses wrap data in a 'data' field based on backend make_api_response
  return responseData.data as T;
}

// Specific methods
export const apiService = {
  get: <T>(endpoint: string, options: RequestInit = {}) => request<T>(endpoint, { ...options, method: 'GET' }),
  post: <T>(endpoint: string, body: any, options: RequestInit = {}) => request<T>(endpoint, { ...options, method: 'POST', body }),
  put: <T>(endpoint: string, body: any, options: RequestInit = {}) => request<T>(endpoint, { ...options, method: 'PUT', body }),
  patch: <T>(endpoint: string, body: any, options: RequestInit = {}) => request<T>(endpoint, { ...options, method: 'PATCH', body }),
  delete: <T>(endpoint: string, options: RequestInit = {}) => request<T>(endpoint, { ...options, method: 'DELETE' }),
}; 