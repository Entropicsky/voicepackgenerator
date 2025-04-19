import React from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow'; // Reuse TakeRow for consistent display
import { Take } from '../../types'; // Add missing import for Take type

const CurrentLineRankedPanel: React.FC = () => {
  const { selectedLineKey, currentLineRankedTakes, setTakeRankWithinLine } = useRanking();

  const handleUnrank = (take: Take) => {
    if (take) {
        setTakeRankWithinLine(take.file, null);
    }
  };

  return (
    <div style={{ flex: 1, border: '1px solid #ccc', padding: '10px', backgroundColor: '#f0f8ff', maxHeight: '80vh', overflowY: 'auto' }}>
      <h3>{selectedLineKey ? `Top Ranked: ${selectedLineKey}` : 'Top Ranked Takes'}</h3>
      {!selectedLineKey && <p style={{ fontStyle: 'italic', color: '#888' }}>Select a line to see its ranks.</p>}
      {[1, 2, 3, 4, 5].map((rankNum, index) => {
        const take = currentLineRankedTakes[index];
        return (
          <div key={rankNum} style={{ marginBottom: '15px' }}>
            <h4>Rank {rankNum}:</h4>
            {take ? (
              <div>
                <TakeRow take={take} showRankButtons={false} />
                <button 
                    onClick={() => handleUnrank(take)} 
                    style={{marginLeft: '10px', fontSize: '0.8em', padding: '2px 5px', cursor: 'pointer'}} 
                    title={`Unrank ${take.file} (Move back to Inbox)`}
                >
                    ❌ Unrank
                </button>
              </div>
            ) : (
              <p style={{ fontStyle: 'italic', color: '#888', marginLeft: '20px' }}>- Empty -</p>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default CurrentLineRankedPanel; 