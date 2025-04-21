import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Checkbox, Table, Input, Select, ActionIcon, Tooltip, Loader } from '@mantine/core';
import { IconPlayerPlay, IconPlayerPause, IconAlertCircle } from '@tabler/icons-react';
import { useVoiceContext } from '../../contexts/VoiceContext';
import { api } from '../../api';
import { notifications } from '@mantine/notifications';

interface VoiceSelectorProps {
  selectedVoices: string[];
  onChange: (selectedIds: string[]) => void;
}

const VoiceSelector: React.FC<VoiceSelectorProps> = ({ selectedVoices, onChange }) => {
  const { voices, loading, error: fetchError } = useVoiceContext();

  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [sortOrder, setSortOrder] = useState<string>('name_asc');

  const [previewingVoiceId, setPreviewingVoiceId] = useState<string | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState<boolean>(false);
  const currentAudio = useRef<HTMLAudioElement | null>(null);
  const currentBlobUrl = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (currentAudio.current) {
        currentAudio.current.pause();
        currentAudio.current = null;
      }
      if (currentBlobUrl.current) {
        URL.revokeObjectURL(currentBlobUrl.current);
        currentBlobUrl.current = null;
      }
    };
  }, []);

  const handleSelectChange = (voiceId: string, checked: boolean) => {
    if (checked) {
      onChange([...selectedVoices, voiceId]);
    } else {
      onChange(selectedVoices.filter(id => id !== voiceId));
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onChange(filteredAndSortedVoices.map(v => v.voice_id));
    } else {
      onChange([]);
    }
  };

  const handleFilterChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const filteredAndSortedVoices = useMemo(() => {
    let filtered = voices;

    if (categoryFilter !== 'all') {
      filtered = filtered.filter(v => v.category === categoryFilter);
    }

    if (searchTerm) {
      filtered = filtered.filter(v => 
        v.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    const [_, sortDir] = sortOrder.split('_');
    const direction = sortDir === 'asc' ? 1 : -1;

    filtered.sort((a, b) => {
        let valA = a.name.toLowerCase();
        let valB = b.name.toLowerCase();
        
        if (valA < valB) return direction;
        if (valA > valB) return -direction;
        return 0;
    });

    return filtered;
  }, [voices, searchTerm, categoryFilter, sortOrder]);

  const allFilteredSelected = filteredAndSortedVoices.length > 0 && 
                             filteredAndSortedVoices.every(v => selectedVoices.includes(v.voice_id));
  const isIndeterminate = !allFilteredSelected && 
                         filteredAndSortedVoices.some(v => selectedVoices.includes(v.voice_id));

  const stopCurrentAudio = () => {
    if (currentAudio.current) {
      currentAudio.current.onended = null;
      currentAudio.current.onerror = null;
      currentAudio.current.pause();
      currentAudio.current.src = '';
      currentAudio.current = null;
    }
    if (currentBlobUrl.current) {
      URL.revokeObjectURL(currentBlobUrl.current);
      currentBlobUrl.current = null;
    }
    setPreviewingVoiceId(null);
    setIsPreviewLoading(false);
  };

  const handlePreviewClick = async (voiceId: string) => {
    if (isPreviewLoading) return;

    if (previewingVoiceId === voiceId) {
      stopCurrentAudio();
    } else {
      stopCurrentAudio();
      setPreviewingVoiceId(voiceId);
      setIsPreviewLoading(true);

      try {
        const audioBlob = await api.getVoicePreview(voiceId);
        const blobUrl = URL.createObjectURL(audioBlob);
        currentBlobUrl.current = blobUrl;

        const audio = new Audio(blobUrl);
        currentAudio.current = audio;

        audio.onended = () => {
          console.log(`Preview finished for ${voiceId}`);
          stopCurrentAudio();
        };
        audio.onerror = (e) => {
          console.error(`Error playing preview for ${voiceId}:`, e);
          notifications.show({
            title: 'Playback Error',
            message: `Could not play preview for voice ${voiceId}.`,
            color: 'red',
            icon: <IconAlertCircle />
          });
          stopCurrentAudio();
        };

        await audio.play();
        setIsPreviewLoading(false);
        console.log(`Playing preview for ${voiceId}`);

      } catch (error: any) {
        console.error(`Failed to fetch/play preview for ${voiceId}:`, error);
        notifications.show({
          title: 'Preview Failed',
          message: error.message || 'Could not generate preview for this voice.',
          color: 'red',
          icon: <IconAlertCircle />
        });
        stopCurrentAudio();
      }
    }
  };

  const categories = useMemo(() => {
      const uniqueCategories = new Set<string>();
      voices.forEach(v => {
          if(v.category) uniqueCategories.add(v.category);
      });
      return Array.from(uniqueCategories).sort();
  }, [voices]);

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px', borderRadius: '5px', backgroundColor: '#fff' }}>
      <h4>Select Voices for Generation</h4>
      
      <div style={{ display: 'flex', gap: '10px', marginBottom: '15px', flexWrap: 'wrap' }}>
        <Input 
          placeholder="Search voices..." 
          value={searchTerm}
          onChange={handleFilterChange}
          style={{ flexGrow: 1, minWidth: '150px' }}
        />
        <Select
          placeholder="Filter by category"
          value={categoryFilter}
          onChange={(value) => setCategoryFilter(value || 'all')}
          data={[
            { value: 'all', label: 'All Categories' },
            ...categories.map(cat => ({ value: cat, label: cat }))
          ]}
          clearable
          style={{ minWidth: '150px' }}
        />
         <Select
          id="voice-sort-order"
          placeholder="Sort by"
          value={sortOrder}
          onChange={(value) => setSortOrder(value || 'name_asc')}
          data={[
            { value: 'name_asc', label: 'Name (A-Z)' },
            { value: 'name_desc', label: 'Name (Z-A)' },
          ]}
           style={{ minWidth: '130px' }}
        />
      </div>

      {loading && <p>Loading voices...</p>}
      {fetchError && <p style={{ color: 'red' }}>{fetchError}</p>}
      
      {!loading && !fetchError && (
        <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
          <Table stickyHeader striped highlightOnHover withTableBorder withColumnBorders>
            <Table.Thead>
              <Table.Tr>
                <Table.Th style={{ width: '50px' }}></Table.Th>
                <Table.Th style={{ width: '50px' }}>
                  <Checkbox 
                    checked={allFilteredSelected}
                    indeterminate={isIndeterminate}
                    onChange={(e) => handleSelectAll(e.currentTarget.checked)}
                    title="Select/Deselect All Visible"
                  />
                </Table.Th>
                <Table.Th>Name</Table.Th>
                <Table.Th>Category</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {filteredAndSortedVoices.map(voice => (
                <Table.Tr key={voice.voice_id}>
                  <Table.Td ta="center">
                    <Tooltip label={previewingVoiceId === voice.voice_id ? "Stop Preview" : "Preview Voice"} position="right" withArrow>
                       <ActionIcon 
                          variant="subtle" 
                          onClick={() => handlePreviewClick(voice.voice_id)}
                          loading={isPreviewLoading && previewingVoiceId === voice.voice_id}
                          disabled={isPreviewLoading && previewingVoiceId !== voice.voice_id}
                       >
                          {previewingVoiceId === voice.voice_id ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
                       </ActionIcon>
                     </Tooltip>
                  </Table.Td>
                  <Table.Td>
                    <Checkbox 
                      checked={selectedVoices.includes(voice.voice_id)}
                      onChange={(e) => handleSelectChange(voice.voice_id, e.currentTarget.checked)}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Tooltip 
                       label={voice.description || 'No description available'} 
                       position="top-start" 
                       withArrow 
                       multiline 
                       w={350}
                       zIndex={1000}
                    >
                      <span>{voice.name}</span>
                    </Tooltip>
                  </Table.Td>
                  <Table.Td>
                     <Tooltip 
                        label={voice.description || 'No description available'} 
                        position="top-start" 
                        withArrow 
                        multiline 
                        w={350}
                        zIndex={1000}
                     >
                       <span>{voice.category || 'N/A'}</span>
                     </Tooltip>
                  </Table.Td>
                </Table.Tr>
              ))}
               {filteredAndSortedVoices.length === 0 && (
                   <Table.Tr><Table.Td colSpan={4} align="center">No voices match filters.</Table.Td></Table.Tr>
               )}
            </Table.Tbody>
          </Table>
        </div>
      )}
    </div>
  );
};

export default VoiceSelector; 