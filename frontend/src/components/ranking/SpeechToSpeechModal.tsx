import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { VoiceOption, ModelOption, SpeechToSpeechPayload } from '../../types';
import { api } from '../../api';
import { Button, Select, TextInput, Checkbox, Text, Loader, Alert } from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
import AppModal from '../common/AppModal';

interface SpeechToSpeechModalProps {
  scriptId: number;
  batchId: string;
  lineKey: string;
  onClose: () => void;
  onRegenJobStarted: (lineKey: string, taskId: string) => void;
  opened: boolean;
}

// Defaults
const DEFAULT_NUM_TAKES = 3;
const DEFAULT_STS_MODEL_ID = "eleven_multilingual_sts_v2"; // Default STS model
const DEFAULT_STABILITY = 0.5;
const DEFAULT_SIMILARITY = 0.9;

const SpeechToSpeechModal: React.FC<SpeechToSpeechModalProps> = ({ 
    scriptId,
    batchId, lineKey, onClose, onRegenJobStarted, opened 
}) => {
  const [sourceAudioFile, setSourceAudioFile] = useState<File | null>(null);
  const [fileAudioB64, setFileAudioB64] = useState<string | null>(null);
  const [numTakes, setNumTakes] = useState<number>(DEFAULT_NUM_TAKES);
  const [replaceExisting, setReplaceExisting] = useState<boolean>(false);

  // Target Voice State
  const [availableVoices, setAvailableVoices] = useState<VoiceOption[]>([]);
  const [targetVoiceId, setTargetVoiceId] = useState<string>('');
  const [voicesLoading, setVoicesLoading] = useState<boolean>(true);
  const [voicesError, setVoicesError] = useState<string | null>(null);

  // STS Model State
  const [availableModels, setAvailableModels] = useState<ModelOption[]>([]);
  const [selectedModelId, setSelectedModelId] = useState<string>(DEFAULT_STS_MODEL_ID);
  const [modelsLoading, setModelsLoading] = useState<boolean>(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  // STS Settings State
  const [stability, setStability] = useState<number>(DEFAULT_STABILITY);
  const [similarity, setSimilarity] = useState<number>(DEFAULT_SIMILARITY);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Mic recording state
  const [recordingState, setRecordingState] = useState<'idle' | 'recording' | 'recorded' | 'error'>('idle');
  const [recordedAudioBlob, setRecordedAudioBlob] = useState<Blob | null>(null);
  const [recordedAudioB64, setRecordedAudioB64] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioStreamRef = useRef<MediaStream | null>(null);

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

  // Fetch Voices
  useEffect(() => {
    api.getVoices()
       .then(voices => {
           setAvailableVoices(voices);
           if (voices.length > 0) setTargetVoiceId(voices[0].voice_id); // Default to first voice
       })
       .catch(err => setVoicesError(`Failed to load voices: ${err.message}`))
       .finally(() => setVoicesLoading(false));
  }, []);

  // Fetch STS Models
  useEffect(() => {
    console.log("[SpeechToSpeechModal] Fetching models with capability: 'sts'"); // Log intent
    api.getModels({ capability: 'sts' })
       .then(models => {
           console.log("[SpeechToSpeechModal] Received models:", models); // Log received data
           setAvailableModels(models);
           if (!models.find(m => m.model_id === DEFAULT_STS_MODEL_ID) && models.length > 0) {
               console.log("[SpeechToSpeechModal] Default STS model not found, using first available.");
               setSelectedModelId(models[0].model_id);
           } else if (models.length === 0) {
                console.log("[SpeechToSpeechModal] No STS models found.");
                setSelectedModelId('');
                setModelsError("No suitable Speech-to-Speech models found in your account.");
           } else {
               // Default model was found or already set
               setSelectedModelId(DEFAULT_STS_MODEL_ID);
           }
       })
       .catch(err => {
            console.error("[SpeechToSpeechModal] Error fetching STS models:", err);
            setModelsError(`Failed to load STS models: ${err.message}`)
       })
       .finally(() => setModelsLoading(false));
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Clear recording if a file is selected
    clearRecording(); 
    setSourceAudioFile(file || null);
    setFileAudioB64(null); 
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            setFileAudioB64(e.target?.result as string);
        };
        reader.onerror = () => {
            setSubmitError('Error reading audio file.');
        };
        reader.readAsDataURL(file); // Read as base64 data URL
    } 
  };

  const startRecording = async () => {
    setSubmitError(null);
    clearRecording(); // Clear previous recording/file
    setSourceAudioFile(null); 
    setFileAudioB64(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = []; // Reset chunks

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' }); // Or determine mime type
        setRecordedAudioBlob(audioBlob);
        // Convert Blob to Base64 Data URL
        const reader = new FileReader();
        reader.onload = (e) => {
            setRecordedAudioB64(e.target?.result as string);
            setRecordingState('recorded');
            console.log("Recording finished and converted to base64.");
        };
        reader.onerror = () => {
            setSubmitError('Error converting recording to base64.');
            setRecordingState('error');
        };
        reader.readAsDataURL(audioBlob);
      };

      mediaRecorderRef.current.start();
      setRecordingState('recording');
      console.log("Recording started");

    } catch (err) {
      console.error("Error accessing microphone:", err);
      setSubmitError('Could not access microphone. Please ensure permission is granted.');
      setRecordingState('error');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recordingState === 'recording') {
      mediaRecorderRef.current.stop();
      // Stop microphone access tracks
      audioStreamRef.current?.getTracks().forEach(track => track.stop());
      audioStreamRef.current = null;
      console.log("Recording stopped by user.");
      // State will be set to 'recorded' in onstop handler
    }
  };

  const clearRecording = () => {
       setRecordedAudioBlob(null);
       setRecordedAudioB64(null);
       setRecordingState('idle');
       if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
           stopRecording(); // Ensure recorder stops if cleared while recording
       }
  };

  // Cleanup effect
   useEffect(() => {
    // Stop recording if component unmounts while recording
    return () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        stopRecording();
      }
    };
  }, []); // Empty dependency array means run only on mount/unmount

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    
    const audioToSubmitB64 = recordedAudioB64 || fileAudioB64;
    
    if (!audioToSubmitB64) { setSubmitError("Please upload or record source audio."); return; }
    if (!targetVoiceId) { setSubmitError("Please select a target voice."); return; }
    if (!selectedModelId) { setSubmitError("Please select an STS model."); return; }
    if (numTakes <= 0) { setSubmitError("Number of takes must be > 0."); return; }

    setIsSubmitting(true);
    const payload: SpeechToSpeechPayload = {
        line_key: lineKey,
        source_audio_data: audioToSubmitB64,
        num_new_takes: numTakes,
        target_voice_id: targetVoiceId,
        model_id: selectedModelId,
        settings: { stability, similarity_boost: similarity },
        replace_existing: replaceExisting
    };

    try {
        console.log("SpeechToSpeechModal: Starting STS job...");
        const response = await api.startSpeechToSpeech(scriptId, batchId, payload);
        console.log("SpeechToSpeechModal: Got API response:", response);
        
        if (!response.task_id) {
            console.error("SpeechToSpeechModal: Received response without task_id!");
            setSubmitError("Failed to start STS: Missing task ID in response");
            setIsSubmitting(false);
            return;
        }
        
        console.log(`SpeechToSpeechModal: Calling onRegenJobStarted with lineKey=${lineKey}, taskId=${response.task_id}`);
        onRegenJobStarted(lineKey, response.task_id);
        
        console.log("SpeechToSpeechModal: Closing modal");
        onClose();
    } catch (err: any) {
        console.error("SpeechToSpeechModal: Failed to submit STS job:", err);
        setSubmitError(`Submission failed: ${err.message}`);
    } finally {
        setIsSubmitting(false);
    }
  };
  
  // --- Styles --- 
  const formatSliderValue = (v: number) => v.toFixed(2);

  return (
    <AppModal
      opened={opened}
      onClose={onClose}
      title={`Speech-to-Speech for Line: "${lineKey}"`}
      size="lg"
      centered
      withinPortal={false}
    >
        <form onSubmit={handleSubmit}>
          {/* Source Audio Input - Choose File OR Record */} 
          <div style={{ marginBottom: '15px', border: '1px dashed grey', padding: '10px' }}>
                <label>Source Audio:</label>
                {/* File Input */}  
                <div style={{marginTop: '5px'}}>
                    <input 
                        type="file" id="sourceAudio" accept="audio/*" 
                        onChange={handleFileChange} 
                        disabled={recordingState === 'recording'}
                    />
                    {sourceAudioFile && !recordedAudioB64 && <small> ({sourceAudioFile.name})</small>}
                </div>
                <div style={{textAlign: 'center', margin: '5px 0'}}>OR</div>
                {/* Mic Recording */}  
                <div>
                    {recordingState === 'idle' && <button type="button" onClick={startRecording}>Start Recording</button>}
                    {recordingState === 'recording' && <button type="button" onClick={stopRecording}>Stop Recording</button>}
                    {recordingState === 'error' && <span style={{color:'red'}}>Mic Error</span>}
                    {recordingState === 'recorded' && (
                        <>
                            <span>Recording available</span> 
                            <button type="button" onClick={clearRecording} style={{marginLeft: '10px'}}>Clear Recording</button>
                            {/* Optional: Add playback for recorded audio */}  
                            {recordedAudioBlob && <audio controls src={URL.createObjectURL(recordedAudioBlob)} style={{verticalAlign: 'middle', marginLeft: '10px'}}></audio>}
                        </>
                    )}
                    {recordingState === 'recording' && <span style={{marginLeft: '10px', fontStyle: 'italic', color: 'red'}}>🔴 Recording...</span>}
                </div>
            </div>
            
            {/* Target Voice */} 
            <div style={{ marginBottom: '15px' }}>
                <label htmlFor="targetVoice">Target Voice:</label><br/>
                <select id="targetVoice" value={targetVoiceId} onChange={e => setTargetVoiceId(e.target.value)} disabled={voicesLoading || !!voicesError} required>
                   {voicesLoading && <option>Loading voices...</option>}
                   {voicesError && <option>Error loading voices</option>}
                   {!voicesLoading && !voicesError && availableVoices.map(v => <option key={v.voice_id} value={v.voice_id}>{v.name}</option>)}
                </select>
                {voicesError && <small style={{color: 'red', marginLeft: '5px'}}>{voicesError}</small>}
            </div>

            {/* STS Model */} 
            <div style={{ marginBottom: '15px' }}>
                <label htmlFor="stsModel">STS Model:</label><br/>
                <select id="stsModel" value={selectedModelId} onChange={e => setSelectedModelId(e.target.value)} disabled={modelsLoading || !!modelsError} required>
                   {modelsLoading && <option>Loading models...</option>}
                   {modelsError && <option>Error loading models</option>}
                   {!modelsLoading && !modelsError && availableModels.map(m => <option key={m.model_id} value={m.model_id}>{m.name}</option>)}
                </select>
                {modelsError && <small style={{color: 'red', marginLeft: '5px'}}>{modelsError}</small>}
            </div>

            {/* Number of Takes */} 
            <div style={{ marginBottom: '15px' }}>
                <label htmlFor="numTakesSts">Number of Takes:</label> 
                <input type="number" id="numTakesSts" value={numTakes} onChange={e => setNumTakes(parseInt(e.target.value, 10) || 1)} min="1" required style={{width: '60px'}}/>
            </div>

            {/* Replace Option */} 
             <div style={{ marginBottom: '15px' }}>
                  <input type="checkbox" id="replaceExistingSts" checked={replaceExisting} onChange={e => setReplaceExisting(e.target.checked)} />
                  <label htmlFor="replaceExistingSts"> Replace existing takes for this line</label>
              </div>

            {/* STS Settings */} 
            <h5>Target Voice Settings:</h5>
            <div style={{ marginBottom: '15px', padding: '0 5px' }}>
                <label>Stability: [{formatSliderValue(stability)}]</label>
                <Slider min={0} max={1} step={0.01} value={stability} onChange={(v: number | number[]) => setStability(v as number)} />
                <div style={{display: 'flex', justifyContent: 'space-between'}}><small>More Variable</small><small>More Stable</small></div>
            </div>
            <div style={{ marginBottom: '15px', padding: '0 5px' }}>
                <label>Similarity Boost: [{formatSliderValue(similarity)}]</label>
                <Slider min={0} max={1} step={0.01} value={similarity} onChange={(v: number | number[]) => setSimilarity(v as number)} />
                <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Low</small><small>High</small></div>
            </div>
            
            {submitError && <p style={{ color: 'red' }}>Error: {submitError}</p>}
              
            {/* Actions */} 
            <div style={{ marginTop: '20px', textAlign: 'right' }}>
                <button type="button" onClick={onClose} style={{ marginRight: '10px' }} disabled={isSubmitting}>Cancel</button>
                <button type="submit" disabled={isSubmitting || !(recordedAudioB64 || fileAudioB64) || !targetVoiceId || !selectedModelId}>
                    {isSubmitting ? 'Generating STS...' : 'Start STS Job'}
                </button>
            </div>
          </form>
    </AppModal>
  );
};

export default SpeechToSpeechModal; 