import React from 'react';
import { useParams } from 'react-router-dom';
import { RankingProvider, useRanking } from '../contexts/RankingContext';
import CurrentLineTakes from '../components/ranking/CurrentLineTakes';
import CurrentLineRankedPanel from '../components/ranking/CurrentLineRankedPanel';
import LineNavigation from '../components/ranking/LineNavigation';

// Inner component to access context data
const RankingUI: React.FC = () => {
  const { batchMetadata, loading, error, isLocked, lockCurrentBatch } = useRanking();

  if (loading) {
    return <p>Loading batch data...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Error loading batch: {error}</p>;
  }

  if (!batchMetadata) {
    return <p>Batch data not found.</p>;
  }

  const handleLock = async () => {
      if (window.confirm('Are you sure you want to lock this batch? This cannot be undone easily.')) {
          try {
              await lockCurrentBatch();
              alert('Batch locked successfully!');
          } catch (err: any) {
              alert(`Failed to lock batch: ${err.message}`);
          }
      }
  };

  // Styles for compact details
  const detailStyle: React.CSSProperties = { marginRight: '15px' };
  const labelStyle: React.CSSProperties = { fontWeight: 'bold' };

  return (
    <div style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
      {/* Compact Batch Details Header */}  
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', paddingBottom: '10px', borderBottom: '1px solid #ddd' }}>
          <div>
              <span style={detailStyle}><span style={labelStyle}>Skin:</span> {batchMetadata.skin_name}</span>
              <span style={detailStyle}><span style={labelStyle}>Voice:</span> {batchMetadata.voice_name}</span>
              <span style={detailStyle}><span style={labelStyle}>Generated:</span> {new Date(batchMetadata.generated_at_utc).toLocaleString()}</span>
              <span style={detailStyle}><span style={labelStyle}>Status:</span> {isLocked ? `Locked (${new Date(batchMetadata.ranked_at_utc || Date.now()).toLocaleDateString()})` : 'Unlocked'}</span>
          </div>
          {!isLocked && (
              <button onClick={handleLock} style={{ padding: '5px 10px' }}>Lock Batch</button>
          )}
      </div>
      
      {/* Main Content Panels */}
      <div style={{ display: 'flex', flexDirection: 'row', gap: '15px' }}>
          <LineNavigation />        {/* flex: 1 */}
          <CurrentLineTakes />      {/* flex: 3 */}
          <CurrentLineRankedPanel />{/* flex: 1 */}
      </div>
    </div>
  );
}

// Main page component that sets up the provider
const RankingPage: React.FC = () => {
  const { batchId } = useParams<{ batchId: string }>();

  if (!batchId) {
    return <p>Error: No Batch ID provided.</p>;
  }

  return (
    <RankingProvider batchId={batchId}>
      <RankingUI />
    </RankingProvider>
  );
};

export default RankingPage; 