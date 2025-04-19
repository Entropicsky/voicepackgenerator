import React from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow';
import { Take } from '../../types';

const TrashPanel: React.FC = () => {
  const { batchMetadata, setTakeRankWithinLine } = useRanking();

  // Calculate trashedTakes directly without useMemo
  const trashedTakes = batchMetadata?.takes
      .filter(t => t.rank === 6)
      .sort((a, b) => a.take_number - b.take_number) || []; 

  // Handle restoring a take
  const handleRestore = (take: Take) => {
    if (take) {
      setTakeRankWithinLine(take.file, null); // Set rank back to null (Inbox)
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '10px', backgroundColor: '#fff0f0', maxHeight: '40vh', overflowY: 'auto', marginTop: '15px' }}>
      <h3>🗑️ Trashed Takes</h3>
      {trashedTakes.length === 0 ? (
        <p style={{ fontStyle: 'italic', color: '#888' }}>- Empty -</p>
      ) : (
        trashedTakes.map((take) => (
          <div key={take.file} style={{ marginBottom: '10px', borderBottom: '1px solid #eee', paddingBottom: '5px' }}>
            <TakeRow take={take} showRankButtons={false} />
            <button 
              onClick={() => handleRestore(take)} 
              style={{marginLeft: '10px', fontSize: '0.8em', padding: '2px 5px', cursor: 'pointer'}}
              title={`Restore ${take.file} (Move back to Inbox)`}
            >
              ♻️ Restore
            </button>
          </div>
        ))
      )}
    </div>
  );
};

export default TrashPanel; 