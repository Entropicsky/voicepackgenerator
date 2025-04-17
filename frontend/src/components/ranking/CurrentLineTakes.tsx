import React, { useState } from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow';
import { Take } from '../../types';
import RegenerationModal from './RegenerationModal';
import { useNavigate } from 'react-router-dom';

// This component is no longer responsible for rendering takes,
// as RankSlots handles grouping and rendering by rank.
// It might be used later for other line-based info or filtering.
const CurrentLineTakes: React.FC = () => {
  const { takesByLine, selectedLineKey, batchMetadata } = useRanking();
  const [showRegenModal, setShowRegenModal] = useState<boolean>(false);
  const navigate = useNavigate();

  // Handle opening the modal
  const handleOpenRegenModal = () => {
    if (selectedLineKey) {
      setShowRegenModal(true);
    }
  };

  // Handle modal close
  const handleCloseRegenModal = () => {
    setShowRegenModal(false);
  };

  // Handle job submission notification from modal
  const handleJobSubmitted = (jobId: number, taskId: string) => {
    console.log(`Line regeneration job ${jobId} submitted (task ${taskId}). Navigating to jobs page.`);
    // Optionally show a temporary success message here
    navigate('/jobs'); // Navigate to jobs page to monitor
  };

  // Handle no line selected state
  if (!selectedLineKey) {
    return (
        <div style={{ flex: 3, padding: '10px', backgroundColor: '#f8f9fa' }}>
            <h3>Select a Line</h3>
            <p>Choose a line from the navigation panel on the left to view and rank its takes.</p>
        </div>
    );
  }

  const currentLineTakes = takesByLine[selectedLineKey!] || [];

  return (
    <div style={{flex: 3, marginRight: '15px', maxHeight: '80vh', overflowY: 'auto', padding: '10px'}}> 
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <h3>Takes for Line: {selectedLineKey}</h3>
          <button onClick={handleOpenRegenModal} title={`Regenerate takes for line ${selectedLineKey}`}> 
              🔄 Regenerate Takes...
          </button>
      </div>
      {currentLineTakes.length === 0 ? (
        <p>No takes found for this line.</p>
      ) : (
        <div> 
          {/* Takes are already sorted by number in context effect */}
          {currentLineTakes.map((take: Take) => (
              <TakeRow key={take.file} take={take} />
            ))}
        </div>
      )}

      {/* Render Modal Conditionally */}  
      {showRegenModal && selectedLineKey && batchMetadata && (
          <RegenerationModal 
              batchId={batchMetadata.batch_id}
              lineKey={selectedLineKey}
              currentTakes={currentLineTakes}
              onClose={handleCloseRegenModal}
              onJobSubmitted={handleJobSubmitted}
          />
      )}
    </div>
  );
};

export default CurrentLineTakes; 