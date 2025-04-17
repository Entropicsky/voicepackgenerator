// frontend/src/contexts/RankingContext.tsx
import React, { createContext, useState, useContext, useCallback, ReactNode, useEffect, useMemo } from 'react';
import { BatchMetadata, Take } from '../types';
import { api } from '../api';
import useDebouncedCallback from '../hooks/useDebouncedCallback'; // Assuming a debounce hook

interface RankingContextType {
  batchMetadata: BatchMetadata | null;
  loading: boolean;
  error: string | null;
  takesByLine: Record<string, Take[]>;
  setTakeRankWithinLine: (file: string, rank: number | null) => void;
  lockCurrentBatch: () => Promise<void>;
  isLocked: boolean;
  selectedLineKey: string | null;
  setSelectedLineKey: (lineKey: string | null) => void;
  currentLineRankedTakes: (Take | null)[]; // Index 0=Rank1, ..., 4=Rank5
}

const RankingContext = createContext<RankingContextType | undefined>(undefined);

interface RankingProviderProps {
  batchId: string;
  children: ReactNode;
}

const DEBOUNCE_DELAY = 500; // ms to wait before sending PATCH request

export const RankingProvider: React.FC<RankingProviderProps> = ({ batchId, children }) => {
  const [batchMetadata, setBatchMetadata] = useState<BatchMetadata | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [takesByLine, setTakesByLine] = useState<Record<string, Take[]>>({});
  const [isLocked, setIsLocked] = useState<boolean>(false); // Track lock status
  const [selectedLineKey, setSelectedLineKey] = useState<string | null>(null); // State for selected line

  // --- Fetch Metadata ---
  useEffect(() => {
    const fetchMetadata = async () => {
      if (!batchId) return;
      setLoading(true);
      setError(null);
      setBatchMetadata(null);
      setTakesByLine({});
      setIsLocked(false);
      console.log(`Fetching metadata for batch: ${batchId}`);
      try {
        const metadata: BatchMetadata = await api.getBatchMetadata(batchId);
        setBatchMetadata(metadata);

        // Check lock status (might be redundant if metadata includes it, but good practice)
        // This requires an `is_locked` field in the metadata or a separate API call.
        // For now, assume metadata contains ranked_at_utc which implies locked.
        setIsLocked(metadata.ranked_at_utc !== null);

        // Group takes by line
        const grouped: Record<string, Take[]> = {};
        for (const take of metadata.takes) {
          if (!grouped[take.line]) {
            grouped[take.line] = [];
          }
          grouped[take.line].push(take);
        }
        // Ensure takes within each line are sorted initially (e.g., by take number)
        for (const line in grouped) {
          grouped[line].sort((a: Take, b: Take) => a.take_number - b.take_number);
        }
        setTakesByLine(grouped);
        // Auto-select the first line if available
        const firstLineKey = Object.keys(grouped).sort()[0];
        setSelectedLineKey(firstLineKey || null);

      } catch (err: any) {
        setError(`Failed to load batch metadata: ${err.message}`);
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchMetadata();
  }, [batchId]); // Refetch if batchId changes

  // --- Rank Update Logic ---
  const updateApiRank = useCallback(async (updates: { file: string, rank: number | null }[]) => {
    if (!batchId || isLocked || updates.length === 0) return;
    console.log(`API Call: Updating ${updates.length} ranks for batch ${batchId}`);
    try {
      // TODO: Implement backend bulk update endpoint?
      // For now, send individual requests sequentially (could be slow)
      for (const update of updates) {
        console.log(`   -> Updating ${update.file} to rank ${update.rank}`);
        await api.updateTakeRank(batchId, update.file, update.rank);
        // Add a small delay between requests?
        // await new Promise(res => setTimeout(res, 50)); 
      }
    } catch (err: any) {
      console.error(`Failed to update ranks:`, err);
      setError(`Failed to save ranks: ${err.message}`);
      // TODO: Re-fetch metadata on failure to sync state?
    }
  }, [batchId, isLocked]);

  const debouncedUpdateApiRank = useDebouncedCallback(updateApiRank, DEBOUNCE_DELAY);

  // Renamed function with LINE-SCOPED cascade logic
  const setTakeRankWithinLine = useCallback((file: string, newRank: number | null) => {
    if (isLocked || !batchMetadata) return;

    let allTakes: Take[] = [...batchMetadata.takes]; // Work with a mutable copy
    let rankUpdates: { file: string, rank: number | null }[] = [];
    let changed = false;

    // Find the take being changed and its line
    const targetTakeIndex = allTakes.findIndex(t => t.file === file);
    if (targetTakeIndex === -1) {
        console.error(`Take ${file} not found in metadata.`);
        return;
    }
    const targetTake = allTakes[targetTakeIndex];
    const targetLine = targetTake.line;
    const currentRank = targetTake.rank;

    if (currentRank === newRank) return; // No change needed

    console.log(`Setting rank for ${file} (Line: ${targetLine}) from ${currentRank} to ${newRank}`);
    changed = true;
    // Prepare the update for the target take
    rankUpdates.push({ file: file, rank: newRank });
    allTakes[targetTakeIndex] = { ...targetTake, rank: newRank, ranked_at: newRank !== null ? new Date().toISOString() : null };

    // Filter takes to only those belonging to the SAME LINE for cascading
    let lineTakesIndices = allTakes
        .map((take, index) => ({ take, index })) // Keep track of original indices
        .filter(({ take }) => take.line === targetLine);

    // Handle unranking - only affects the target take
    if (newRank === null) {
        // No cascading needed when unranking
    } else {
        // Handle ranking (1-5) within the line
        let rankToShift = newRank;
        let currentTakeInLineIndex = lineTakesIndices.findIndex(({ take }) => take.file === file); // Index within lineTakes

        // Find if another take *within the same line* already has the target rank
        let takeToShiftLineIndex = lineTakesIndices.findIndex(({ take }) => take.rank === rankToShift && take.file !== file);

        // Cascade downwards *within the line*
        while (takeToShiftLineIndex !== -1 && rankToShift <= 5) {
            const nextRank = rankToShift + 1;
            const originalIndexToShift = lineTakesIndices[takeToShiftLineIndex].index;
            const fileToShift = allTakes[originalIndexToShift].file;

            if (nextRank > 5) {
                 console.log(` -> Bumping ${fileToShift} (Line: ${targetLine}) from ${rankToShift} to unranked`);
                 rankUpdates.push({ file: fileToShift, rank: null });
                 allTakes[originalIndexToShift] = { ...allTakes[originalIndexToShift], rank: null, ranked_at: null };
                 takeToShiftLineIndex = -1; // End cascade
            } else {
                 console.log(` -> Bumping ${fileToShift} (Line: ${targetLine}) from ${rankToShift} to ${nextRank}`);
                 rankUpdates.push({ file: fileToShift, rank: nextRank });
                 allTakes[originalIndexToShift] = { ...allTakes[originalIndexToShift], rank: nextRank, ranked_at: new Date().toISOString() };
                 rankToShift = nextRank;
                 // Refresh lineTakesIndices after modification before finding next one
                 lineTakesIndices = allTakes
                     .map((take, index) => ({ take, index }))
                     .filter(({ take }) => take.line === targetLine);
                 takeToShiftLineIndex = lineTakesIndices.findIndex(({ take }) => take.rank === rankToShift && take.file !== fileToShift);
            }
        }
    }

    if (changed) {
      // Update local state immediately
      const newTakesByLine = allTakes.reduce((acc: Record<string, Take[]>, take: Take) => {
        (acc[take.line] = acc[take.line] || []).push(take);
        // Keep takes sorted within each line group
        if (acc[take.line].length > 1) {
            acc[take.line].sort((a: Take, b: Take) => a.take_number - b.take_number);
        }
        return acc;
      }, {} as Record<string, Take[]>);

      setBatchMetadata((prev: BatchMetadata | null) => prev ? { ...prev, takes: allTakes } : null);
      setTakesByLine(newTakesByLine);

      // Call debounced API update with all accumulated changes
      if (rankUpdates.length > 0) {
          debouncedUpdateApiRank(rankUpdates);
      }
    }

  }, [batchMetadata, isLocked, debouncedUpdateApiRank]);

  // --- Lock Batch Logic ---
   const lockCurrentBatch = useCallback(async () => {
    if (!batchId || isLocked) return;
    console.log(`API Call: Locking batch ${batchId}`);
    try {
        await api.lockBatch(batchId);
        setIsLocked(true);
        // Update local metadata state as well
        setBatchMetadata((prevMeta: BatchMetadata | null) => prevMeta ? { ...prevMeta, ranked_at_utc: new Date().toISOString() } : null);
    } catch (err: any) {
        console.error(`Failed to lock batch ${batchId}:`, err);
        setError(`Failed to lock batch: ${err.message}`);
        // Do not set isLocked to true if API fails
    }
  }, [batchId, isLocked]);

  // --- Memoized Ranked Takes for CURRENTLY SELECTED line ---
  const currentLineRankedTakes = useMemo<(Take | null)[]>(() => {
    const ranks: (Take | null)[] = Array(5).fill(null);
    if (selectedLineKey && batchMetadata?.takes) {
        const lineTakes = batchMetadata.takes.filter((t: Take) => t.line === selectedLineKey);
        for (const take of lineTakes) {
            if (take.rank !== null && take.rank >= 1 && take.rank <= 5) {
                if (ranks[take.rank - 1] === null) {
                  ranks[take.rank - 1] = take;
                }
            }
        }
    }
    return ranks;
  }, [batchMetadata, selectedLineKey]);

  // --- Context Value ---
  const value: RankingContextType = {
    batchMetadata,
    loading,
    error,
    takesByLine,
    setTakeRankWithinLine,
    lockCurrentBatch,
    isLocked,
    selectedLineKey,
    setSelectedLineKey,
    currentLineRankedTakes
  };

  return <RankingContext.Provider value={value}>{children}</RankingContext.Provider>;
};

// Hook to use the context
export const useRanking = (): RankingContextType => {
  const context = useContext(RankingContext);
  if (context === undefined) {
    throw new Error('useRanking must be used within a RankingProvider');
  }
  return context;
}; 