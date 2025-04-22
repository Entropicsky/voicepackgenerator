import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Take } from '../../types';
import { useRanking } from '../../contexts/RankingContext';
import { api } from '../../api'; // For getting audio URL
import { ActionIcon, Tooltip, Text, Loader, Alert, Group, Box } from '@mantine/core';
import { IconCrop, IconAlertCircle } from '@tabler/icons-react';

interface TakeRowProps {
  take: Take;
  // Add optional flags/handlers to control button visibility/actions
  showRankButtons?: boolean; // Default true
  onTrash?: () => void;      // Handler for trash action
  onEdit: (take: Take) => void; // Add onEdit prop
}

// Helper to format settings
const formatSettings = (settings: Take['generation_settings']): string => {
  if (!settings) return 'No settings recorded';
  const parts = [];
  if (settings.stability !== undefined && settings.stability !== null) 
    parts.push(`Stab: ${settings.stability.toFixed(2)}`);
  if (settings.similarity_boost !== undefined && settings.similarity_boost !== null)
    parts.push(`Sim: ${settings.similarity_boost.toFixed(2)}`);
  if (settings.style !== undefined && settings.style !== null)
    parts.push(`Style: ${settings.style.toFixed(2)}`);
  if (settings.speed !== undefined && settings.speed !== null)
    parts.push(`Speed: ${settings.speed.toFixed(2)}`);
  if (typeof settings.use_speaker_boost === 'boolean') 
    parts.push(`Boost: ${settings.use_speaker_boost ? 'On' : 'Off'}`);
  
  return parts.length > 0 ? parts.join(' | ') : 'Settings not available';
};

const TakeRow: React.FC<TakeRowProps> = ({ take, showRankButtons = true, onTrash, onEdit }) => {
  const { 
      batchMetadata, 
      setTakeRankWithinLine, 
      isLocked, 
      currentlyPlayingTakeFile, // Get playback state
      setCurrentlyPlayingTakeFile,
      cropStatusByTakeFile // Get crop status map
  } = useRanking();
  
  const audioRef = useRef<HTMLAudioElement | null>(null); // Ref to hold the Audio object

  // Determine current crop status for this take
  const currentCropStatus = cropStatusByTakeFile[take.file];
  const isCropping = currentCropStatus && (currentCropStatus.status === 'SUBMITTED' || currentCropStatus.status === 'STARTED' || currentCropStatus.status === 'PENDING');
  const cropFailed = currentCropStatus && currentCropStatus.status === 'FAILURE';

  const handlePlay = () => {
    if (!batchMetadata) return;

    // Toggle Pause: If this audio is already playing, pause it and clear state
    if (audioRef.current && !audioRef.current.paused && currentlyPlayingTakeFile === take.file) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
        setCurrentlyPlayingTakeFile(null);
        console.log(`Paused take: ${take.file}`);
        return;
    }

    // If another audio is playing, signal it to stop FIRST by clearing the global state.
    if (currentlyPlayingTakeFile !== null && currentlyPlayingTakeFile !== take.file) {
        console.log(`Signaling take ${currentlyPlayingTakeFile} to stop because ${take.file} is starting.`);
        setCurrentlyPlayingTakeFile(null); 
    }

    // Clear previous audio object ref *for this instance* if it exists
    if (audioRef.current) {
        audioRef.current.onended = null;
        audioRef.current.pause();
        audioRef.current = null;
    }

    const audioUrl = api.getAudioUrl(`${batchMetadata.skin_name}/${batchMetadata.voice_name}/${batchMetadata.batch_id}/takes/${take.file}`);
    console.log(`Creating audio for take ${take.file}: ${audioUrl}`);
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onended = () => {
        console.log(`Audio ended naturally for ${take.file}`);
        if (currentlyPlayingTakeFile === take.file) { setCurrentlyPlayingTakeFile(null); }
        if (audioRef.current === audio) { audioRef.current = null; }
    };

    audio.play().then(() => {
        console.log(`Setting currently playing take to: ${take.file}`);
        setCurrentlyPlayingTakeFile(take.file); // Set this as playing *after* successful start
    }).catch(e => {
        console.error("Audio playback error:", e);
        if (currentlyPlayingTakeFile === take.file) { setCurrentlyPlayingTakeFile(null); }
        if (audioRef.current === audio) { audioRef.current = null; }
    });
  };

  // Effect to pause this audio if another starts playing OR if playing is cleared globally
  useEffect(() => {
      if (audioRef.current) {
          if (currentlyPlayingTakeFile !== take.file) {
              if (!audioRef.current.paused) {
                  console.log(`Global player changed (${currentlyPlayingTakeFile}). Pausing ${take.file}.`);
                  audioRef.current.pause();
              }
          }
      }
  }, [currentlyPlayingTakeFile, take.file]);


  // Effect for cleanup when the component unmounts or take changes
  useEffect(() => {
    const currentAudio = audioRef.current;
    const currentTakeFile = take.file;
    return () => {
      console.log(`Cleaning up TakeRow for ${currentTakeFile}`);
      if (currentAudio) {
        currentAudio.pause();
        currentAudio.onended = null;
      }
      if (currentlyPlayingTakeFile === currentTakeFile) {
        setCurrentlyPlayingTakeFile(null);
      }
    };
  }, [take.file, currentlyPlayingTakeFile, setCurrentlyPlayingTakeFile]);

  // Call the context function which handles line-scoped cascade logic
  const handleRankClick = (newRank: number | null) => {
    if (!isLocked) {
      setTakeRankWithinLine(take.file, newRank);
    }
  };

  const buttonStyle = (rankNum: number): React.CSSProperties => ({
    minWidth: '25px',
    margin: '0 2px',
    border: take.rank === rankNum ? '2px solid blue' : '1px solid #ccc',
    fontWeight: take.rank === rankNum ? 'bold' : 'normal',
    padding: '2px 5px',
    cursor: isLocked ? 'not-allowed' : 'pointer' // Add cursor style
  });

  // NEW style for the Trash button
  const trashButtonStyle: React.CSSProperties = {
     marginLeft: '5px',
     border: '1px solid #ccc',
     padding: '2px 5px',
     cursor: isLocked ? 'not-allowed' : 'pointer', // Disable cursor if locked
     color: 'red' // Make it red
  };

  return (
    <div style={{ 
          marginLeft: '10px',
          marginBottom: '5px',
          padding: '8px', 
          border: '1px solid #e0e0e0', 
          display: 'flex', 
          alignItems: 'center', 
          gap: '15px', 
          borderRadius: '4px', 
          backgroundColor: '#fff', // Keep background consistent
          opacity: isCropping ? 0.6 : 1, // Dim row while cropping
          pointerEvents: isCropping ? 'none' : 'auto' // Prevent interaction while cropping
      }}>
        {/* Play/Pause Button - Toggles based on state */}
        <button onClick={handlePlay} title={currentlyPlayingTakeFile === take.file ? `Pause ${take.file}` : `Play ${take.file}`} disabled={isCropping} style={{ flexShrink: 0, padding: '5px 8px' }}>
          {currentlyPlayingTakeFile === take.file ? '⏸️ Pause' : '▶️ Play'}
        </button>

        {/* Edit Button (Use props.onEdit) */}
        <Tooltip label={isCropping ? "Crop in progress..." : "Edit/Crop Audio"} position="top" withArrow>
            <ActionIcon 
                variant="default" 
                size="sm"
                onClick={() => onEdit(take)}
                disabled={isLocked || isCropping}
            >
                <IconCrop size={16} />
            </ActionIcon>
        </Tooltip>

        {/* Take Info */}
        <Box style={{ flexGrow: 1, position: 'relative' }}>
          <span><strong>Take {take.take_number}:</strong> {take.file}</span>
          <Text size="xs" c="dimmed" title={take.script_text || ''}>
            {take.script_text || ''}
          </Text>
          {/* NEW: Display Formatted Generation Settings */}
          {take.generation_settings && (
            <Text size="xs" c="gray" mt={3}> 
              {formatSettings(take.generation_settings)}
            </Text>
          )}
          {/* Display Crop Status */}
          {isCropping && (
              <Group gap="xs" style={{ position: 'absolute', top: '0', right: '0', backgroundColor: 'rgba(255,255,255,0.8)', padding: '2px 5px', borderRadius: '3px' }}>
                  <Loader size="xs" /> 
                  <Text size="xs" c="blue">Cropping...</Text>
              </Group>
          )}
          {cropFailed && (
               <Tooltip label={currentCropStatus?.error || 'Unknown error'} position="top" multiline w={220}>
                  <Group gap="xs" style={{ position: 'absolute', top: '0', right: '0', backgroundColor: 'rgba(255,255,255,0.8)', padding: '2px 5px', borderRadius: '3px' }}>
                      <IconAlertCircle size={14} color="red"/>
                      <Text size="xs" c="red">Crop Failed</Text>
                  </Group>
              </Tooltip>
          )}
        </Box>

        {/* Rank Buttons (Conditional) */}
        {showRankButtons && (
          <div style={{ flexShrink: 0 }}>
              <span style={{ opacity: isCropping ? 0.5 : 1 }}>Rank: </span>
              {[1, 2, 3, 4, 5].map(r => (
                  <button 
                    key={r} 
                    onClick={() => handleRankClick(r)} 
                    title={`Rank ${r}`} 
                    disabled={isLocked || isCropping}
                    style={buttonStyle(r)}
                  >
                      {r}
                  </button>
              ))}
              {/* Trash Button (use onTrash handler) */}
              <button 
                onClick={onTrash} // Call the passed handler
                title="Trash this take (move to Trash bin)" 
                disabled={isLocked || isCropping} 
                style={trashButtonStyle}
              >
                🗑️
              </button>
          </div>
        )}
    </div>
  );
};

export default TakeRow; 