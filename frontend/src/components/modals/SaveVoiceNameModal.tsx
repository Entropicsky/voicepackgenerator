import React, { useState, useEffect } from 'react';
import { RichVoicePreview } from '../../types'; // Assuming types are in ../types

interface SaveVoiceNameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string) => void; // Passes the chosen name back
  previewToSave: RichVoicePreview | null;
  isSaving: boolean; // To disable submit button while saving
}

const SaveVoiceNameModal: React.FC<SaveVoiceNameModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  previewToSave,
  isSaving
}) => {
  const [voiceName, setVoiceName] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // Reset name when modal opens with a new preview
  useEffect(() => {
    if (isOpen && previewToSave) {
      setVoiceName(''); // Clear previous name attempts
      setError(null);
    }
  }, [isOpen, previewToSave]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!voiceName.trim()) {
      setError('Please enter a name for the voice.');
      return;
    }
    onSubmit(voiceName.trim());
    // Don't close here, let the parent close after successful save
    // onClose(); 
  };

  if (!isOpen || !previewToSave) {
    return null;
  }

  // Simple inline styles for modal
  const modalStyle: React.CSSProperties = {
    position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
    backgroundColor: 'white', padding: '25px', borderRadius: '8px', 
    boxShadow: '0 5px 15px rgba(0,0,0,0.3)', zIndex: 1050, // Higher z-index
    minWidth: '400px'
  };
  const overlayStyle: React.CSSProperties = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
    backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 1040
  };

  return (
    <div style={overlayStyle} onClick={onClose}> 
      <div style={modalStyle} onClick={e => e.stopPropagation()}> 
        <h4>Save Voice Preview</h4>
        <p style={{ fontSize: '0.9em', color: '#555', marginBottom: '15px' }}>
          Saving preview <small>(ID: ...{previewToSave.generated_voice_id.slice(-6)})</small><br/>
          Generated with description: "{previewToSave.originalDescription}"
        </p>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '10px' }}>
            <label htmlFor="modalVoiceName">New Voice Name:</label><br/>
            <input 
              type="text" 
              id="modalVoiceName" 
              value={voiceName} 
              onChange={e => setVoiceName(e.target.value)} 
              placeholder="Enter name for voice library"
              required 
              style={{ width: '95%', padding: '8px', marginTop: '5px' }}
              autoFocus // Focus input when modal opens
            />
          </div>
          {error && <p style={{ color: 'red', fontSize: '0.9em' }}>{error}</p>}
          <div style={{ marginTop: '20px', textAlign: 'right' }}>
            <button type="button" onClick={onClose} style={{ marginRight: '10px' }} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" disabled={isSaving || !voiceName.trim()}>
              {isSaving ? 'Saving...' : 'Confirm Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SaveVoiceNameModal; 