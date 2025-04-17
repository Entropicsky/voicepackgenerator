import React, { useState } from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow';
import { Take } from '../../types';
import RegenerationModal from './RegenerationModal';
import SpeechToSpeechModal from './SpeechToSpeechModal';
import { useNavigate } from 'react-router-dom';

// This component is no longer responsible for rendering takes,
// as RankSlots handles grouping and rendering by rank.
// It might be used later for other line-based info or filtering.
const CurrentLineTakes: React.FC = () => {
  const { takesByLine, selectedLineKey, batchMetadata } = useRanking();
  const [showRegenModal, setShowRegenModal] = useState<boolean>(false);
  const [showStsModal, setShowStsModal] = useState<boolean>(false);
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

  const handleOpenStsModal = () => {
    if (selectedLineKey) {
      setShowStsModal(true);
    }
  };

  const handleCloseStsModal = () => {
    setShowStsModal(false);
  };

  // Handle job submission notification from modal
  const handleJobSubmitted = (jobId: number, taskId: string) => {
    console.log(`New job ${jobId} submitted (task ${taskId}). Navigating to jobs page.`);
    navigate('/jobs');
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
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap'}}>
          <h3>Takes for Line: {selectedLineKey}</h3>
          <div>
              <button onClick={handleOpenRegenModal} title={`Regenerate takes for line ${selectedLineKey}`} style={{marginRight: '10px'}}>
                  🔄 Regenerate (TTS)...
              </button>
               <button onClick={handleOpenStsModal} title={`Generate takes using Speech-to-Speech for line ${selectedLineKey}"}`}>
                  🎤 Speech-to-Speech...
              </button>
          </div>
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
      {showStsModal && selectedLineKey && batchMetadata && (
          <SpeechToSpeechModal 
              batchId={batchMetadata.batch_id}
              lineKey={selectedLineKey}
              onClose={handleCloseStsModal}
              onJobSubmitted={handleJobSubmitted}
          />
      )}
    </div>
  );
};

export default CurrentLineTakes; 