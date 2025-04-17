import React, { useState, useCallback } from 'react';
import { GenerationConfig } from '../../types';

interface GenerationFormProps {
  selectedVoiceIds: string[];
  onSubmit: (config: GenerationConfig) => void;
  isSubmitting: boolean;
}

const GenerationForm: React.FC<GenerationFormProps> = ({ selectedVoiceIds, onSubmit, isSubmitting }) => {
  const [skinName, setSkinName] = useState<string>('MyNewSkin');
  const [variants, setVariants] = useState<number>(3);
  const [scriptFile, setScriptFile] = useState<File | null>(null);
  const [scriptContent, setScriptContent] = useState<string | null>(null); // To store file content
  const [error, setError] = useState<string | null>(null);

  // TODO: Add state for parameter ranges if needed, using defaults for now

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.type === 'text/csv' || file.name.endsWith('.csv')) {
        setScriptFile(file);
        setError(null);
        // Read file content
        const reader = new FileReader();
        reader.onload = (e) => {
          setScriptContent(e.target?.result as string);
        };
        reader.onerror = () => {
          setError('Error reading script file.');
          setScriptContent(null);
        };
        reader.readAsText(file);
      } else {
        setError('Please upload a valid CSV file.');
        setScriptFile(null);
        setScriptContent(null);
      }
    } else {
      setScriptFile(null);
      setScriptContent(null);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (selectedVoiceIds.length === 0) {
      setError('Please select at least one voice.');
      return;
    }
    if (!scriptContent) {
      setError('Please upload a script CSV file.');
      return;
    }
    if (variants <= 0) {
      setError('Variants per line must be at least 1.');
      return;
    }

    const config: GenerationConfig = {
      skin_name: skinName,
      voice_ids: selectedVoiceIds,
      script_csv_content: scriptContent,
      variants_per_line: variants,
      // TODO: Add optional params like model, ranges, speaker_boost from state later
    };
    onSubmit(config);
  };

  return (
    <form onSubmit={handleSubmit} style={{ border: '1px solid #ccc', padding: '15px', marginTop: '15px' }}>
      <h4>Generation Parameters:</h4>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      <div>
        <label htmlFor="skinName">Skin Name: </label>
        <input
          type="text"
          id="skinName"
          value={skinName}
          onChange={(e) => setSkinName(e.target.value)}
          required
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label htmlFor="variants">Takes per Line: </label>
        <input
          type="number"
          id="variants"
          value={variants}
          onChange={(e) => setVariants(parseInt(e.target.value, 10) || 1)}
          min="1"
          required
        />
      </div>
      <div style={{ marginTop: '10px' }}>
        <label htmlFor="scriptCsv">Script CSV File: </label>
        <input
          type="file"
          id="scriptCsv"
          accept=".csv"
          onChange={handleFileChange}
          required
        />
        {scriptFile && <span> ({scriptFile.name})</span>}
      </div>

      {/* TODO: Add inputs for stability_range, similarity_boost_range, style_range, speed_range, use_speaker_boost */}

      <button type="submit" disabled={isSubmitting || !scriptContent || selectedVoiceIds.length === 0} style={{ marginTop: '15px' }}>
        {isSubmitting ? 'Generating...' : 'Start Generation Job'}
      </button>
    </form>
  );
};

export default GenerationForm; 