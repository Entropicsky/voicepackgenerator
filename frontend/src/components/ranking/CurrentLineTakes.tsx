import React from 'react';
import { useRanking } from '../../contexts/RankingContext';
import TakeRow from './TakeRow';
import { Take } from '../../types';

// This component is no longer responsible for rendering takes,
// as RankSlots handles grouping and rendering by rank.
// It might be used later for other line-based info or filtering.
const CurrentLineTakes: React.FC = () => {
  // Get selected line and takes data from context
  const { takesByLine, selectedLineKey } = useRanking();

  // Handle no line selected state
  if (!selectedLineKey) {
    return (
        <div style={{ flex: 3, padding: '10px', backgroundColor: '#f8f9fa' }}>
            <h3>Select a Line</h3>
            <p>Choose a line from the navigation panel on the left to view and rank its takes.</p>
        </div>
    );
  }

  const currentLineTakes = takesByLine[selectedLineKey] || [];

  return (
    <div style={{flex: 3, marginRight: '15px', maxHeight: '80vh', overflowY: 'auto', padding: '10px'}}> 
      <h3>Takes for Line: {selectedLineKey}</h3>
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
    </div>
  );
};

export default CurrentLineTakes; 