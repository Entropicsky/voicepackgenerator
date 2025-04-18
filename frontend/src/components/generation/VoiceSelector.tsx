import React, { useState, useEffect, useMemo } from 'react';
import { Checkbox, Table, Input, Select } from '@mantine/core';
import { VoiceOption } from '../../types';
import { useVoiceContext } from '../../contexts/VoiceContext';

interface VoiceSelectorProps {
  selectedVoices: string[];
  onChange: (selectedIds: string[]) => void;
}

const VoiceSelector: React.FC<VoiceSelectorProps> = ({ selectedVoices, onChange }) => {
  const { voices, loading, error: fetchError } = useVoiceContext();

  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [sortOrder, setSortOrder] = useState<string>('name_asc');

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

    const [sortKey, sortDir] = sortOrder.split('_');
    filtered.sort((a, b) => {
        let valA = a.name.toLowerCase();
        let valB = b.name.toLowerCase();
        
        if (valA < valB) return sortDir === 'asc' ? -1 : 1;
        if (valA > valB) return sortDir === 'asc' ? 1 : -1;
        return 0;
    });

    return filtered;
  }, [voices, searchTerm, categoryFilter, sortOrder]);

  const allFilteredSelected = filteredAndSortedVoices.length > 0 && 
                             filteredAndSortedVoices.every(v => selectedVoices.includes(v.voice_id));
  const isIndeterminate = !allFilteredSelected && 
                         filteredAndSortedVoices.some(v => selectedVoices.includes(v.voice_id));

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
          onChange={(e) => setSearchTerm(e.target.value)}
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
                  <Table.Td>
                    <Checkbox 
                      checked={selectedVoices.includes(voice.voice_id)}
                      onChange={(e) => handleSelectChange(voice.voice_id, e.currentTarget.checked)}
                    />
                  </Table.Td>
                  <Table.Td>{voice.name}</Table.Td>
                  <Table.Td>{voice.category || 'N/A'}</Table.Td>
                </Table.Tr>
              ))}
               {filteredAndSortedVoices.length === 0 && (
                   <Table.Tr><Table.Td colSpan={3} align="center">No voices match filters.</Table.Td></Table.Tr>
               )}
            </Table.Tbody>
          </Table>
        </div>
      )}
    </div>
  );
};

export default VoiceSelector; 