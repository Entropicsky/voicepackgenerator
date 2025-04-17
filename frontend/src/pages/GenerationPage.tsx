import React, { useState, useCallback } from 'react';
import VoiceSelector from '../components/generation/VoiceSelector';
import GenerationForm from '../components/generation/GenerationForm';
import TaskMonitor from '../components/generation/TaskMonitor';
import { GenerationConfig } from '../types';
import { api } from '../api';

const GenerationPage: React.FC = () => {
  const [selectedVoiceIds, setSelectedVoiceIds] = useState<string[]>([]);
  const [submittedTaskIds, setSubmittedTaskIds] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleVoiceSelectionChange = (newSelectedIds: string[]) => {
    setSelectedVoiceIds(newSelectedIds);
  };

  const handleGenerationSubmit = useCallback(async (config: GenerationConfig) => {
    setIsSubmitting(true);
    setSubmitError(null);
    console.log("Submitting generation config:", config);
    try {
      const response = await api.startGeneration(config);
      setSubmittedTaskIds(prevIds => [...prevIds, response.task_id]); // Add new task ID
    } catch (error: any) {
      console.error("Failed to start generation job:", error);
      setSubmitError(`Failed to start job: ${error.message}`);
    } finally {
      setIsSubmitting(false);
    }
  }, []); // No dependencies needed if api is stable

  return (
    <div>
      <h2>Generate New Voice Pack</h2>

      {/* Use columns or better layout later */}
      <div style={{ display: 'flex', gap: '20px' }}>
        <div style={{ flex: 1 }}>
           <VoiceSelector
            selectedVoices={selectedVoiceIds}
            onChange={handleVoiceSelectionChange}
          />
        </div>
        <div style={{ flex: 2 }}>
          <GenerationForm
            selectedVoiceIds={selectedVoiceIds}
            onSubmit={handleGenerationSubmit}
            isSubmitting={isSubmitting}
          />
           {submitError && <p style={{ color: 'red', marginTop: '10px' }}>{submitError}</p>}
        </div>
      </div>

      <hr style={{margin: '20px 0'}} />

      <TaskMonitor submittedTaskIds={submittedTaskIds} />

    </div>
  );
};

export default GenerationPage; 