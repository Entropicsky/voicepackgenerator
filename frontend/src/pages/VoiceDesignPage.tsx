import React, { useState, useCallback } from 'react';
import { api } from '../api';
import { 
    CreateVoicePreviewPayload, SaveVoicePayload, 
    RichVoicePreview 
} from '../types'; 
import Slider from 'rc-slider'; 
import 'rc-slider/assets/index.css';
// Consider using a notification library (like Mantine's) for feedback
// import { notifications } from '@mantine/notifications'; 
// Import the voice context hook
import { useVoiceContext } from '../contexts/VoiceContext'; 
// Import the new modal
import SaveVoiceNameModal from '../components/modals/SaveVoiceNameModal'; 
// Import Text component from Mantine for the counter
import { Text } from '@mantine/core';

const VoiceDesignPage: React.FC = () => {
  // --- State Variables ---
  
  // Config Inputs
  const [voiceDescription, setVoiceDescription] = useState<string>('');
  const [textToPreview, setTextToPreview] = useState<string>('');
  const [autoGenerateText, setAutoGenerateText] = useState<boolean>(false);
  const [loudness, setLoudness] = useState<number>(0.5);
  const [quality, setQuality] = useState<number>(0.9);
  const [guidanceScale, setGuidanceScale] = useState<number>(5);
  const [seed, setSeed] = useState<string>(''); // Store as string for input flexibility

  // Result / Workflow State - UPDATED
  const [currentPreviews, setCurrentPreviews] = useState<RichVoicePreview[]>([]); // Holds latest generation
  const [heldPreviews, setHeldPreviews] = useState<RichVoicePreview[]>([]); // Holds previews user wants to keep
  const [generatedText, setGeneratedText] = useState<string>(''); 
  // NEW: State for the naming/saving modal
  const [namingModalOpen, setNamingModalOpen] = useState<boolean>(false);
  const [previewToName, setPreviewToName] = useState<RichVoicePreview | null>(null);

  // UI State
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Get refetch function from context
  const { refetchVoices } = useVoiceContext(); 

  // --- Handlers ---

  const handleGeneratePreviews = async () => {
    setError(null);
    // --- NEW: Check description length FIRST ---
    if (voiceDescription.length > 800) {
      setError("Voice description cannot exceed 800 characters.");
      return;
    }
    // --- End New Check ---
    
    // Existing checks
    if (voiceDescription.length < 20) { // Keep lower bound check
      setError("Voice description must be at least 20 characters.");
      return;
    }
    if (!autoGenerateText && (textToPreview.length < 100 || textToPreview.length > 1000)) {
       setError("Preview text must be between 100 and 1000 characters (or use auto-generate).");
       return;
    }

    // --- Store the description used for THIS generation batch --- 
    const descriptionForThisBatch = voiceDescription;

    setIsGenerating(true);
    
    // Determine the text to send based on the checkbox
    const gettysburgStart = "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.";
    const textToSend = autoGenerateText ? gettysburgStart : textToPreview;
    
    const payload: CreateVoicePreviewPayload = {
      voice_description: descriptionForThisBatch, // Use stored description
      auto_generate_text: autoGenerateText,
      loudness: loudness,
      quality: quality,
      guidance_scale: guidanceScale,
      text: textToSend || "" // Ensure text is always a string, fallback to empty if needed
    };
    const seedNum = parseInt(seed, 10);
    if (!isNaN(seedNum) && seedNum >= 0) {
      payload.seed = seedNum;
    }

    try {
      // ADD DETAILED LOGGING HERE
      console.log("--- Sending to api.createVoicePreviews ---");
      console.log("Payload:", JSON.stringify(payload, null, 2));
      console.log(`Payload contains 'text' field: ${payload.hasOwnProperty('text')}`);
      console.log(`Value of 'text' field: ${payload.text}`);
      console.log(`Value of 'auto_generate_text' field: ${payload.auto_generate_text}`);
      console.log("-------------------------------------------");
      // END DETAILED LOGGING
      
      console.log("Sending payload:", payload); // Keep original log too
      const response = await api.createVoicePreviews(payload);
      
      // --- Augment previews with original description --- 
      const richPreviews: RichVoicePreview[] = (response.previews || []).map(preview => ({
          ...preview,
          originalDescription: descriptionForThisBatch 
      }));
      
      setCurrentPreviews(richPreviews); // Set state with augmented previews
      setGeneratedText(response.text || 'Text not returned.');
      console.log("Received and processed previews:", richPreviews);
    } catch (err: any) {
      console.error("Error generating previews:", err);
      setError(`Failed to generate previews: ${err.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  // NEW: Handler to move a preview from current to held
  const handleHoldPreview = (previewToHold: RichVoicePreview) => {
      setHeldPreviews(prev => {
          // Avoid adding duplicates if somehow clicked twice
          if (prev.some(p => p.generated_voice_id === previewToHold.generated_voice_id)) {
              return prev;
          }
          return [...prev, previewToHold];
      });
      // Remove from current previews
      setCurrentPreviews(prev => prev.filter(p => p.generated_voice_id !== previewToHold.generated_voice_id));
  };

  // NEW: Handler to discard a preview from either list
  const handleDiscardPreview = (previewToDiscardId: string, from: 'current' | 'held') => {
      if (from === 'current') {
          setCurrentPreviews(prev => prev.filter(p => p.generated_voice_id !== previewToDiscardId));
      } else {
          setHeldPreviews(prev => prev.filter(p => p.generated_voice_id !== previewToDiscardId));
          // If the discarded preview was the one about to be named, close modal
          if (previewToName?.generated_voice_id === previewToDiscardId) {
              setPreviewToName(null);
              setNamingModalOpen(false);
          }
      }
  };

  // NEW: Handler to open the naming modal
  const handleOpenNamingModal = (preview: RichVoicePreview) => {
      setPreviewToName(preview);
      setNamingModalOpen(true);
      setError(null); // Clear previous errors when opening modal
  };

  // MODIFIED: Save logic accepts preview and name from modal submit
  const handleSaveVoice = useCallback(async (previewToSave: RichVoicePreview, newName: string) => {
    setError(null); // Clear error state on new attempt
    setIsSaving(true); // Set saving state for modal button
    const payload: SaveVoicePayload = {
      generated_voice_id: previewToSave.generated_voice_id,
      voice_name: newName, // Name comes from modal
      voice_description: previewToSave.originalDescription, 
    };

    try {
      const savedVoice = await api.saveVoiceFromPreview(payload);
      console.log("Voice saved successfully:", savedVoice);
      alert(`Voice '${savedVoice.name}' (ID: ${savedVoice.voice_id}) saved successfully!`);
      
      console.log("[VoiceDesignPage] Triggering voice list refetch...");
      refetchVoices(); 
      
      // --- Update success logic --- 
      // Remove the saved preview from the held list
      setHeldPreviews(prev => prev.filter(p => p.generated_voice_id !== previewToSave.generated_voice_id));
      // Close the modal
      setNamingModalOpen(false);
      setPreviewToName(null);
      // Do NOT clear other state like current previews or form config

    } catch (err: any) {
      console.error("Error saving voice:", err);
      // Show error message (maybe inside the modal in future? For now, page level)
      setError(`Failed to save voice: ${err.message}`); 
      // Keep modal open on error? Or close? Let's close for now.
      setNamingModalOpen(false);
      setPreviewToName(null);
    } finally {
      setIsSaving(false); // Reset saving state
    }
    // Remove dependencies that are now passed as args
  }, [refetchVoices]); 

  // Helper to get playable audio source
  const getAudioSrc = (base64: string): string => {
    // Basic check - might need refinement based on actual base64 prefix
    if (base64.startsWith('data:audio')) return base64;
    // Assuming mp3 if no prefix - this might be incorrect, adjust as needed
    return `data:audio/mpeg;base64,${base64}`; 
  };
  
  const formatSliderValue = (v: number) => v.toFixed(2);

  // --- Render --- 
  return (
    <div style={{ width: '100%', maxWidth: '100%', padding: '0 20px' }}>
      <h2>Create Voices</h2>
      <div style={{ 
        display: 'flex', 
        gap: '20px', 
        flexWrap: 'nowrap', 
        minHeight: '650px',
        width: '100%'
      }}>
        
        {/* Left Column: Configuration */}
        <div style={{ 
          width: '35%', 
          minWidth: '350px', 
          border: '1px solid #eee', 
          padding: '20px', 
          borderRadius: '5px' 
        }}>
          <h4>1. Configure Voice</h4>

          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="voiceDesc">Voice Description (20-800 chars):</label><br/>
            <textarea 
              id="voiceDesc" 
              rows={4} 
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={voiceDescription}
              onChange={e => setVoiceDescription(e.target.value)}
              placeholder="e.g., An old British male with a raspy, deep voice. Professional, relaxed and assertive."
              maxLength={1000} // Keep a slightly higher textarea limit to allow typing, but validate at 800
            />
            <Text size="xs" ta="right" c={voiceDescription.length > 800 ? 'red' : 'dimmed'}>
              {voiceDescription.length} / 800
            </Text>
          </div>

          <div style={{ marginBottom: '15px' }}>
            <label htmlFor="textPreview">Text to Preview (100-1000 chars):</label><br/>
            <textarea 
              id="textPreview" 
              rows={4} 
              style={{ width: '100%', boxSizing: 'border-box' }}
              value={textToPreview}
              onChange={e => setTextToPreview(e.target.value)}
              placeholder="Enter text for the generated voice to speak..."
              disabled={autoGenerateText}
            />
            <div style={{ marginTop: '5px' }}>
              <input 
                type="checkbox" 
                id="autoGenText" 
                checked={autoGenerateText} 
                onChange={e => {
                  const isChecked = e.target.checked;
                  setAutoGenerateText(isChecked);
                  // If checked, fill the text area; if unchecked, clear it
                  if (isChecked) {
                    const gettysburgStart = "Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal.";
                    setTextToPreview(gettysburgStart);
                  } else {
                    setTextToPreview(''); // Clear text when unchecked
                  }
                }} 
              />
              <label htmlFor="autoGenText"> Auto-generate suitable text</label>
            </div>
          </div>
          
          <h5>Settings:</h5>
           <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Loudness: [{formatSliderValue(loudness)}]</label>
              <Slider min={-1} max={1} step={0.05} value={loudness} onChange={(v) => setLoudness(v as number)} />
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>Quietest</small><small>Loudest</small></div>
          </div>
           <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Quality (vs Variety): [{formatSliderValue(quality)}]</label>
              <Slider min={-1} max={1} step={0.05} value={quality} onChange={(v) => setQuality(v as number)} />
               <div style={{display: 'flex', justifyContent: 'space-between'}}><small>More Variety</small><small>Higher Quality</small></div>
          </div>
           <div style={{ marginBottom: '15px', padding: '0 5px' }}>
              <label>Guidance Scale: [{formatSliderValue(guidanceScale)}]</label>
              <Slider min={0} max={20} step={0.5} value={guidanceScale} onChange={(v) => setGuidanceScale(v as number)} /> 
              <div style={{display: 'flex', justifyContent: 'space-between'}}><small>More Creative</small><small>Stricter Prompt Adherence</small></div>
          </div>
           <div style={{ marginBottom: '15px' }}>
              <label htmlFor="seed">Seed (Optional):</label>
              <input 
                type="number" id="seed" value={seed} 
                onChange={e => setSeed(e.target.value)} 
                min="0" placeholder="Leave empty for random" 
                style={{width: '180px', marginLeft: '10px'}}
              />
          </div>

          <button onClick={handleGeneratePreviews} disabled={isGenerating || !voiceDescription}>
            {isGenerating ? 'Generating...' : 'Generate Previews'}
          </button>
          {error && !isGenerating && !isSaving && <p style={{ color: 'red', marginTop: '10px' }}>Error: {error}</p>}
        
        </div>

        {/* Right Column: Results & Saving */}
        <div style={{ 
          width: '65%',
          display: 'flex', 
          flexDirection: 'column', 
          gap: '20px' 
        }}>
          
          {/* Section for Latest Previews */}
          <div style={{ border: '1px solid #eee', padding: '20px', borderRadius: '5px' }}>
            <h4>Latest Previews</h4>
            {isGenerating && <p>Generating previews...</p>}
            {!isGenerating && currentPreviews.length === 0 && <p>Click "Generate Previews" to start.</p>}
            {currentPreviews.length > 0 && (
              <div>
                <p style={{fontSize: '0.9em', fontStyle: 'italic'}}><strong>Text Used:</strong> "{generatedText}"</p>
                {currentPreviews.map((preview, index) => (
                  <div key={preview.generated_voice_id} style={{
                      border: '1px solid #ccc', 
                      padding: '10px', marginBottom: '10px', borderRadius: '4px',
                      display: 'flex', flexDirection: 'column', gap: '5px'
                  }}>
                    <p style={{margin: 0}}>Preview {index + 1} <small>(ID: ...{preview.generated_voice_id.slice(-6)})</small></p>
                    <audio controls src={getAudioSrc(preview.audio_base_64)} style={{ width: '100%' }}>
                      Your browser does not support the audio element.
                    </audio>
                    <div>
                      <button 
                        onClick={() => handleHoldPreview(preview)} 
                        disabled={isSaving}
                        style={{ marginRight: '10px' }}
                      >
                        ➕ Hold
                      </button>
                      <button 
                        onClick={() => handleDiscardPreview(preview.generated_voice_id, 'current')} 
                        disabled={isSaving}
                        style={{ color: 'red' }} 
                      >
                        🗑️ Discard
                      </button>
                     </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section for Held Previews */}
          <div style={{ border: '1px solid #eee', padding: '20px', borderRadius: '5px' }}>
             <h4>Held Previews</h4>
             {heldPreviews.length === 0 && <p>Previews you 'Hold' will appear here.</p>}
             {heldPreviews.map((preview, index) => (
                <div key={preview.generated_voice_id} style={{
                    border: '1px solid #ccc', 
                    padding: '10px', marginBottom: '10px', borderRadius: '4px',
                    display: 'flex', flexDirection: 'column', gap: '5px'
                }}>
                   <p style={{margin: 0}}>Held {index + 1} <small>(ID: ...{preview.generated_voice_id.slice(-6)})</small></p>
                   <p style={{margin: 0, fontSize: '0.8em', fontStyle: 'italic', color: '#555'}}>Desc: "{preview.originalDescription.substring(0, 50)}..."</p>
                   <audio controls src={getAudioSrc(preview.audio_base_64)} style={{ width: '100%' }}>
                     Your browser does not support the audio element.
                   </audio>
                   <div>
                       <button 
                         onClick={() => handleOpenNamingModal(preview)} 
                         disabled={isSaving}
                         style={{ marginRight: '10px' }}
                       >
                         💾 Save Voice...
                       </button>
                       <button 
                         onClick={() => handleDiscardPreview(preview.generated_voice_id, 'held')} 
                         disabled={isSaving}
                         style={{ color: 'red' }} 
                       >
                          🗑️ Discard
                       </button>
                    </div>
                </div>
              ))}
          </div>

          {/* Display page-level error if not generating/saving */}
          {error && !isGenerating && !isSaving && <p style={{ color: 'red', marginTop: '10px' }}>Error: {error}</p>} 
        
        </div>

      </div>

      {/* Render the Save Name Modal */} 
      <SaveVoiceNameModal 
        isOpen={namingModalOpen}
        onClose={() => { setNamingModalOpen(false); setPreviewToName(null); }}
        onSubmit={(name) => {
            if(previewToName) {
                handleSaveVoice(previewToName, name);
            }
        }}
        previewToSave={previewToName}
        isSaving={isSaving}
      />

    </div>
  );
};

export default VoiceDesignPage; 