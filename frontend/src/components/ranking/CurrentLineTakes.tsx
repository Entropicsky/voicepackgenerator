import React, { useState, useCallback } from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow';
import { Take } from '../../types';
import RegenerationModal from './RegenerationModal';
import SpeechToSpeechModal from './SpeechToSpeechModal';
import { Modal, Text, Box, Button, Paper } from '@mantine/core';
import AudioEditModal from './AudioEditModal';

// This component is no longer responsible for rendering takes,
// as RankSlots handles grouping and rendering by rank.
// It might be used later for other line-based info or filtering.
const CurrentLineTakes: React.FC = () => {
  const { 
      takesByLine, 
      selectedLineKey, 
      batchMetadata, 
      lineRegenerationStatus,
      startLineRegeneration,
      setTakeRankWithinLine,
      batchId,
      startCropTaskTracking
  } = useRanking();
  console.log(`[CurrentLineTakes] Received batchId from context: ${batchId}`);
  const [showRegenModal, setShowRegenModal] = useState<boolean>(false);
  const [showStsModal, setShowStsModal] = useState<boolean>(false);
  const [editingTake, setEditingTake] = useState<Take | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState<boolean>(false);

  // Get the current regeneration status for the selected line
  const currentRegenJob = selectedLineKey ? lineRegenerationStatus[selectedLineKey] : null;
  const isRegenerating = !!currentRegenJob && currentRegenJob.status !== 'SUCCESS' && currentRegenJob.status !== 'FAILURE';

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

  // NEW handler passed to modals
  const handleRegenJobStarted = (lineKey: string, taskId: string) => {
    startLineRegeneration(lineKey, taskId);
    // Close the modal after submission is initiated
    setShowRegenModal(false);
    setShowStsModal(false);
  };

  // <<< Handlers for Edit Modal >>>
  const handleOpenEditModal = (takeToEdit: Take) => {
    console.log(`[CurrentLineTakes] Opening BASIC edit modal for take:`, takeToEdit);
    setEditingTake(takeToEdit);
    setIsEditModalOpen(true);
  };

  const handleCloseEditModal = () => {
    console.log(`[CurrentLineTakes] Closing edit modal.`);
    setIsEditModalOpen(false);
    setEditingTake(null);
  };

  // <<< New handler for when crop task is submitted >>>
  const handleCropStarted = useCallback((taskId: string) => {
      if (!editingTake) return;
      console.log(`[CurrentLineTakes] Crop task ${taskId} started for take ${editingTake.file}. Closing editor and starting tracking.`);
      startCropTaskTracking(editingTake.file, taskId); // Tell context to track
      handleCloseEditModal(); // Close the editor UI
  }, [editingTake, startCropTaskTracking]); // Add dependencies

  // Handle no line selected state
  if (!selectedLineKey) {
    return (
        <div style={{ flex: 3, padding: '10px', backgroundColor: '#f8f9fa' }}>
            <h3>Select a Line</h3>
            <p>Choose a line from the navigation panel on the left to view and rank its takes.</p>
        </div>
    );
  }

  // Calculate inboxTakes directly without useMemo
  const inboxTakes = (takesByLine[selectedLineKey!] || []).filter(take => take.rank === null);

  return (
    <div style={{flex: 3, marginRight: '15px', maxHeight: '80vh', overflowY: 'auto', padding: '10px'}}> 
      
      {/* Header Section (Always Visible) */} 
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', marginBottom: '15px'}}>
          <h3>Takes for Line: {selectedLineKey}</h3>
          <div>
             {/* Only show Regen/STS buttons when NOT editing */}
             {!isEditModalOpen && (
                 <> 
                    {isRegenerating ? (
                        <div style={{ fontStyle: 'italic', color: 'blue', padding: '5px 10px', border: '1px solid blue', borderRadius: '4px' }}>
                            🔄 Regenerating... ({currentRegenJob?.status})
                            {currentRegenJob?.info?.status && <small> ({currentRegenJob.info.status})</small>}
                        </div>
                    ) : currentRegenJob?.status === 'FAILURE' ? (
                        <div style={{ fontStyle: 'italic', color: 'red', padding: '5px 10px', border: '1px solid red', borderRadius: '4px' }}>
                            ❌ Regeneration Failed: {currentRegenJob?.error || 'Unknown error'}
                        </div>
                    ) : (
                       <>
                            <button onClick={handleOpenRegenModal} title={`Regenerate takes for line ${selectedLineKey}`} style={{marginRight: '10px'}} disabled={isRegenerating}>
                                🔄 Regenerate (TTS)...
                            </button>
                            <button onClick={handleOpenStsModal} title={`Generate takes using Speech-to-Speech for line ${selectedLineKey}"}`} disabled={isRegenerating}>
                                🎤 Speech-to-Speech...
                            </button>
                        </>
                    )}
                </>
             )}
          </div>
      </div>

      {/* --- Conditionally Render Editor OR Take List --- */} 
      {isEditModalOpen && editingTake && batchMetadata ? (
          // --- Render Editor View --- 
          <Paper shadow="md" p="md" mt="lg" withBorder style={{position: 'relative', zIndex: 10}}>
              <h4>Editing: {editingTake.file}</h4> 
              <AudioEditModal 
                  take={editingTake} 
                  batchMetadata={batchMetadata}
                  onCropStarted={handleCropStarted}
              />
              <Button variant="light" color="gray" onClick={handleCloseEditModal} mt="sm">
                  Close Editor
              </Button>
          </Paper>
      ) : (
          // --- Render Take List View --- 
          <> 
            {inboxTakes.length === 0 ? (
              <p>No unranked takes found for this line (Inbox is empty).</p>
            ) : (
              <div> 
                {inboxTakes.map((take: Take) => (
                    <TakeRow 
                        key={take.file} 
                        take={take} 
                        showRankButtons={true}
                        onTrash={() => setTakeRankWithinLine(take.file, 6)} 
                        onEdit={handleOpenEditModal}
                    />
                  ))}
              </div>
            )}
          </>
      )}

      {/* Render Other Modals (Regen/STS) - These use portals by default */}
      {showRegenModal && selectedLineKey && batchId && (
          <RegenerationModal 
              batchId={batchId}
              lineKey={selectedLineKey}
              currentTakes={takesByLine[selectedLineKey!] || []}
              onClose={handleCloseRegenModal}
              onRegenJobStarted={handleRegenJobStarted}
          />
      )}
      {showStsModal && selectedLineKey && batchId && (
          <SpeechToSpeechModal 
              batchId={batchId}
              lineKey={selectedLineKey}
              onClose={handleCloseStsModal}
              onRegenJobStarted={handleRegenJobStarted}
          />
      )}
    </div>
  );
};

export default CurrentLineTakes; 