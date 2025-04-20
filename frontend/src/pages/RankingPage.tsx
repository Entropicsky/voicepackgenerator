import React from 'react';
// Remove useParams import if no longer needed here
// import { useParams } from 'react-router-dom'; 
// Remove RankingProvider import, it's now handled by the route wrapper
// import { RankingProvider, useRanking } from '../contexts/RankingContext'; 
import { useRanking } from '../contexts/RankingContext'; // Keep useRanking
import CurrentLineTakes from '../components/ranking/CurrentLineTakes';
import CurrentLineRankedPanel from '../components/ranking/CurrentLineRankedPanel';
import LineNavigation from '../components/ranking/LineNavigation';
import TrashPanel from '../components/ranking/TrashPanel';
import { Loader, Alert, Button, Group, Text } from '@mantine/core'; // Import Mantine components
import { IconAlertCircle } from '@tabler/icons-react'; // Import icons

// Renamed from RankingUI to RankingPage, this is now the main export
const RankingPage: React.FC = () => {
  // Get data directly from the context provided by the route wrapper
  const {
    batchMetadata,
    loading,
    error,
    isLocked,
    lockCurrentBatch,
    refetchMetadata,
    batchId, // Now available from context!
  } = useRanking();

  if (loading) {
    // Use Mantine Loader
    return <Loader style={{ display: 'block', margin: 'auto' }} />;
  }

  if (error) {
    // Use Mantine Alert
    return (
      <Alert icon={<IconAlertCircle size="1rem" />} title="Error Loading Batch" color="red">
        {error}
      </Alert>
    );
  }

  if (!batchMetadata) {
    // Use Mantine Alert for not found
    return (
      <Alert icon={<IconAlertCircle size="1rem" />} title="Not Found" color="yellow">
        Batch data not found.
      </Alert>
    );
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

  return (
    // Use Mantine styling conventions if desired, or keep existing inline styles
    <div style={{ padding: '15px', border: '1px solid #ddd', borderRadius: '5px', backgroundColor: '#f9f9f9' }}>
      {/* Batch Details Header */}  
      <Group justify="space-between" mb="md" pb="md" style={{ borderBottom: '1px solid #ddd' }}>
        <Group gap="xl">
          <Text size="sm"><Text span fw={700}>Skin:</Text> {batchMetadata.skin_name}</Text>
          <Text size="sm"><Text span fw={700}>Voice:</Text> {batchMetadata.voice_name}</Text>
          <Text size="sm"><Text span fw={700}>Generated:</Text> {new Date(batchMetadata.generated_at_utc).toLocaleString()}</Text>
          <Text size="sm"><Text span fw={700}>Status:</Text> {isLocked ? `Locked (${new Date(batchMetadata.ranked_at_utc || Date.now()).toLocaleDateString()})` : 'Unlocked'}</Text>
        </Group>
        <Group>
          <Button onClick={refetchMetadata} disabled={loading} variant="outline" size="xs" title="Reload batch data from server">
            Refresh Data
          </Button>
          {/* Use batchPrefix (available as batchId from context) for download URL */}
          <Button 
            component="a" 
            href={`/api/batch/${encodeURIComponent(batchId)}/download`} 
            download={`${batchMetadata?.voice_name}.zip`} 
            variant="outline" 
            color="green" 
            size="xs"
            title={`Download ZIP for ${batchId}`}
          >
            Download ZIP
          </Button>
          {!isLocked && (
            <Button onClick={handleLock} size="xs">Lock Batch</Button>
          )}
        </Group>
      </Group>
      
      {/* Main Content Panels */} 
      <div style={{ display: 'flex', flexDirection: 'row', gap: '15px' }}>
        <LineNavigation />        {/* flex: 1 */}
        <CurrentLineTakes />      {/* flex: 3 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <CurrentLineRankedPanel />{/* Takes remaining vertical space */}
          <TrashPanel />            {/* Sits below ranked panel */}
        </div>
      </div>
    </div>
  );
}

// Remove the outer RankingPage component that was adding the provider

export default RankingPage; // Export the UI component directly 