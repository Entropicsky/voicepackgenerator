import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import VoiceSelector from '../components/generation/VoiceSelector';
import GenerationForm, { VoiceSettingRanges } from '../components/generation/GenerationForm';
import { GenerationConfig } from '../types';
import { api } from '../api';

// Helper to calculate midpoint
const calculateMidpoint = (range: [number, number]): number => {
  return (range[0] + range[1]) / 2;
}

// Type for the specific preview settings
interface PreviewSettings {
  stability: number;
  similarity: number;
  style: number;
  speed: number;
  // Note: speakerBoost is not directly used in preview settings, but kept if needed later
}

const GenerationPage: React.FC = () => {
  const [selectedVoiceIds, setSelectedVoiceIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const navigate = useNavigate();

  // --- NEW: State for current range midpoints for preview --- 
  const [currentPreviewSettings, setCurrentPreviewSettings] = useState<PreviewSettings | null>(null);

  const handleVoiceSelectionChange = (newSelectedIds: string[]) => {
    setSelectedVoiceIds(newSelectedIds);
  };

  // --- NEW: Callback to update preview settings when form ranges change --- 
  const handleFormRangesChange = useCallback((ranges: VoiceSettingRanges) => {
    setCurrentPreviewSettings({
      stability: calculateMidpoint(ranges.stabilityRange),
      similarity: calculateMidpoint(ranges.similarityRange),
      style: calculateMidpoint(ranges.styleRange),
      speed: calculateMidpoint(ranges.speedRange),
    });
  }, []); // Empty dependency array, function itself doesn't depend on state

  const handleGenerationSubmit = useCallback(async (config: GenerationConfig) => {
    setIsSubmitting(true);
    setSubmitError(null);
    console.log("Submitting generation config:", config);
    try {
      const response = await api.startGeneration(config);
      console.log(`Job ${response.job_id} (Task ${response.task_id}) submitted.`);
      navigate('/jobs');
    } catch (error: any) {
      console.error("Failed to start generation job:", error);
      setSubmitError(`Failed to start job: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }, [navigate]);

  return (
    <div>
      <h2>Generate Recordings</h2>

      {/* Use columns or better layout later */}
      <div style={{ display: 'flex', gap: '20px' }}>
        <div style={{ flex: 1 }}>
           <VoiceSelector
            selectedVoices={selectedVoiceIds}
            onChange={handleVoiceSelectionChange}
            previewSettings={currentPreviewSettings}
          />
        </div>
        <div style={{ flex: 2 }}>
          <GenerationForm
            selectedVoiceIds={selectedVoiceIds}
            onSubmit={handleGenerationSubmit}
            isSubmitting={isSubmitting}
            onRangesChange={handleFormRangesChange}
          />
           {submitError && <p style={{ color: 'red', marginTop: '10px' }}>{submitError}</p>}
        </div>
      </div>

    </div>
  );
};

export default GenerationPage; 