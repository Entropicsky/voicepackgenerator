import React, { createContext, useState, useContext, useCallback, useEffect, ReactNode } from 'react';
import { api } from '../api';
import { VoiceOption } from '../types';

interface VoiceContextType {
  voices: VoiceOption[];
  loading: boolean;
  error: string | null;
  refetchVoices: () => void; // Function to manually trigger a refetch
}

const VoiceContext = createContext<VoiceContextType | undefined>(undefined);

interface VoiceProviderProps {
  children: ReactNode;
}

export const VoiceProvider: React.FC<VoiceProviderProps> = ({ children }) => {
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchVoices = useCallback(async () => {
    console.log("[VoiceContext] Fetching voices...");
    setLoading(true);
    setError(null);
    try {
      // Fetch all available voices (adjust options if needed later)
      const fetchedVoices = await api.getVoices({ page_size: 200 }); 
      setVoices(fetchedVoices);
    } catch (err: any) {
      console.error("[VoiceContext] Failed to fetch voices:", err);
      setError(`Failed to load voices: ${err.message}`);
      setVoices([]); // Clear voices on error
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch voices on initial mount
  useEffect(() => {
    fetchVoices();
  }, [fetchVoices]);

  // Provide state and refetch function through context
  const value: VoiceContextType = {
    voices,
    loading,
    error,
    refetchVoices: fetchVoices, // Expose fetchVoices as refetchVoices
  };

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
};

// Hook to use the context
export const useVoiceContext = (): VoiceContextType => {
  const context = useContext(VoiceContext);
  if (context === undefined) {
    throw new Error('useVoiceContext must be used within a VoiceProvider');
  }
  return context;
}; 