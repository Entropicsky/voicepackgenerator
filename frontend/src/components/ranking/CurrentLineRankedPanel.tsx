import React from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow'; // Reuse TakeRow for consistent display

const CurrentLineRankedPanel: React.FC = () => {
  const { selectedLineKey, currentLineRankedTakes } = useRanking();

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
              <TakeRow take={take} />
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