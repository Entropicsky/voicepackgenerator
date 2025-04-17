import React, { useState, useEffect } from 'react';
import { api } from '../../api';
import { VoiceOption } from '../../types';

interface VoiceSelectorProps {
  selectedVoices: string[]; // Array of selected voice IDs
  onChange: (selectedIds: string[]) => void;
}

const VoiceSelector: React.FC<VoiceSelectorProps> = ({ selectedVoices, onChange }) => {
  const [availableVoices, setAvailableVoices] = useState<VoiceOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVoices = async () => {
      setLoading(true);
      setError(null);
      try {
        const voices = await api.getVoices();
        setAvailableVoices(voices);
      } catch (err: any) {
        setError(`Failed to load voices: ${err.message}`);
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchVoices();
  }, []); // Fetch only once on mount

  const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value, checked } = event.target;
    let newSelectedVoices: string[];

    if (checked) {
      newSelectedVoices = [...selectedVoices, value];
    } else {
      newSelectedVoices = selectedVoices.filter(id => id !== value);
    }
    onChange(newSelectedVoices);
  };

  if (loading) {
    return <p>Loading voices...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div style={{ maxHeight: '200px', overflowY: 'scroll', border: '1px solid #ccc', padding: '10px' }}>
      <h4>Available Voices (Select one or more):</h4>
      {availableVoices.length === 0 ? (
        <p>No voices found.</p>
      ) : (
        availableVoices.map((voice) => (
          <div key={voice.id}>
            <input
              type="checkbox"
              id={`voice-${voice.id}`}
              value={voice.id}
              checked={selectedVoices.includes(voice.id)}
              onChange={handleCheckboxChange}
            />
            <label htmlFor={`voice-${voice.id}`}>{voice.name} ({voice.id})</label>
          </div>
        ))
      )}
    </div>
  );
};

export default VoiceSelector; 