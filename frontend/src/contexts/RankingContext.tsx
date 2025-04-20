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

// <<< NEW: Status for Crop Task >>>
interface CropJobStatus {
    taskId: string;
    status: TaskStatus['status'] | 'SUBMITTED'; // Same statuses as regen
    error?: string | null;
}

interface RankingContextType {
  batchId: string;
  batchMetadata: BatchMetadata | null;
  loading: boolean;
  error: string | null;
  takesByLine: Record<string, Take[]>;
  setTakeRankWithinLine: (file: string, rank: number | null) => void;
  isLocked: boolean;
  selectedLineKey: string | null;
  setSelectedLineKey: (lineKey: string | null) => void;
  currentLineRankedTakes: (Take | null)[]; // Index 0=Rank1, ..., 4=Rank5
  refetchMetadata: () => void;
  // NEW: State and function for tracking line regenerations
  lineRegenerationStatus: Record<string, LineRegenerationJobStatus>;
  startLineRegeneration: (lineKey: string, taskId: string) => void;
  // >> ADDED: State for single audio playback control
  currentlyPlayingTakeFile: string | null;
  setCurrentlyPlayingTakeFile: (file: string | null) => void;
  // <<< NEW: Crop Status Tracking >>>
  cropStatusByTakeFile: Record<string, CropJobStatus>;
  startCropTaskTracking: (takeFile: string, taskId: string) => void;
}

const RankingContext = createContext<RankingContextType | undefined>(undefined);

interface RankingProviderProps {
  batchId: string;
  children: ReactNode;
}

const DEBOUNCE_DELAY = 500; // ms to wait before sending PATCH request
const LINE_REGEN_POLL_INTERVAL = 4000; // ms to poll for line regen status
const CROP_POLL_INTERVAL = 4000; // Same interval as regen for now

export const RankingProvider: React.FC<RankingProviderProps> = ({ batchId, children }) => {
  console.log(`[RankingProvider] Initializing with batchId prop: ${batchId}`); 
  const [batchMetadata, setBatchMetadata] = useState<BatchMetadata | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [takesByLine, setTakesByLine] = useState<Record<string, Take[]>>({});
  const [isLocked, setIsLocked] = useState<boolean>(false); // Track lock status
  const [selectedLineKey, setSelectedLineKey] = useState<string | null>(null);
  // NEW: State for line regeneration tracking
  const [lineRegenerationStatus, setLineRegenerationStatus] = useState<Record<string, LineRegenerationJobStatus>>({}); 
  // >> ADDED: State for playback control
  const [currentlyPlayingTakeFile, setCurrentlyPlayingTakeFile] = useState<string | null>(null);
  // <<< NEW: Crop Status State >>>
  const [cropStatusByTakeFile, setCropStatusByTakeFile] = useState<Record<string, CropJobStatus>>({});
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null); // Ref for regen interval ID
  const cropPollingIntervalRef = useRef<NodeJS.Timeout | null>(null); // Ref for crop interval ID

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
    setCurrentlyPlayingTakeFile(null); // >> ADDED: Reset playing take on batch change
    setCropStatusByTakeFile({}); // <<< Reset crop status on batch change >>>
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

  // <<< NEW: Crop Task Tracking Logic >>>
  const startCropTaskTracking = useCallback((takeFile: string, taskId: string) => {
      console.log(`[RankingContext] Starting to track crop task ${taskId} for take ${takeFile}`);
      setCropStatusByTakeFile(prev => ({
          ...prev,
          [takeFile]: { taskId, status: 'SUBMITTED', error: null }
      }));
      // Trigger polling immediately if not already running (or rely on useEffect dependency)
  }, []);

  // <<< NEW: Polling effect for active Crop tasks >>>
  useEffect(() => {
    const activeCrops = Object.entries(cropStatusByTakeFile)
        .filter(([_, job]) => job.status !== 'SUCCESS' && job.status !== 'FAILURE');

    const pollCropStatuses = async () => {
        if (activeCrops.length === 0) {
             if (cropPollingIntervalRef.current) {
                 console.log("[RankingContext Crop Polling] No active crops, clearing interval.");
                 clearInterval(cropPollingIntervalRef.current);
                 cropPollingIntervalRef.current = null;
             }
            return;
        }
        
        console.log(`[RankingContext Crop Polling] Checking status for ${activeCrops.length} active crop tasks...`);

        const statusPromises = activeCrops.map(async ([takeFile, job]) => {
            try {
                // Use the SAME task status endpoint
                const taskStatus = await api.getTaskStatus(job.taskId); 
                return { takeFile, taskStatus };
            } catch (err: any) {
                console.error(`[RankingContext Crop Polling] Error fetching status for crop task ${job.taskId} (file ${takeFile}):`, err);
                return { takeFile, taskStatus: { task_id: job.taskId, status: 'FAILURE', info: { error: `Failed to fetch status: ${err.message}` } } as TaskStatus };
            }
        });

        const results = await Promise.all(statusPromises);

        let stateUpdates: Record<string, CropJobStatus> = {};
        let stillActive = false;

        results.forEach(({ takeFile, taskStatus }) => {
            const currentStatus = cropStatusByTakeFile[takeFile];
            if (currentStatus && currentStatus.status !== taskStatus.status) {
                console.log(`[RankingContext Crop Polling] Status update for file ${takeFile} (Task ${taskStatus.task_id}): ${currentStatus.status} -> ${taskStatus.status}`);
                stateUpdates[takeFile] = {
                    taskId: taskStatus.task_id,
                    status: taskStatus.status,
                    error: taskStatus.status === 'FAILURE' ? (taskStatus.info?.error || 'Unknown error') : null
                };

                if (taskStatus.status !== 'SUCCESS' && taskStatus.status !== 'FAILURE') {
                    stillActive = true; 
                }
                // If SUCCESS, we can potentially clear the status or mark as done
                // Let's just clear it for now after success
                if (taskStatus.status === 'SUCCESS') {
                     console.log(`[RankingContext Crop Polling] Crop for ${takeFile} succeeded. Removing from tracking.`);
                     // We will remove it after updating state
                } else if (taskStatus.status === 'FAILURE'){
                     console.error(`[RankingContext Crop Polling] Crop task ${taskStatus.task_id} for ${takeFile} FAILED: ${stateUpdates[takeFile].error}`);
                }
            } else if (currentStatus && currentStatus.status !== 'SUCCESS' && currentStatus.status !== 'FAILURE'){
                 stillActive = true; // Mark that polling should continue if unchanged and not terminal
            }
        });

        if (Object.keys(stateUpdates).length > 0) {
            setCropStatusByTakeFile(prev => {
                const newState = { ...prev, ...stateUpdates };
                // Remove entries that just succeeded
                Object.entries(stateUpdates).forEach(([file, job]) => {
                    if (job.status === 'SUCCESS') {
                        delete newState[file];
                    }
                });
                return newState;
            });
        }
         
        if (!stillActive && cropPollingIntervalRef.current) {
            console.log("[RankingContext Crop Polling] All crops terminal or finished, clearing interval.");
            clearInterval(cropPollingIntervalRef.current);
            cropPollingIntervalRef.current = null;
        }
    };

    if (activeCrops.length > 0 && !cropPollingIntervalRef.current) {
        console.log("[RankingContext Crop Polling] Active crops detected, setting up interval.");
        cropPollingIntervalRef.current = setInterval(pollCropStatuses, CROP_POLL_INTERVAL);
    }

    // Cleanup function
    return () => {
        if (cropPollingIntervalRef.current) {
            console.log("[RankingContext Crop Polling] Cleanup: Clearing interval.");
            clearInterval(cropPollingIntervalRef.current);
            cropPollingIntervalRef.current = null;
        }
    };
  }, [cropStatusByTakeFile, batchId]); // Dependencies

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

  // --- Memoized Ranked Takes for CURRENTLY SELECTED line ---
  // Calculate directly without useMemo
  const calculateRankedTakes = () => {
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
  };
  const currentLineRankedTakes = calculateRankedTakes();

  // --- Context Value ---
  const value: RankingContextType = {
    batchId,
    batchMetadata,
    loading,
    error,
    takesByLine,
    setTakeRankWithinLine,
    isLocked,
    selectedLineKey,
    setSelectedLineKey,
    currentLineRankedTakes,
    refetchMetadata: fetchMetadata,
    // NEW: Expose regeneration state and trigger function
    lineRegenerationStatus,
    startLineRegeneration,
    // >> ADDED: Expose playback control state and function
    currentlyPlayingTakeFile,
    setCurrentlyPlayingTakeFile,
    // <<< NEW: Expose crop status and tracking function >>>
    cropStatusByTakeFile,
    startCropTaskTracking
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