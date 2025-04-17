import React, { useState, useCallback } from 'react';
import { GenerationConfig } from '../../types';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';

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

const GenerationForm: React.FC<GenerationFormProps> = ({ selectedVoiceIds, onSubmit, isSubmitting }) => {
  // Basic Info
  const [skinName, setSkinName] = useState<string>('MyNewSkin');
  const [variants, setVariants] = useState<number>(3);
  const [scriptFile, setScriptFile] = useState<File | null>(null);
  const [scriptContent, setScriptContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // TTS Range Settings State
  const [stabilityRange, setStabilityRange] = useState<[number, number]>(DEFAULT_STABILITY_RANGE);
  const [similarityRange, setSimilarityRange] = useState<[number, number]>(DEFAULT_SIMILARITY_RANGE);
  const [styleRange, setStyleRange] = useState<[number, number]>(DEFAULT_STYLE_RANGE);
  const [speedRange, setSpeedRange] = useState<[number, number]>(DEFAULT_SPEED_RANGE);
  const [speakerBoost, setSpeakerBoost] = useState<boolean>(DEFAULT_SPEAKER_BOOST);

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

    // Ensure ranges are valid (min <= max)
    if (stabilityRange[0] > stabilityRange[1] || 
        similarityRange[0] > similarityRange[1] ||
        styleRange[0] > styleRange[1] ||
        speedRange[0] > speedRange[1]) {
        setError('Invalid range: Min value cannot be greater than Max value for TTS settings.');
        return;
    }

    const config: GenerationConfig = {
      skin_name: skinName,
      voice_ids: selectedVoiceIds,
      script_csv_content: scriptContent!, 
      variants_per_line: variants,
      // Pass ranges to the backend
      stability_range: stabilityRange,
      similarity_boost_range: similarityRange,
      style_range: styleRange,
      speed_range: speedRange,
      use_speaker_boost: speakerBoost,
    };
    onSubmit(config);
  };

  // Helper to format slider value
  const formatSliderValue = (value: number) => value.toFixed(2);

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

      {/* TTS Settings Section with Range Sliders */} 
      <div style={{ marginTop: '20px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
          <h5>Voice Setting Ranges (Randomized per Take):</h5>
          
          {/* Stability Range */} 
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

          {/* Similarity Range */} 
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

          {/* Style Range */} 
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

           {/* Speed Range */} 
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

          {/* Speaker Boost */} 
          <div style={{ marginBottom: '10px' }}>
              <input 
                  type="checkbox" id="speakerBoost" 
                  checked={speakerBoost} onChange={e => setSpeakerBoost(e.target.checked)}
              />
              <label htmlFor="speakerBoost"> Speaker Boost</label>
              <small> (Fixed for all takes in job)</small>
          </div>
      </div>
      
      <button type="submit" disabled={isSubmitting || !scriptContent || selectedVoiceIds.length === 0} style={{ marginTop: '15px' }}>
        {isSubmitting ? 'Generating...' : 'Start Generation Job'}
      </button>
    </form>
  );
};

export default GenerationForm; 