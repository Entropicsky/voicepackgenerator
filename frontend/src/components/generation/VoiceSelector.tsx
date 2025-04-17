import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { api } from '../../api';
import { VoiceOption } from '../../types';
import useDebouncedCallback from '../../hooks/useDebouncedCallback';

interface VoiceSelectorProps {
  selectedVoices: string[]; // Array of selected voice IDs
  onChange: (selectedIds: string[]) => void;
}

const SEARCH_DEBOUNCE = 300; // Debounce search input

const VoiceSelector: React.FC<VoiceSelectorProps> = ({ selectedVoices, onChange }) => {
  const [allFetchedVoices, setAllFetchedVoices] = useState<VoiceOption[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // State for filters and sorting
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [filterCategory, setFilterCategory] = useState<string>('all'); // Default to 'all'
  const [sortBy, setSortBy] = useState<'name' | 'created_at_unix' | 'category'>('category'); // Default sort
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  const debouncedSetSearchTerm = useDebouncedCallback(setSearchTerm, SEARCH_DEBOUNCE);

  // Fetch voices when filters/sort change
  useEffect(() => {
    const fetchVoices = async () => {
      setLoading(true);
      setError(null);
      try {
        // Pass the selected category directly to the API if not 'all'
        const apiCategory = filterCategory === 'all' ? undefined : filterCategory;
        const apiSort = sortBy === 'category' ? 'name' : sortBy;
        const apiSortDir = sortDirection;

        console.log(`Fetching with category: ${apiCategory}, search: ${searchTerm}`); // Log params

        const voices = await api.getVoices({
            search: searchTerm || undefined,
            category: apiCategory,
            sort: apiSort,
            sort_direction: apiSortDir,
            page_size: 100
        });
        setAllFetchedVoices(voices);
      } catch (err: any) {
        setError(`Failed to load voices: ${err.message}`);
        console.error(err);
        setAllFetchedVoices([]); // Clear list on error
      } finally {
        setLoading(false);
      }
    };

    fetchVoices();
  }, [searchTerm, filterCategory, sortBy, sortDirection]);

  // Client-side sorting (Prioritize specific categories if needed, then apply selected sort)
  const displayedVoices = useMemo(() => {
    // API handles filtering by category, so we just sort the results
    return [...allFetchedVoices].sort((a, b) => {
        // --- Optional: Prioritize certain categories --- 
        const priorityOrder = ['generated', 'cloned']; // Voices likely created by the user
        const catA = a.category || '';
        const catB = b.category || '';
        const priorityA = priorityOrder.indexOf(catA);
        const priorityB = priorityOrder.indexOf(catB);

        // If one has priority and the other doesn't (or has lower priority)
        if (priorityA !== -1 && (priorityB === -1 || priorityA < priorityB)) return -1;
        if (priorityB !== -1 && (priorityA === -1 || priorityB < priorityA)) return 1;
        // If priorities are the same or neither are priority categories, proceed to selected sort

        // --- Apply Selected Sort --- 
        const field = sortBy;
        const dir = sortDirection === 'asc' ? 1 : -1;

        if (field === 'category') { // Client-side category sort
            return catA.localeCompare(catB) * dir;
        }

        const valA = field === 'name' ? (a[field] || '') : 0; // Only support name sort from API for now
        const valB = field === 'name' ? (b[field] || '') : 0;

        if (typeof valA === 'string' && typeof valB === 'string') {
            return valA.localeCompare(valB) * dir;
        }
        return 0;
    });
  }, [allFetchedVoices, sortBy, sortDirection]);

  const handleCheckboxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { value, checked } = event.target;
    let newSelectedVoices: string[];

    if (checked) {
      newSelectedVoices = [...selectedVoices, value];
    } else {
      newSelectedVoices = selectedVoices.filter(id => id !== value);
    }
    onChange(newSelectedVoices);
  };

  return (
    <div>
      <h4>Available Voices (Select one or more):</h4>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '10px', alignItems: 'center' }}>
        <input 
            type="text"
            placeholder="Search voices..."
            onChange={(e) => debouncedSetSearchTerm(e.target.value)}
            style={{ padding: '5px' }}
        />
        <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} style={{ padding: '5px' }}>
            <option value="all">All Categories</option>
            <option value="generated">Generated</option>
            <option value="cloned">Cloned</option>
            <option value="professional">Professional</option>
            <option value="premade">Premade</option>
            {/* Add workspace, community, default if needed */}
        </select>
         <button onClick={() => { setSortBy('name'); setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')}}>
             Sort by Name ({sortBy === 'name' ? (sortDirection === 'asc' ? '↑' : '↓') : '-'})
         </button>
      </div>

      <div style={{ maxHeight: '250px', overflowY: 'scroll', border: '1px solid #ccc', padding: '10px' }}>
        {loading && <p>Loading voices...</p>}
        {error && <p style={{ color: 'red' }}>{error}</p>}
        {!loading && !error && displayedVoices.length === 0 && (
          <p>No voices found matching criteria.</p>
        )}
        {!loading && !error && displayedVoices.length > 0 && (
          displayedVoices.map((voice) => (
            <div key={voice.voice_id}>
              <input
                type="checkbox"
                id={`voice-${voice.voice_id}`}
                value={voice.voice_id}
                checked={selectedVoices.includes(voice.voice_id)}
                onChange={handleCheckboxChange}
              />
              <label htmlFor={`voice-${voice.voice_id}`}>
                  {voice.name} 
                  <small style={{color: '#555'}}> ({voice.category || 'Unknown'} / {voice.voice_id})</small>
              </label>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default VoiceSelector; 