import React from 'react';
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
  // Use the new function name from context
  const { batchMetadata, setTakeRankWithinLine, isLocked } = useRanking();

  const handlePlay = () => {
    if (!batchMetadata) return;
    const audioUrl = api.getAudioUrl(`${batchMetadata.skin_name}/${batchMetadata.voice_name}/${batchMetadata.batch_id}/takes/${take.file}`);
    console.log("Play audio:", audioUrl);
    const audio = new Audio(audioUrl);
    audio.play().catch(e => console.error("Audio playback error:", e));
  };

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
      {/* Play Button */}
      <button onClick={handlePlay} title={`Play ${take.file}`} style={{ flexShrink: 0, padding: '5px 8px' }}>▶️ Play</button>

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