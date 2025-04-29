import React, { useState, useEffect } from 'react';
import { GenerationConfig, ModelOption, VoScriptListItem } from '../../types';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { api } from '../../api';
import { Select, Button, TextInput, NumberInput, Checkbox, Text, Box } from '@mantine/core';
import { useForm, isNotEmpty } from '@mantine/form';

// Type for the settings ranges
export interface VoiceSettingRanges {
  stabilityRange: [number, number];
  similarityRange: [number, number];
  styleRange: [number, number];
  speedRange: [number, number];
  speakerBoost: boolean;
}

interface GenerationFormProps {
  selectedVoiceIds: string[];
  onSubmit: (config: GenerationConfig) => void;
  isSubmitting: boolean;
  // Callback for when ranges change
  onRangesChange?: (ranges: VoiceSettingRanges) => void;
}

// Default Ranges
const DEFAULT_STABILITY_RANGE: [number, number] = [0.5, 0.75];
const DEFAULT_SIMILARITY_RANGE: [number, number] = [0.70, 0.9];
const DEFAULT_STYLE_RANGE: [number, number] = [0.25, 0.55]; // Style Exaggeration
const DEFAULT_SPEED_RANGE: [number, number] = [0.85, 1.05];
const DEFAULT_SPEAKER_BOOST = true;
const DEFAULT_MODEL_ID = "eleven_multilingual_v2";

// --- Session Storage Keys ---
const SESSION_STORAGE_KEYS = {
  STABILITY: 'genFormStabilityRange',
  SIMILARITY: 'genFormSimilarityRange',
  STYLE: 'genFormStyleRange',
  SPEED: 'genFormSpeedRange',
  SPEAKER_BOOST: 'genFormSpeakerBoost',
};

// Helper to get cached value or default
const getCachedOrDefault = <T,>(key: string, defaultValue: T): T => {
  try {
    const cached = sessionStorage.getItem(key);
    if (cached !== null) {
      return JSON.parse(cached) as T;
    }
  } catch (e) {
    console.error(`Error reading session storage key "${key}":`, e);
    sessionStorage.removeItem(key); // Clear corrupted item
  }
  return defaultValue;
};

// Helper to calculate midpoint position as percentage
const calculateMidpointPercent = (range: [number, number], sliderMin: number, sliderMax: number): number => {
  const midpoint = (range[0] + range[1]) / 2;
  const totalRange = sliderMax - sliderMin;
  if (totalRange === 0) return 50; // Avoid division by zero, center if range is 0
  return ((midpoint - sliderMin) / totalRange) * 100;
}

const GenerationForm: React.FC<GenerationFormProps> = ({ selectedVoiceIds, onSubmit, isSubmitting, onRangesChange }) => {
  // Use Mantine Form for validation
  const form = useForm({
    initialValues: {
      skinName: 'MyNewSkin',
      variants: 3,
      selectedVoScriptId: null as string | null,
      selectedModelId: DEFAULT_MODEL_ID,
      // Load initial values from session storage or use defaults
      stabilityRange: getCachedOrDefault<[number, number]>(SESSION_STORAGE_KEYS.STABILITY, DEFAULT_STABILITY_RANGE),
      similarityRange: getCachedOrDefault<[number, number]>(SESSION_STORAGE_KEYS.SIMILARITY, DEFAULT_SIMILARITY_RANGE),
      styleRange: getCachedOrDefault<[number, number]>(SESSION_STORAGE_KEYS.STYLE, DEFAULT_STYLE_RANGE),
      speedRange: getCachedOrDefault<[number, number]>(SESSION_STORAGE_KEYS.SPEED, DEFAULT_SPEED_RANGE),
      speakerBoost: getCachedOrDefault<boolean>(SESSION_STORAGE_KEYS.SPEAKER_BOOST, DEFAULT_SPEAKER_BOOST),
    },
    validate: {
      skinName: isNotEmpty('Skin Name is required'),
      variants: (value) => (value <= 0 ? 'Takes must be at least 1' : null),
      selectedVoScriptId: isNotEmpty('Please select a VO script'),
      // Add range validation if needed
    },
    validateInputOnBlur: true,
  });

  // VO Script State (RENAMED)
  const [availableVoScripts, setAvailableVoScripts] = useState<VoScriptListItem[]>([]);
  const [voScriptsLoading, setVoScriptsLoading] = useState<boolean>(false);
  const [voScriptsError, setVoScriptsError] = useState<string | null>(null);

  // Model State (keep separate)
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
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
                 form.setFieldValue('selectedModelId', models[0]?.model_id || ''); // Select first available if default missing
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

  // Fetch available VO scripts on mount (UPDATED)
  useEffect(() => {
    setVoScriptsLoading(true);
    setVoScriptsError(null);
    api.listVoScripts() // Use new API function
      .then(voScripts => {
        setAvailableVoScripts(voScripts);
        // Reset selection if current one disappears?
        if (form.values.selectedVoScriptId && !voScripts.find(s => s.id.toString() === form.values.selectedVoScriptId)) {
          form.setFieldValue('selectedVoScriptId', null);
        }
      })
      .catch(err => {
        setVoScriptsError(`Failed to load VO scripts: ${err.message}`);
        console.error(err);
      })
      .finally(() => setVoScriptsLoading(false));
  }, []);

  // --- Session Storage & Callback Effect ---
  // Combine saving to session storage and calling the callback
  useEffect(() => {
    const currentRanges = {
      stabilityRange: form.values.stabilityRange,
      similarityRange: form.values.similarityRange,
      styleRange: form.values.styleRange,
      speedRange: form.values.speedRange,
      speakerBoost: form.values.speakerBoost,
    };
    sessionStorage.setItem(SESSION_STORAGE_KEYS.STABILITY, JSON.stringify(currentRanges.stabilityRange));
    sessionStorage.setItem(SESSION_STORAGE_KEYS.SIMILARITY, JSON.stringify(currentRanges.similarityRange));
    sessionStorage.setItem(SESSION_STORAGE_KEYS.STYLE, JSON.stringify(currentRanges.styleRange));
    sessionStorage.setItem(SESSION_STORAGE_KEYS.SPEED, JSON.stringify(currentRanges.speedRange));
    sessionStorage.setItem(SESSION_STORAGE_KEYS.SPEAKER_BOOST, JSON.stringify(currentRanges.speakerBoost));
    
    // Call the callback function if provided
    onRangesChange?.(currentRanges);

  }, [
    form.values.stabilityRange, 
    form.values.similarityRange, 
    form.values.styleRange, 
    form.values.speedRange, 
    form.values.speakerBoost, 
    onRangesChange // Include callback in dependency array
  ]);

  // Handle form submission (UPDATED)
  const handleFormSubmit = (values: typeof form.values) => {
    // Add validation for selected voices again just before submit
    if (selectedVoiceIds.length === 0) {
        form.setFieldError('selectedVoiceIds', 'Please select at least one voice');
        return; 
    }

    // Build config from validated form values
    const finalConfig: GenerationConfig = {
      skin_name: values.skinName,
      voice_ids: selectedVoiceIds,
      variants_per_line: values.variants,
      stability_range: values.stabilityRange,
      similarity_boost_range: values.similarityRange,
      style_range: values.styleRange,
      speed_range: values.speedRange,
      use_speaker_boost: values.speakerBoost,
      model_id: values.selectedModelId,
      vo_script_id: parseInt(values.selectedVoScriptId!, 10), // Use vo_script_id
    };

    onSubmit(finalConfig);
  };

  // Helper to format slider value
  const formatSliderValue = (value: number) => value.toFixed(2);

  return (
    // Use Mantine form
    <form onSubmit={form.onSubmit(handleFormSubmit)} style={{ border: '1px solid #ccc', padding: '15px', marginTop: '15px' }}>
      <h4>Generation Parameters:</h4>
       {/* Display overall form error if needed, or rely on field errors */}
       {/* {form.errors && <Text color="red">Please fix errors</Text>} */}
       
      {/* Use Mantine TextInput */}
      <TextInput
        label="Skin Name"
        placeholder="Enter a name for this skin/batch"
        required
        {...form.getInputProps('skinName')}
      />
      {/* Use Mantine NumberInput */}
      <NumberInput
        label="Takes per Line"
        placeholder="Number of takes per script line"
        required
        min={1}
        mt="md"
        {...form.getInputProps('variants')}
      />

      {/* VO Script Select (UPDATED) */}
      <Select
          label="Select VO Script" // UPDATED Label
          placeholder="Choose a VO script..."
          required
          data={availableVoScripts.map(script => ({
            value: script.id.toString(),
            // Adjust label as needed based on VoScriptListItem type fields
            label: `${script.name} (Status: ${script.status}, Updated: ${new Date(script.updated_at).toLocaleDateString()})` 
          }))}
          searchable
          nothingFoundMessage={voScriptsLoading ? "Loading VO scripts..." : voScriptsError ? "Error loading VO scripts" : "No VO scripts found"}
          disabled={voScriptsLoading || !!voScriptsError}
          error={voScriptsError || form.errors.selectedVoScriptId} // Use new state/form prop
          mt="md"
          {...form.getInputProps('selectedVoScriptId')} // Use new form prop
        />

      {/* Use Mantine Select for Model */}
      <Select 
            label="Model"
            placeholder="Select a model..."
            required
            mt="md"
            value={form.values.selectedModelId} 
            onChange={(_value) => form.setFieldValue('selectedModelId', _value || DEFAULT_MODEL_ID)} 
            disabled={modelsLoading || !!modelsError}
            data={availableModels.map(model => (
                { value: model.model_id, label: `${model.name} (${model.model_id})` }
            ))}
             nothingFoundMessage={modelsLoading ? "Loading models..." : modelsError ? "Error loading models" : "No models found"}
             error={modelsError}
            // {...form.getInputProps('selectedModelId')}
        />

      <div style={{ marginTop: '20px', paddingTop: '15px', borderTop: '1px solid #eee' }}>
          <h5>Voice Setting Ranges (Randomized per Take):</h5>
          
          {/* --- Stability Slider --- */}
          <Box style={{ position: 'relative', marginBottom: '15px', padding: '0 10px', paddingBottom: '10px' }}>
              <Text size="sm">Stability Range: [{formatSliderValue(form.values.stabilityRange[0])} - {formatSliderValue(form.values.stabilityRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.stabilityRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('stabilityRange', value as [number, number])} 
              />
              {/* Midpoint Marker */}
              <Box style={{
                  position: 'absolute',
                  left: `${calculateMidpointPercent(form.values.stabilityRange, 0, 1)}%`,
                  top: 'calc(50% + 4px)',
                  width: '2px',
                  height: '10px',
                  backgroundColor: 'grey',
                  transform: 'translateX(-50%)',
                  zIndex: 1, 
                  pointerEvents: 'none', 
              }} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">More Variable</Text><Text size="xs">More Stable</Text></div>
          </Box>
          
          {/* --- Similarity Slider --- */}
          <Box style={{ position: 'relative', marginBottom: '15px', padding: '0 10px', paddingBottom: '10px' }}>
              <Text size="sm">Similarity Boost Range: [{formatSliderValue(form.values.similarityRange[0])} - {formatSliderValue(form.values.similarityRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.similarityRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('similarityRange', value as [number, number])} 
              />
               {/* Midpoint Marker */}
              <Box style={{
                  position: 'absolute',
                  left: `${calculateMidpointPercent(form.values.similarityRange, 0, 1)}%`,
                  top: 'calc(50% + 4px)', 
                  width: '2px',
                  height: '10px',
                  backgroundColor: 'grey',
                  transform: 'translateX(-50%)',
                  zIndex: 1,
                  pointerEvents: 'none',
              }} />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">Low</Text><Text size="xs">High</Text></div>
          </Box>

          {/* --- Style Exaggeration Slider --- */}
          <Box style={{ position: 'relative', marginBottom: '15px', padding: '0 10px', paddingBottom: '10px' }}>
              <Text size="sm">Style Exaggeration Range: [{formatSliderValue(form.values.styleRange[0])} - {formatSliderValue(form.values.styleRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.styleRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('styleRange', value as [number, number])} 
              />
               {/* Midpoint Marker */}
              <Box style={{
                  position: 'absolute',
                  left: `${calculateMidpointPercent(form.values.styleRange, 0, 1)}%`,
                  top: 'calc(50% + 4px)',
                  width: '2px',
                  height: '10px',
                  backgroundColor: 'grey',
                  transform: 'translateX(-50%)',
                  zIndex: 1,
                  pointerEvents: 'none',
              }} />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">None</Text><Text size="xs">Exaggerated</Text></div>
          </Box>

          {/* --- Speed Slider --- */}
          <Box style={{ position: 'relative', marginBottom: '15px', padding: '0 10px', paddingBottom: '10px' }}>
              <Text size="sm">Speed Range: [{formatSliderValue(form.values.speedRange[0])} - {formatSliderValue(form.values.speedRange[1])}]</Text>
              <Slider 
                  range min={0.5} max={2.0} step={0.05} allowCross={false}
                  value={form.values.speedRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('speedRange', value as [number, number])} 
              />
               {/* Midpoint Marker */}
              <Box style={{
                  position: 'absolute',
                  left: `${calculateMidpointPercent(form.values.speedRange, 0.5, 2.0)}%`,
                  top: 'calc(50% + 4px)',
                  width: '2px',
                  height: '10px',
                  backgroundColor: 'grey',
                  transform: 'translateX(-50%)',
                  zIndex: 1,
                  pointerEvents: 'none',
              }} />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">Slower</Text><Text size="xs">Faster</Text></div>
          </Box>

          {/* Use Mantine Checkbox */}
           <Checkbox
            mt="md"
            label="Speaker Boost (Fixed for all takes in job)"
            {...form.getInputProps('speakerBoost', { type: 'checkbox' })}
           />
      </div>
      
      {/* Use Mantine Button - disabled state handled by form validity */}
      <Button type="submit" loading={isSubmitting} mt="lg">
        Start Generation Job
      </Button>
       {/* Add voice selection error message if needed */} 
       {form.errors.selectedVoiceIds && <Text color="red" size="sm" mt="xs">{form.errors.selectedVoiceIds}</Text>}
    </form>
  );
};

export default GenerationForm; 