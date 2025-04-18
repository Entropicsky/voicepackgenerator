import React, { useState, useEffect } from 'react';
import { GenerationConfig, Take, ModelOption } from '../../types';
import { api } from '../../api';
import Slider from 'rc-slider'; // Assuming rc-slider is installed
import 'rc-slider/assets/index.css';

interface RegenerationModalProps {
  batchId: string;
  lineKey: string;
  currentTakes: Take[]; // Pass current takes to get initial text
  onClose: () => void;
  onRegenJobStarted: (lineKey: string, taskId: string) => void; 
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
    batchId, lineKey, currentTakes, onClose, onRegenJobStarted 
}) => {
  const [lineText, setLineText] = useState<string>('');
  const [numTakes, setNumTakes] = useState<number>(DEFAULT_NUM_TAKES);
  const [replaceExisting, setReplaceExisting] = useState<boolean>(false);
  
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
        const response = await api.regenerateLineTakes(batchId, {
            line_key: lineKey,
            line_text: lineText,
            num_new_takes: numTakes,
            settings: settingsPayload,
            replace_existing: replaceExisting
        });
        console.log(`Line regeneration job submitted: DB ID ${response.job_id}, Task ID ${response.task_id}`);
        onRegenJobStarted(lineKey, response.task_id);
        onClose(); // Close modal on success
    } catch (err: any) {
        console.error("Failed to submit regeneration job:", err);
        setError(`Submission failed: ${err.message}`);
    } finally {
        setIsSubmitting(false);
    }
  };

  // --- Styles --- (Simplified for brevity)
  const modalStyle: React.CSSProperties = {
      position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
      backgroundColor: 'white', padding: '20px 40px', borderRadius: '8px', 
      boxShadow: '0 4px 15px rgba(0,0,0,0.2)', zIndex: 1000, width: '600px', maxHeight: '90vh', overflowY: 'auto'
  };
  const overlayStyle: React.CSSProperties = {
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
      backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 999
  };
  const formatSliderValue = (value: number) => value.toFixed(2);

  return (
    <div style={overlayStyle} onClick={onClose}> {/* Close on overlay click */} 
      <div style={modalStyle} onClick={(e) => e.stopPropagation()}> {/* Prevent closing when clicking inside modal */} 
        <h3>Regenerate Takes for Line: "{lineKey}"</h3>
        <form onSubmit={handleSubmit}>
            {/* Line Text */} 
            <div style={{ marginBottom: '15px' }}>
                <label htmlFor="lineText">Line Text:</label><br/>
                <textarea 
                    id="lineText" 
                    value={lineText} 
                    onChange={e => setLineText(e.target.value)}
                    rows={3} 
                    style={{ width: '100%', boxSizing: 'border-box' }}
                    required
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
            {error && <p style={{ color: 'red' }}>Error: {error}</p>}
            
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
      </div>
    </div>
  );
};

export default RegenerationModal; 