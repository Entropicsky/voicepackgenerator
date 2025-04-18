// frontend/src/contexts/RankingContext.tsx
import React, { createContext, useState, useContext, useCallback, ReactNode, useEffect, useMemo, useRef } from 'react';
import { BatchMetadata, Take, TaskStatus } from '../types';
import { api } from '../api';
import useDebouncedCallback from '../hooks/useDebouncedCallback'; // Assuming a debounce hook

// Define the structure for tracking line regeneration status
interface LineRegenerationJobStatus {
    taskId: string;
    status: TaskStatus['status'] | 'SUBMITTED'; // Add SUBMITTED as initial client-side status
    info?: any;
    error?: string | null;
}

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
  refetchMetadata: () => void;
  // NEW: State and function for tracking line regenerations
  lineRegenerationStatus: Record<string, LineRegenerationJobStatus>; 
  startLineRegeneration: (lineKey: string, taskId: string) => void;
}

const RankingContext = createContext<RankingContextType | undefined>(undefined);

interface RankingProviderProps {
  batchId: string;
  children: ReactNode;
}

const DEBOUNCE_DELAY = 500; // ms to wait before sending PATCH request
const LINE_REGEN_POLL_INTERVAL = 4000; // ms to poll for line regen status

export const RankingProvider: React.FC<RankingProviderProps> = ({ batchId, children }) => {
  const [batchMetadata, setBatchMetadata] = useState<BatchMetadata | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [takesByLine, setTakesByLine] = useState<Record<string, Take[]>>({});
  const [isLocked, setIsLocked] = useState<boolean>(false); // Track lock status
  const [selectedLineKey, setSelectedLineKey] = useState<string | null>(null);
  // NEW: State for line regeneration tracking
  const [lineRegenerationStatus, setLineRegenerationStatus] = useState<Record<string, LineRegenerationJobStatus>>({}); 
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null); // Ref for interval ID

  // --- Fetch Metadata ---
  const fetchMetadata = useCallback(async () => {
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
      setIsLocked(metadata.ranked_at_utc !== null);
      const grouped: Record<string, Take[]> = {};
      for (const take of metadata.takes) {
        if (!grouped[take.line]) {
          grouped[take.line] = [];
        }
        grouped[take.line].push(take);
      }
      for (const line in grouped) {
        grouped[line].sort((a: Take, b: Take) => a.take_number - b.take_number);
      }
      setTakesByLine(grouped);
    } catch (err: any) {
      setError(`Failed to load batch metadata: ${err.message}`);
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [batchId]);

  // Effect to fetch data on mount/batchId change
  useEffect(() => {
    setSelectedLineKey(null); // Reset selected line when batch ID changes
    setLineRegenerationStatus({}); // Clear regen status on batch change
    fetchMetadata();
  }, [fetchMetadata]);

  // NEW Effect to auto-select the first line *after* data is loaded
  useEffect(() => {
    // Only run if not loading, no error, some lines exist, and no line is currently selected
    if (!loading && !error && Object.keys(takesByLine).length > 0 && selectedLineKey === null) {
      const firstLineKey = Object.keys(takesByLine).sort()[0];
      console.log(`[RankingContext] Auto-selecting first line: ${firstLineKey}`);
      setSelectedLineKey(firstLineKey);
    }
    // Dependencies: trigger when loading finishes or takesByLine data arrives
  }, [loading, error, takesByLine, selectedLineKey, setSelectedLineKey]);

  // --- NEW: Logic for handling line regeneration --- 

  // Function to fetch takes for a specific line and update state
  const fetchTakesForLine = useCallback(async (lineKey: string) => {
      if (!batchId) return;
      console.log(`[RankingContext] Fetching updated takes for line: ${lineKey}`);
      try {
          const updatedTakes = await api.getLineTakes(batchId, lineKey);
          // Update the takesByLine state
          setTakesByLine(prevTakes => ({
              ...prevTakes,
              [lineKey]: updatedTakes.sort((a, b) => a.take_number - b.take_number)
          }));
          // Update the batchMetadata state
          setBatchMetadata((prevMeta: BatchMetadata | null) => {
              if (!prevMeta) return null;
              // Filter out old takes for this line, then add new ones
              const otherTakes = prevMeta.takes.filter((t: Take) => t.line !== lineKey);
              return {
                  ...prevMeta,
                  takes: [...otherTakes, ...updatedTakes]
              };
          });
          console.log(`[RankingContext] Successfully updated takes for line: ${lineKey}`);
      } catch (err: any) {
          console.error(`[RankingContext] Failed to fetch takes for line ${lineKey}:`, err);
          // Optionally surface this error to the user?
          setError(`Failed to refresh takes for line ${lineKey}: ${err.message}`); 
      }
  }, [batchId]);

  // Function called by modals to start tracking a new regen job
  const startLineRegeneration = useCallback((lineKey: string, taskId: string) => {
      console.log(`[RankingContext] Starting to track regeneration for line ${lineKey}, task ${taskId}`);
      setLineRegenerationStatus(prev => ({
          ...prev,
          [lineKey]: { taskId, status: 'SUBMITTED', info: 'Job submitted', error: null }
      }));
      // Trigger polling immediately if not already running (or rely on useEffect dependency)
  }, []);

  // Polling effect for active line regenerations
  useEffect(() => {
    const activeRegens = Object.entries(lineRegenerationStatus)
        .filter(([_, job]) => job.status !== 'SUCCESS' && job.status !== 'FAILURE');

    const pollStatuses = async () => {
        if (activeRegens.length === 0) {
             if (pollingIntervalRef.current) {
                 console.log("[RankingContext Polling] No active regenerations, clearing interval.");
                 clearInterval(pollingIntervalRef.current);
                 pollingIntervalRef.current = null;
             }
            return;
        }
        
        console.log(`[RankingContext Polling] Checking status for ${activeRegens.length} active line regenerations...`);

        const statusPromises = activeRegens.map(async ([lineKey, job]) => {
            try {
                const taskStatus = await api.getTaskStatus(job.taskId);
                return { lineKey, taskStatus };
            } catch (err: any) {
                console.error(`[RankingContext Polling] Error fetching status for task ${job.taskId} (line ${lineKey}):`, err);
                // Create a synthetic FAILURE status on fetch error
                return { lineKey, taskStatus: { task_id: job.taskId, status: 'FAILURE', info: { error: `Failed to fetch status: ${err.message}` } } as TaskStatus };
            }
        });

        const results = await Promise.all(statusPromises);

        let needsTakeRefresh: string[] = [];
        let stateUpdates: Record<string, LineRegenerationJobStatus> = {};
        let stillActive = false;

        results.forEach(({ lineKey, taskStatus }) => {
            const currentStatus = lineRegenerationStatus[lineKey];
            // Only update if status actually changed
            if (currentStatus && currentStatus.status !== taskStatus.status) {
                console.log(`[RankingContext Polling] Status update for line ${lineKey} (Task ${taskStatus.task_id}): ${currentStatus.status} -> ${taskStatus.status}`);
                stateUpdates[lineKey] = {
                    taskId: taskStatus.task_id,
                    status: taskStatus.status,
                    info: taskStatus.info,
                    error: taskStatus.status === 'FAILURE' ? (taskStatus.info?.error || 'Unknown error') : null
                };

                if (taskStatus.status === 'SUCCESS') {
                    needsTakeRefresh.push(lineKey);
                } else if (taskStatus.status !== 'FAILURE') {
                    stillActive = true; // Mark that polling should continue
                }
            } else if (currentStatus && currentStatus.status !== 'SUCCESS' && currentStatus.status !== 'FAILURE'){
                 stillActive = true; // Mark that polling should continue if unchanged and not terminal
            }
        });

        if (Object.keys(stateUpdates).length > 0) {
            setLineRegenerationStatus(prev => ({
                ...prev,
                ...stateUpdates
            }));
        }

        if (needsTakeRefresh.length > 0) {
            console.log(`[RankingContext Polling] Triggering take refresh for lines: ${needsTakeRefresh.join(', ')}`);
            // Trigger fetches sequentially for now
            for (const lineKey of needsTakeRefresh) {
                await fetchTakesForLine(lineKey);
                // Optionally clear the status after successful refresh
                // setLineRegenerationStatus(prev => {
                //     const newState = { ...prev };
                //     delete newState[lineKey];
                //     return newState;
                // });
            }
        }
         
        // If no tasks are active anymore after the updates, clear interval
        if (!stillActive && pollingIntervalRef.current) {
            console.log("[RankingContext Polling] All regenerations terminal, clearing interval.");
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
    };

    // Setup interval if there are active regenerations and no interval is running
    if (activeRegens.length > 0 && !pollingIntervalRef.current) {
        console.log("[RankingContext Polling] Active regenerations detected, setting up interval.");
        pollingIntervalRef.current = setInterval(pollStatuses, LINE_REGEN_POLL_INTERVAL);
    }

    // Cleanup function
    return () => {
        if (pollingIntervalRef.current) {
            console.log("[RankingContext Polling] Cleanup: Clearing interval.");
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
    };
  }, [lineRegenerationStatus, fetchTakesForLine, batchId]); // Dependencies: re-run when status changes or batchId changes

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
    currentLineRankedTakes,
    refetchMetadata: fetchMetadata,
    // NEW: Expose regeneration state and trigger function
    lineRegenerationStatus,
    startLineRegeneration 
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