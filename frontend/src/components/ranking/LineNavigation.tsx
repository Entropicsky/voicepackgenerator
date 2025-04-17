import React from 'react';
import { useRanking } from '../../contexts/RankingContext';

const LineNavigation: React.FC = () => {
  const { takesByLine, selectedLineKey, setSelectedLineKey } = useRanking();

  const lineKeys = Object.keys(takesByLine).sort();

  if (lineKeys.length === 0) {
    return <p>No lines found in this batch.</p>;
  }

  const selectedIndex = selectedLineKey ? lineKeys.indexOf(selectedLineKey) : -1;

  const handleSelect = (key: string) => {
    setSelectedLineKey(key);
  };

  const handlePrev = () => {
    if (selectedIndex > 0) {
      setSelectedLineKey(lineKeys[selectedIndex - 1]);
    }
  };

  const handleNext = () => {
    if (selectedIndex !== -1 && selectedIndex < lineKeys.length - 1) {
      setSelectedLineKey(lineKeys[selectedIndex + 1]);
    }
  };

  const linkStyle = (key: string): React.CSSProperties => ({
    display: 'block',
    padding: '8px 10px',
    marginBottom: '2px',
    cursor: 'pointer',
    textDecoration: 'none',
    backgroundColor: selectedLineKey === key ? '#cfe2ff' : 'transparent',
    color: selectedLineKey === key ? '#0056b3' : '#0d6efd',
    borderRadius: '4px',
    fontWeight: selectedLineKey === key ? 'bold' : 'normal'
  });

  const buttonStyle: React.CSSProperties = {
      padding: '5px 10px',
      margin: '5px'
  }

  return (
    <div style={{ flex: 1, borderRight: '1px solid #ccc', padding: '10px', maxHeight: '80vh', overflowY: 'auto' }}>
      <h3>Lines</h3>
      <div>
          <button onClick={handlePrev} disabled={selectedIndex <= 0} style={buttonStyle}>&lt; Prev</button>
          <button onClick={handleNext} disabled={selectedIndex === -1 || selectedIndex >= lineKeys.length - 1} style={buttonStyle}>Next &gt;</button>
      </div>
      <nav>
        {lineKeys.map((key) => (
          <a
            key={key}
            href="#"
            style={linkStyle(key)}
            onClick={(e) => { e.preventDefault(); handleSelect(key); }}
          >
            {key}
          </a>
        ))}
      </nav>
    </div>
  );
};

export default LineNavigation; 