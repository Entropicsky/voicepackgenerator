import React, { useState, useEffect, useRef, useCallback } from 'react';
import { GenerationConfig, Take, ModelOption } from '../../types';
import { api } from '../../api';
import Slider from 'rc-slider'; // Assuming rc-slider is installed
import 'rc-slider/assets/index.css';
import { Checkbox, Button, Textarea, TextInput, Text, Alert, Tabs } from '@mantine/core'; // Import Checkbox and other components
import { IconAlertCircle } from '@tabler/icons-react';
import AppModal from '../common/AppModal';

interface RegenerationModalProps {
  batchId: string;
  lineKey: string;
  currentTakes: Take[]; // Pass current takes to get initial text
  onClose: () => void;
  onRegenJobStarted: (lineKey: string, taskId: string) => void; 
  opened: boolean; // Add opened prop
}

// Defaults for the modal form
const DEFAULT_NUM_TAKES = 5;
const DEFAULT_STABILITY_RANGE: [number, number] = [0.5, 0.75];
const DEFAULT_SIMILARITY_RANGE: [number, number] = [0.75, 0.9];
const DEFAULT_STYLE_RANGE: [number, number] = [0.0, 0.45];
const DEFAULT_SPEED_RANGE: [number, number] = [0.95, 1.05];
const DEFAULT_SPEAKER_BOOST = true;
const DEFAULT_MODEL_ID = "eleven_multilingual_v2";

const RegenerationModal: React.FC<RegenerationModalProps> = ({ 
    batchId, lineKey, currentTakes, onClose, onRegenJobStarted, opened // Destructure opened prop
}) => {
  const [lineText, setLineText] = useState<string>('');
  const [numTakes, setNumTakes] = useState<number>(DEFAULT_NUM_TAKES);
  const [replaceExisting, setReplaceExisting] = useState<boolean>(false);
  const [updateScript, setUpdateScript] = useState<boolean>(false); // <-- New State
  
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

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null); // Add Ref
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false); // State for AI optimization loading
  const [optimizeError, setOptimizeError] = useState<string | null>(null); // State for AI optimization error

  // Effect to handle Escape key press for closing the modal
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    // Cleanup function to remove the event listener
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose]); // Dependency array ensures the latest onClose is used

  // Pre-fill text area with the script text from the first take of the current line
  useEffect(() => {
    if (currentTakes && currentTakes.length > 0) {
      setLineText(currentTakes[0].script_text || '');
    } else {
        setLineText('Error: Could not find original script text.'); // Handle case where takes might be empty
    }
  }, [currentTakes]);

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
        setModelsLoading(true);
        setModelsError(null);
        try {
            const models = await api.getModels();
            setAvailableModels(models);
            if (!models.find(m => m.model_id === DEFAULT_MODEL_ID)) {
                 setSelectedModelId(models[0]?.model_id || '');
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

  // NEW: Handler for the insert pause button
  const handleInsertPause = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const text = textarea.value;
      const pauseTag = '<break time="0.5s" />';
      const newText = text.substring(0, start) + pauseTag + text.substring(end);
      
      setLineText(newText);

      // Move cursor to after the inserted tag
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + pauseTag.length;
        textarea.focus();
      }, 0);
    }
  };

  // --- NEW: Handler for the AI Wizard button --- //
  const handleOptimizeText = async () => {
    setError(null); // Clear general error
    setOptimizeError(null); // Clear specific optimization error
    if (!lineText.trim()) {
        setOptimizeError("Cannot optimize empty text.");
        return;
    }
    setIsOptimizing(true);
    console.log("Calling AI text optimization...");
    try {
        const response = await api.optimizeLineText(lineText);
        if (response && response.optimized_text) {
            console.log("Received optimized text: ", response.optimized_text);
            setLineText(response.optimized_text); // Update the text area state
            // Optionally clear the error if successful
            setOptimizeError(null); 
        } else {
             console.error("Optimization response missing optimized_text field.", response);
             setOptimizeError("Received invalid response from optimization service.");
        }
    } catch (err: any) {
        console.error("Failed to optimize text:", err);
        setOptimizeError(`Optimization failed: ${err.message}`);
    } finally {
        setIsOptimizing(false);
    }
  };
  // --- END NEW HANDLER --- //

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (numTakes <= 0) {
        setError("Number of takes must be greater than 0.");
        return;
    }
     if (!lineText.trim()) {
        setError("Line text cannot be empty.");
        return;
    }
    if (stabilityRange[0] > stabilityRange[1] || 
        similarityRange[0] > similarityRange[1] ||
        styleRange[0] > styleRange[1] ||
        speedRange[0] > speedRange[1]) {
        setError('Invalid range: Min value cannot be greater than Max value.');
        return;
    }

    setIsSubmitting(true);

    const settingsPayload: Partial<GenerationConfig> = {
        stability_range: stabilityRange,
        similarity_boost_range: similarityRange,
        style_range: styleRange,
        speed_range: speedRange,
        use_speaker_boost: speakerBoost,
        model_id: selectedModelId
    };

    try {
        console.log("RegenerationModal: Submitting regeneration request to API...");
        const response = await api.regenerateLineTakes(batchId, {
            line_key: lineKey,
            line_text: lineText,
            num_new_takes: numTakes,
            settings: settingsPayload,
            replace_existing: replaceExisting,
            update_script: updateScript // <-- Pass the flag
        });
        console.log("RegenerationModal: Received API response:", response);
        console.log(`RegenerationModal: Task ID = ${response.taskId}, Job ID = ${response.jobId}`);
        
        // Check if taskId is defined before calling the callback
        if (!response.taskId) {
            console.error("RegenerationModal: taskId is undefined in API response!");
            setError("Failed to start regeneration: Missing task ID in response");
            setIsSubmitting(false);
            return;
        }
        
        console.log(`RegenerationModal: Calling onRegenJobStarted with lineKey=${lineKey}, taskId=${response.taskId}`);
        onRegenJobStarted(lineKey, response.taskId);
        onClose(); // Close modal on success
    } catch (err: any) {
        console.error("Failed to submit regeneration job:", err);
        setError(`Submission failed: ${err.message}`);
    } finally {
        setIsSubmitting(false);
    }
  };

  // --- Styles --- (Simplified for brevity)
  const overlayStyle: React.CSSProperties = {
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
      backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 999
  };
  const formatSliderValue = (value: number) => value.toFixed(2);

  return (
    <AppModal
      opened={opened} // Use the passed prop
      onClose={onClose}
      title={`Regenerate Takes for Line: "${lineKey}"`} // Add title prop
      size="lg" // Add size prop
      centered // Add centered prop
      withinPortal={false}
    >
        {/* The form is the direct child */}
        <form onSubmit={handleSubmit}>
          {/* Line Text - MODIFIED */} 
          <div style={{ marginBottom: '5px' }}> 
              {/* Use HStack for Label + Button */} 
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}> 
                <label htmlFor="lineText">Line Text:</label>
                {/* Group the buttons together */} 
                <div style={{ display: 'flex', gap: '5px' }}> 
                  <button 
                     type="button" 
                     onClick={handleInsertPause} 
                     style={{padding: '2px 5px', fontSize: '0.8em'}} 
                     disabled={isOptimizing || isSubmitting} // Disable if optimizing or submitting
                     title="Insert a 0.5 second pause tag at cursor position"
                  >
                    + 0.5s Pause
                  </button>
                  <button 
                     type="button" 
                     onClick={handleOptimizeText} 
                     style={{padding: '2px 5px', fontSize: '0.8em'}}
                     disabled={isOptimizing || isSubmitting} // Disable if optimizing or submitting
                     title="Use AI to optimize this line for ElevenLabs based on scripthelp.md guidelines"
                  >
                    {isOptimizing ? '✨ Optimizing...' : '✨ AI Wizard'}
                  </button>
                </div>
              </div>
              <textarea 
                  id="lineText" 
                  ref={textareaRef} // Add ref
                  value={lineText} 
                  onChange={e => setLineText(e.target.value)}
                  rows={3} 
                  style={{ width: '100%', boxSizing: 'border-box', marginTop: '5px' }} 
                  required 
              /> 
          </div>
            
          {/* NEW: Update Script Checkbox */} 
          <div style={{ marginBottom: '15px' }}> 
              <Checkbox
                  id="updateScriptCheckbox"
                  label="Update this line in the original script"
                  checked={updateScript}
                  onChange={(event) => setUpdateScript(event.currentTarget.checked)}
              />
          </div>
            
          {/* Number of Takes */} 
          <div style={{ marginBottom: '15px' }}> 
              <label htmlFor="numTakes">Number of New Takes: </label> 
              <input 
                  type="number" id="numTakes" value={numTakes} 
                  onChange={e => setNumTakes(parseInt(e.target.value, 10) || 1)} 
                  min="1" style={{ width: '60px' }} 
                  required 
              /> 
          </div>
            
          {/* Replace/Add Option */} 
          <div style={{ marginBottom: '15px' }}> 
              <input 
                  type="checkbox" id="replaceExisting" 
                  checked={replaceExisting} onChange={e => setReplaceExisting(e.target.checked)}
              />
              <label htmlFor="replaceExisting"> Replace existing takes for this line (archives old files)</label>
          </div>

          {/* TTS Settings */} 
          <h5>Voice Setting Ranges (Randomized per Take):</h5>
           {/* Stability */} 
          <div style={{ marginBottom: '15px', padding: '0 5px' }}> 
              <label>Stability: [{formatSliderValue(stabilityRange[0])} - {formatSliderValue(stabilityRange[1])}]</label>
              <Slider range min={0} max={1} step={0.01} value={stabilityRange} onChange={(v: number | number[]) => setStabilityRange(v as [number,number])} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Variable</small><small>Stable</small></div>
          </div>
           {/* Similarity */} 
          <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Similarity: [{formatSliderValue(similarityRange[0])} - {formatSliderValue(similarityRange[1])}]</label>
              <Slider range min={0} max={1} step={0.01} value={similarityRange} onChange={(v: number | number[]) => setSimilarityRange(v as [number,number])} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Low</small><small>High</small></div>
          </div>
          {/* Style */} 
          <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Style Exag.: [{formatSliderValue(styleRange[0])} - {formatSliderValue(styleRange[1])}]</label>
              <Slider range min={0} max={1} step={0.01} value={styleRange} onChange={(v: number | number[]) => setStyleRange(v as [number,number])} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>None</small><small>Exaggerated</small></div>
          </div>
          {/* Speed */} 
          <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Speed: [{formatSliderValue(speedRange[0])} - {formatSliderValue(speedRange[1])}]</label>
              <Slider range min={0.5} max={2.0} step={0.05} value={speedRange} onChange={(v: number | number[]) => setSpeedRange(v as [number,number])} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Slower</small><small>Faster</small></div>
          </div>
          {/* Speaker Boost */} 
          <div style={{ marginBottom: '15px' }}>
              <input type="checkbox" id="modalSpeakerBoost" checked={speakerBoost} onChange={e => setSpeakerBoost(e.target.checked)} />
              <label htmlFor="modalSpeakerBoost"> Speaker Boost</label>
          </div>
          {/* Model Selection */} 
           <div style={{ marginBottom: '15px' }}>
              <label htmlFor="modalModelSelect">Model: </label>
              <select 
                  id="modalModelSelect" 
                  value={selectedModelId} 
                  onChange={e => setSelectedModelId(e.target.value)} 
                  disabled={modelsLoading || !!modelsError}
              >
                  {modelsLoading && <option>Loading...</option>}
                  {modelsError && <option>Error</option>}
                  {!modelsLoading && !modelsError && availableModels.map(model => (
                      <option key={model.model_id} value={model.model_id}>
                          {model.name}
                      </option>
                  ))}
              </select>
              {modelsError && <span style={{ color: 'red', marginLeft: '10px' }}>{modelsError}</span>}
          </div>
          
          {/* Error Display */}
          {/* Display general submission error */}
          {error && <p style={{ color: 'red', marginTop: '10px' }}>Error: {error}</p>}
          {/* Display specific optimization error */}
          {optimizeError && <p style={{ color: 'orange', marginTop: '5px' }}>Optimization Note: {optimizeError}</p>}
          
          {/* Actions */}
          <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <button type="button" onClick={onClose} style={{ marginRight: '10px' }} disabled={isSubmitting}>
                  Cancel
              </button>
              <button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Submitting...' : 'Regenerate Line Takes'}
              </button>
          </div>
        </form>
    </AppModal>
  );
};

export default RegenerationModal; 