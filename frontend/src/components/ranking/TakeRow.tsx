import React, { useRef, useEffect } from 'react';
import { Take } from '../../types';
import { useRanking } from '../../contexts/RankingContext';
import { api } from '../../api'; // For getting audio URL

interface TakeRowProps {
  take: Take;
  // Add optional flags/handlers to control button visibility/actions
  showRankButtons?: boolean; // Default true
  onTrash?: () => void;      // Handler for trash action
}

const TakeRow: React.FC<TakeRowProps> = ({ take, showRankButtons = true, onTrash }) => {
  const { 
      batchMetadata, 
      setTakeRankWithinLine, 
      isLocked, 
      currentlyPlayingTakeFile, // Get playback state
      setCurrentlyPlayingTakeFile // Get setter
  } = useRanking();
  
  const audioRef = useRef<HTMLAudioElement | null>(null); // Ref to hold the Audio object

  const handlePlay = () => {
    if (!batchMetadata) return;

    // If this audio is already playing, pause it and clear state
    if (audioRef.current && !audioRef.current.paused && currentlyPlayingTakeFile === take.file) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0; 
        setCurrentlyPlayingTakeFile(null); // Clear the global playing state
        return; // Stop here
    }

    // Stop any currently playing audio *before* creating the new one
    // (though useEffect below also handles this, this can be slightly more immediate)
    if (currentlyPlayingTakeFile !== null && currentlyPlayingTakeFile !== take.file) {
       // Another audio is playing - the useEffect hook in the *other* component instance will handle pausing it.
       // We just need to ensure we set *this* one as the current player below.
    }

    // Clear previous audio object if it exists
    if (audioRef.current) {
        audioRef.current.pause(); // Ensure it's stopped
        audioRef.current = null; 
    }

    const audioUrl = api.getAudioUrl(`${batchMetadata.skin_name}/${batchMetadata.voice_name}/${batchMetadata.batch_id}/takes/${take.file}`);
    console.log(`Play audio: ${audioUrl} for take ${take.file}`);
    const audio = new Audio(audioUrl);
    audioRef.current = audio; // Store the new audio object

    // When audio finishes naturally
    audio.onended = () => {
        console.log(`Audio ended naturally for ${take.file}`);
        if (currentlyPlayingTakeFile === take.file) {
            setCurrentlyPlayingTakeFile(null); // Clear global state only if this was the one playing
        }
        audioRef.current = null; // Clear the ref
    };

    // Handle potential playback errors
    audio.play().then(() => {
        // Successfully started playing
        console.log(`Setting currently playing take to: ${take.file}`);
        setCurrentlyPlayingTakeFile(take.file); // Set this as the currently playing take
    }).catch(e => {
        console.error("Audio playback error:", e);
        audioRef.current = null; // Clear ref on error
        if (currentlyPlayingTakeFile === take.file) {
             setCurrentlyPlayingTakeFile(null); // Clear global state on error too
        }
    });
  };

  // Effect to pause this audio if another starts playing
  useEffect(() => {
      if (audioRef.current && currentlyPlayingTakeFile !== take.file) {
          console.log(`Another take (${currentlyPlayingTakeFile}) started playing. Pausing ${take.file}.`);
          audioRef.current.pause();
          // Optionally reset time if you want it to start from beginning next time
          // audioRef.current.currentTime = 0; 
          // We don't clear audioRef here, only pause it. handlePlay will clear if user plays this again.
      }
  }, [currentlyPlayingTakeFile, take.file]); // Re-run when the global playing file changes


  // Effect for cleanup when the component unmounts or take changes
  useEffect(() => {
    // Store the ref in a variable for the cleanup function scope
    const currentAudio = audioRef.current; 
    const currentTakeFile = take.file;
    
    return () => {
      console.log(`Cleaning up TakeRow for ${currentTakeFile}`);
      if (currentAudio) {
        currentAudio.pause(); // Pause audio on unmount
      }
      // If this component's audio was the one playing globally, clear the global state
      if (currentlyPlayingTakeFile === currentTakeFile) {
        setCurrentlyPlayingTakeFile(null);
      }
    };
    // IMPORTANT: Add setCurrentlyPlayingTakeFile to dependencies if ESLint warns, 
    // otherwise run only on unmount/take change
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
        backgroundColor: '#fff' // Keep background consistent
    }}>
      {/* Play/Pause Button - Toggles based on state */}
      <button onClick={handlePlay} title={currentlyPlayingTakeFile === take.file ? `Pause ${take.file}` : `Play ${take.file}`} style={{ flexShrink: 0, padding: '5px 8px' }}>
        {currentlyPlayingTakeFile === take.file ? '⏸️ Pause' : '▶️ Play'}
      </button>

      {/* Take Info */}
      <div style={{ flexGrow: 1 }}>
        <span><strong>Take {take.take_number}:</strong> {take.file}</span>
        <small style={{ display: 'block', color: '#555' }}>{take.script_text}</small>
      </div>

      {/* Rank Buttons (Conditional) */}
      {showRankButtons && (
        <div style={{ flexShrink: 0 }}>
            <span>Rank: </span>
            {[1, 2, 3, 4, 5].map(r => (
                <button 
                  key={r} 
                  onClick={() => handleRankClick(r)} 
                  title={`Rank ${r}`} 
                  disabled={isLocked} 
                  style={buttonStyle(r)}
                >
                    {r}
                </button>
            ))}
            {/* Trash Button (use onTrash handler) */}
            <button 
              onClick={onTrash} // Call the passed handler
              title="Trash this take (move to Trash bin)" 
              disabled={isLocked} 
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