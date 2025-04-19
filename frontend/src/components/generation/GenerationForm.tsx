import React, { useState, useEffect } from 'react';
import { GenerationConfig, ModelOption, ScriptMetadata } from '../../types';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { api } from '../../api';
import { Select } from '@mantine/core';

interface GenerationFormProps {
  selectedVoiceIds: string[];
  onSubmit: (config: GenerationConfig) => void;
  isSubmitting: boolean;
}

// Default Ranges
const DEFAULT_STABILITY_RANGE: [number, number] = [0.5, 0.75];
const DEFAULT_SIMILARITY_RANGE: [number, number] = [0.75, 0.9];
const DEFAULT_STYLE_RANGE: [number, number] = [0.0, 0.45]; // Style Exaggeration
const DEFAULT_SPEED_RANGE: [number, number] = [0.95, 1.05];
const DEFAULT_SPEAKER_BOOST = true;
const DEFAULT_MODEL_ID = "eleven_multilingual_v2";

const GenerationForm: React.FC<GenerationFormProps> = ({ selectedVoiceIds, onSubmit, isSubmitting }) => {
  // Basic Info
  const [skinName, setSkinName] = useState<string>('MyNewSkin');
  const [variants, setVariants] = useState<number>(3);
  const [error, setError] = useState<string | null>(null);

  // DB Script State
  const [availableScripts, setAvailableScripts] = useState<ScriptMetadata[]>([]);
  const [selectedScriptId, setSelectedScriptId] = useState<string | null>(null); // Store as string for Select component
  const [scriptsLoading, setScriptsLoading] = useState<boolean>(false);
  const [scriptsError, setScriptsError] = useState<string | null>(null);

  // TTS Range Settings State
  const [stabilityRange, setStabilityRange] = useState<[number, number]>(DEFAULT_STABILITY_RANGE);
  const [similarityRange, setSimilarityRange] = useState<[number, number]>(DEFAULT_SIMILARITY_RANGE);
  const [styleRange, setStyleRange] = useState<[number, number]>(DEFAULT_STYLE_RANGE);
  const [speedRange, setSpeedRange] = useState<[number, number]>(DEFAULT_SPEED_RANGE);
  const [speakerBoost, setSpeakerBoost] = useState<boolean>(DEFAULT_SPEAKER_BOOST);

  // Model Selection State
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(DEFAULT_MODEL_ID);
  const [modelsLoading, setModelsLoading] = useState<boolean>(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
        setModelsLoading(true);
        setModelsError(null);
        try {
            const models = await api.getModels();
            setAvailableModels(models);
            // Ensure default is valid, fallback if needed
            if (!models.find(m => m.model_id === DEFAULT_MODEL_ID)) {
                 setSelectedModelId(models[0]?.model_id || ''); // Select first available if default missing
            }
        } catch (err: any) {
             setModelsError(`Failed to load models: ${err.message}`);
             console.error(err);
        } finally {
             setModelsLoading(false);
        }
    };
    fetchModels();
  }, []);

  // Fetch available scripts on mount
  useEffect(() => {
    setScriptsLoading(true);
    setScriptsError(null);
    api.listScripts(false)
      .then(scripts => {
        setAvailableScripts(scripts);
        // Reset selection if current one disappears?
        if (selectedScriptId && !scripts.find(s => s.id.toString() === selectedScriptId)) {
          setSelectedScriptId(null);
        }
      })
      .catch(err => {
        setScriptsError(`Failed to load scripts: ${err.message}`);
        console.error(err);
      })
      .finally(() => setScriptsLoading(false));
  }, []);

  // Handle form submission
  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    if (selectedVoiceIds.length === 0) {
      setError('Please select at least one voice.');
      return;
    }
    
    if (!selectedScriptId) {
      setError('Please select a script from the list.');
      return;
    }
    
    if (variants <= 0) {
      setError('Variants per line must be at least 1.');
      return;
    }
    // Ensure ranges are valid (min <= max)
    if (stabilityRange[0] > stabilityRange[1] || 
        similarityRange[0] > similarityRange[1] ||
        styleRange[0] > styleRange[1] ||
        speedRange[0] > speedRange[1]) {
        setError('Invalid range: Min value cannot be greater than Max value for TTS settings.');
        return;
    }

    // Build config
    const baseConfig = {
      skin_name: skinName,
      voice_ids: selectedVoiceIds,
      variants_per_line: variants,
      stability_range: stabilityRange,
      similarity_boost_range: similarityRange,
      style_range: styleRange,
      speed_range: speedRange,
      use_speaker_boost: speakerBoost,
      model_id: selectedModelId
    };

    const finalConfig: GenerationConfig = {
      ...baseConfig,
      script_id: parseInt(selectedScriptId, 10), // Convert string ID back to number
      // script_csv_content is never set
    };

    onSubmit(finalConfig);
  };

  // Helper to format slider value
  const formatSliderValue = (value: number) => value.toFixed(2);

  // Check if submit should be disabled
  const isSubmitDisabled = isSubmitting
    || selectedVoiceIds.length === 0
    || !selectedScriptId;

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
        <Select
          label="Select Script"
          placeholder="Choose a script..."
          value={selectedScriptId}
          onChange={setSelectedScriptId}
          data={availableScripts.map(script => ({
            value: script.id.toString(),
            label: `${script.name} (${script.line_count} lines, updated ${new Date(script.updated_at).toLocaleDateString()})`
          }))}
          searchable
          nothingFoundMessage={scriptsLoading ? "Loading scripts..." : scriptsError ? "Error loading scripts" : "No scripts found"}
          disabled={scriptsLoading || !!scriptsError}
          required
          error={scriptsError}
          mt="md"
        />
      </div>

      <div style={{ marginTop: '10px' }}>
        <label htmlFor="modelSelect">Model: </label>
        <select 
            id="modelSelect" 
            value={selectedModelId} 
            onChange={e => setSelectedModelId(e.target.value)} 
            disabled={modelsLoading || !!modelsError}
        >
            {modelsLoading && <option>Loading models...</option>}
            {modelsError && <option>Error loading models</option>}
            {!modelsLoading && !modelsError && availableModels.map(model => (
                <option key={model.model_id} value={model.model_id}>
                    {model.name} ({model.model_id})
                </option>
            ))}
        </select>
        {modelsError && <span style={{ color: 'red', marginLeft: '10px' }}>{modelsError}</span>}
      </div>

      <div style={{ marginTop: '20px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
          <h5>Voice Setting Ranges (Randomized per Take):</h5>
          
          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <label>Stability Range: [{formatSliderValue(stabilityRange[0])} - {formatSliderValue(stabilityRange[1])}]</label>
              <Slider 
                  range
                  min={0} max={1} step={0.01} allowCross={false}
                  value={stabilityRange} 
                  onChange={(value: number | number[]) => setStabilityRange(value as [number, number])} 
              />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>More Variable</small><small>More Stable</small></div>
          </div>

          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <label>Similarity Boost Range: [{formatSliderValue(similarityRange[0])} - {formatSliderValue(similarityRange[1])}]</label>
              <Slider 
                  range
                  min={0} max={1} step={0.01} allowCross={false}
                  value={similarityRange} 
                  onChange={(value: number | number[]) => setSimilarityRange(value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Low</small><small>High</small></div>
          </div>

          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <label>Style Exaggeration Range: [{formatSliderValue(styleRange[0])} - {formatSliderValue(styleRange[1])}]</label>
              <Slider 
                  range
                  min={0} max={1} step={0.01} allowCross={false}
                  value={styleRange} 
                  onChange={(value: number | number[]) => setStyleRange(value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><small>None</small><small>Exaggerated</small></div>
          </div>

          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <label>Speed Range: [{formatSliderValue(speedRange[0])} - {formatSliderValue(speedRange[1])}]</label>
              <Slider 
                  range
                  min={0.5} max={2.0} step={0.05} allowCross={false}
                  value={speedRange} 
                  onChange={(value: number | number[]) => setSpeedRange(value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Slower</small><small>Faster</small></div>
          </div>

          <div style={{ marginBottom: '10px' }}>
              <input 
                  type="checkbox" id="speakerBoost" 
                  checked={speakerBoost} onChange={e => setSpeakerBoost(e.target.checked)}
              />
              <label htmlFor="speakerBoost"> Speaker Boost</label>
              <small> (Fixed for all takes in job)</small>
          </div>
      </div>
      
      <button type="submit" disabled={isSubmitDisabled} style={{ marginTop: '15px' }}>
        {isSubmitting ? 'Generating...' : 'Start Generation Job'}
      </button>
    </form>
  );
};

export default GenerationForm; 