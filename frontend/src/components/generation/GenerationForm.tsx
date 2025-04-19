import React, { useState, useEffect } from 'react';
import { GenerationConfig, ModelOption, ScriptMetadata } from '../../types';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import { api } from '../../api';
import { Select, Button, TextInput, NumberInput, Checkbox, Text } from '@mantine/core';
import { useForm, isNotEmpty } from '@mantine/form';

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
  // Use Mantine Form for validation
  const form = useForm({
    initialValues: {
      skinName: 'MyNewSkin',
      variants: 3,
      selectedScriptId: null as string | null,
      selectedModelId: DEFAULT_MODEL_ID,
      stabilityRange: DEFAULT_STABILITY_RANGE,
      similarityRange: DEFAULT_SIMILARITY_RANGE,
      styleRange: DEFAULT_STYLE_RANGE,
      speedRange: DEFAULT_SPEED_RANGE,
      speakerBoost: DEFAULT_SPEAKER_BOOST,
    },
    validate: {
      skinName: isNotEmpty('Skin Name is required'),
      variants: (value) => (value <= 0 ? 'Takes must be at least 1' : null),
      selectedScriptId: isNotEmpty('Please select a script'),
      selectedVoiceIds: (value, values) => (selectedVoiceIds.length === 0 ? 'Please select at least one voice' : null),
      // Add range validation if needed
    },
    // Add a reference to selectedVoiceIds for validation purposes
    validateInputOnBlur: true,
  });

  // Script State (keep separate from form state for fetching)
  const [availableScripts, setAvailableScripts] = useState<ScriptMetadata[]>([]);
  const [scriptsLoading, setScriptsLoading] = useState<boolean>(false);
  const [scriptsError, setScriptsError] = useState<string | null>(null);

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

  // Fetch available scripts on mount
  useEffect(() => {
    setScriptsLoading(true);
    setScriptsError(null);
    api.listScripts(false)
      .then(scripts => {
        setAvailableScripts(scripts);
        // Reset selection if current one disappears?
        if (form.values.selectedScriptId && !scripts.find(s => s.id.toString() === form.values.selectedScriptId)) {
          form.setFieldValue('selectedScriptId', null);
        }
      })
      .catch(err => {
        setScriptsError(`Failed to load scripts: ${err.message}`);
        console.error(err);
      })
      .finally(() => setScriptsLoading(false));
  }, []);

  // Handle form submission
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
      script_id: parseInt(values.selectedScriptId!, 10), // Already validated not null
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

      {/* Use Mantine Select with consistent styling */}
      <Select
          label="Select Script"
          placeholder="Choose a script..."
          required
          data={availableScripts.map(script => ({
            value: script.id.toString(),
            label: `${script.name} (${script.line_count} lines, updated ${new Date(script.updated_at).toLocaleDateString()})`
          }))}
          searchable
          nothingFoundMessage={scriptsLoading ? "Loading scripts..." : scriptsError ? "Error loading scripts" : "No scripts found"}
          disabled={scriptsLoading || !!scriptsError}
          error={scriptsError || form.errors.selectedScriptId} // Show fetch error or validation error
          mt="md"
          {...form.getInputProps('selectedScriptId')}
          // Add style props for consistency if needed
          // styles={{ input: { borderColor: form.errors.selectedScriptId ? 'red' : undefined } }}
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
          
          {/* Use Text for labels */}
          {/* ... Slider components remain the same, but update state via form.setFieldValue ... */}
          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <Text size="sm">Stability Range: [{formatSliderValue(form.values.stabilityRange[0])} - {formatSliderValue(form.values.stabilityRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.stabilityRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('stabilityRange', value as [number, number])} 
              />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">More Variable</Text><Text size="xs">More Stable</Text></div>
          </div>
          {/* ... Repeat slider pattern for Similarity, Style, Speed using form.values and form.setFieldValue ... */}
          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <Text size="sm">Similarity Boost Range: [{formatSliderValue(form.values.similarityRange[0])} - {formatSliderValue(form.values.similarityRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.similarityRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('similarityRange', value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">Low</Text><Text size="xs">High</Text></div>
          </div>
          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <Text size="sm">Style Exaggeration Range: [{formatSliderValue(form.values.styleRange[0])} - {formatSliderValue(form.values.styleRange[1])}]</Text>
              <Slider 
                  range min={0} max={1} step={0.01} allowCross={false}
                  value={form.values.styleRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('styleRange', value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">None</Text><Text size="xs">Exaggerated</Text></div>
          </div>
          <div style={{ marginBottom: '15px', padding: '0 10px' }}>
              <Text size="sm">Speed Range: [{formatSliderValue(form.values.speedRange[0])} - {formatSliderValue(form.values.speedRange[1])}]</Text>
              <Slider 
                  range min={0.5} max={2.0} step={0.05} allowCross={false}
                  value={form.values.speedRange} 
                  onChange={(value: number | number[]) => form.setFieldValue('speedRange', value as [number, number])} 
              />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><Text size="xs">Slower</Text><Text size="xs">Faster</Text></div>
          </div>

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