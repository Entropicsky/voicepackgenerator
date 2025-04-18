import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { GenerationJob, TaskStatus } from '../types';
import { Button } from '@mantine/core';

const JOB_LIST_REFRESH_INTERVAL = 15000; // Refresh full list every 15s
const LIVE_STATUS_REFRESH_INTERVAL = 5000; // Refresh live status of active jobs every 5s

const JobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  // State to hold the latest live status fetched from Celery backend
  const [liveStatuses, setLiveStatuses] = useState<Record<string, TaskStatus>>({}); 
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Keep track of jobs that need live status updates
  const activeJobTaskIds = useRef<Set<string>>(new Set()); 

  const fetchJobs = useCallback(async () => {
    // Only set loading on initial fetch or manual refresh
    // setLoading(true); 
    setError(null);
    try {
      console.log("Fetching job list from DB...");
      const fetchedJobs = await api.getJobs();
      setJobs(fetchedJobs);
      // Update the set of active task IDs
      const currentActiveIds = new Set<string>();
      fetchedJobs.forEach(job => {
        if (job.celery_task_id && (job.status === 'PENDING' || job.status === 'STARTED')) {
             currentActiveIds.add(job.celery_task_id);
        }
      });
      activeJobTaskIds.current = currentActiveIds;
      console.log("Active Task IDs needing live status:", Array.from(activeJobTaskIds.current));
      // Trigger immediate live status fetch for active jobs
      fetchLiveStatuses(); 
    } catch (err: any) {
      setError(`Failed to load jobs: ${err.message}`);
      console.error(err);
    } finally {
      // Only set loading false after initial fetch
      if (loading) setLoading(false);
    }
  }, [loading]); // Include loading in deps for initial fetch logic

  const fetchLiveStatuses = useCallback(async () => {
      if (activeJobTaskIds.current.size === 0) {
          // console.log("No active jobs to poll live status for.");
          return; // No active jobs
      }
      console.log("Fetching live statuses for active jobs:", Array.from(activeJobTaskIds.current));
      const statusPromises = Array.from(activeJobTaskIds.current).map(taskId => 
          api.getTaskStatus(taskId).catch(err => {
              console.error(`Error fetching status for ${taskId}:`, err);
              // Return a placeholder error status
              return { task_id: taskId, status: 'FETCH_ERROR', info: { error: err.message } } as TaskStatus; 
          })
      );
      try {
          const statuses = await Promise.all(statusPromises);
          setLiveStatuses(prev => {
              const newStatuses = { ...prev };
              let activeIdsStillActive = false;
              statuses.forEach(status => {
                  if (status) { // Ensure status is not null/undefined from catch
                    newStatuses[status.task_id] = status;
                    // Check if this task is still active after fetch
                    if (!['SUCCESS', 'FAILURE', 'FETCH_ERROR'].includes(status.status)) {
                        activeIdsStillActive = true;
                    }
                  }
              });
              // If no tasks are active anymore, clear the activeJobTaskIds set
              if (!activeIdsStillActive) {
                  activeJobTaskIds.current.clear();
              }
              return newStatuses;
          });
      } catch (err) {
          // Should be caught by individual promise catches, but just in case
          console.error("Error in Promise.all for live statuses:", err);
      }
  }, []); // No dependencies needed here

  // Fetch jobs list periodically
  useEffect(() => {
    fetchJobs(); // Initial fetch
    const jobListIntervalId = setInterval(fetchJobs, JOB_LIST_REFRESH_INTERVAL);
    return () => clearInterval(jobListIntervalId);
  }, [fetchJobs]); // Run once on mount

  // Fetch live statuses periodically only if there are active jobs
  useEffect(() => {
      let liveStatusIntervalId: NodeJS.Timeout | null = null;
      if (activeJobTaskIds.current.size > 0) {
          console.log("Setting up live status polling interval.");
          liveStatusIntervalId = setInterval(fetchLiveStatuses, LIVE_STATUS_REFRESH_INTERVAL);
      } else {
          console.log("No active jobs, clearing live status polling interval.");
      }
      return () => {
          if (liveStatusIntervalId) clearInterval(liveStatusIntervalId);
      };
  }, [fetchLiveStatuses, activeJobTaskIds.current.size]); // Rerun when active jobs change


  const parseJsonSafe = (jsonString: string | null): any => {
    if (!jsonString) return null;
    try {
      return JSON.parse(jsonString);
    } catch (e) {
      console.error("Failed to parse JSON string:", jsonString, e);
      return null;
    }
  };

  const getStatusColor = (status: string): string => {
      switch (status) {
          case 'SUCCESS': return '#e8f5e9'; // Light green
          case 'FAILURE': return '#ffebee'; // Light red
          case 'STARTED':
          case 'PROGRESS':
              return '#e1f5fe'; // Light blue
          case 'PENDING':
              return '#fff9c4'; // Light yellow
          case 'COMPLETED_WITH_ERRORS':
              return '#fff3e0'; // Light orange
          case 'SUBMIT_FAILED':
          case 'FETCH_ERROR':
              return '#fce4ec'; // Light pink/red
          default:
              return '#fff'; // White
      }
  };

  const renderJobStatus = (job: GenerationJob): React.ReactNode => {
      // Prioritize live status if available and job is not terminal in DB
      if (job.celery_task_id && (job.status === 'PENDING' || job.status === 'STARTED')) {
          const liveStatus = liveStatuses[job.celery_task_id];
          if (liveStatus) {
              let displayStatus = liveStatus.status;
              let displayInfo = '';
              if (liveStatus.info) {
                  if (typeof liveStatus.info === 'object') {
                      displayInfo = liveStatus.info.status || liveStatus.info.error || JSON.stringify(liveStatus.info);
                  } else {
                      displayInfo = String(liveStatus.info);
                  }
              }
              return (
                  <> 
                      <span style={{fontWeight: 'bold'}}>{displayStatus}</span>
                      {displayInfo && <><br /><small>({displayInfo})</small></>}
                  </>
              );
          }
      }
      // Fallback to DB status
      return <span style={{fontWeight: 'bold'}}>{job.status}</span>;
  }

  const renderJobDetails = (job: GenerationJob) => {
    // Log the job object to inspect its properties
    console.log("Rendering details for job:", job);

    const params = parseJsonSafe(job.parameters_json);
    const batchIds = parseJsonSafe(job.result_batch_ids_json);

    const isLineRegen = job.job_type === 'line_regen';
    const targetBatchId = job.target_batch_id;
    const targetLineKey = job.target_line_key;

    // Log the conditions
    console.log(`Job ${job.id}: isLineRegen=${isLineRegen}, status=${job.status}, targetBatchId=${targetBatchId}`);

    return (
      <>
        <td>
          <small>
            {params ? (
              <>
                <div><strong>Skin:</strong> {params.skin_name}</div>
                <div><strong>Voices:</strong> {params.voice_ids?.join(', ') || 'N/A'}</div>
                <div><strong>Takes/Line:</strong> {params.variants_per_line}</div>
                {isLineRegen && targetLineKey && <div><strong>Target Line:</strong> {targetLineKey}</div>} 
                {/* Display regeneration specific params? */}
                {isLineRegen && params?.settings && (
                    <div><strong>Regen Params:</strong> 
                        {/* Simple display, could format better */} 
                        Stab:[{params.settings.stability_range?.join('-') || 'N/A'}], 
                        Sim:[{params.settings.similarity_boost_range?.join('-') || 'N/A'}], 
                        Style:[{params.settings.style_range?.join('-') || 'N/A'}], 
                        Speed:[{params.settings.speed_range?.join('-') || 'N/A'}]
                    </div>
                )}
              </>
            ) : (
              <div>Params: N/A</div>
            )}
          </small>
        </td>
        <td>
          <small>
            <div><strong>Result:</strong> {job.result_message || 'N/A'}</div>
            
            {/* Separate Links based on Job Type */} 
            
            {/* Link for Successful/Partial Line Regen Jobs */}  
            {isLineRegen && (job.status === 'SUCCESS' || job.status === 'COMPLETED_WITH_ERRORS') && targetBatchId && (
                 <div>
                     <Link 
                        key={`${targetBatchId}-link`}
                        to={`/batch/${targetBatchId}`} 
                        style={{marginRight: '5px', fontWeight: 'bold'}}
                     >
                         [View/Rank Batch]
                     </Link>
                     (Line: {targetLineKey || 'N/A'})
                 </div>
            )} 
            
            {/* Links for Successful/Partial Full Batch Jobs */} 
            {!isLineRegen && (job.status === 'SUCCESS' || job.status === 'COMPLETED_WITH_ERRORS') && batchIds && batchIds.length > 0 && (
                <div>
                    <strong>Batches Generated:</strong>
                    <ul style={{ margin: '2px 0 0 0', paddingLeft: '15px' }}>
                        {batchIds.map((batchId: string) => (
                            <li key={batchId}>
                                {batchId} 
                                <Link key={`${batchId}-rank`} to={`/batch/${batchId}`} style={{ marginLeft: '5px' }}>[Rank]</Link>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
            
            {/* Error Display (applies to both job types) */} 
            {(job.status === 'FAILURE' || job.status === 'SUBMIT_FAILED') && job.result_message && (
                <div style={{ color: 'red', marginTop: '5px' }}>
                    <strong>Error Details:</strong> {job.result_message}
                </div>
            )}
          </small>
        </td>
      </>
    );
  };

  if (loading) { // Use initial loading state
    return <p>Loading job history...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <h2>Generation Jobs</h2>
      <Button onClick={fetchJobs} loading={loading} variant="outline" size="xs" style={{ marginBottom: '10px' }}>
          Refresh List
      </Button>
      {jobs.length === 0 && !loading ? (
        <p>No generation jobs found.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left', width: '20%' }}>Submitted</th>
              <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left', width: '15%' }}>Status</th>
              <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left', width: '32.5%' }}>Parameters</th> 
              <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left', width: '32.5%' }}>Result / Batches</th> 
            </tr>
          </thead>
          <tbody>
            {jobs.map(job => (
              <tr key={job.id} style={{ backgroundColor: getStatusColor(liveStatuses[job.celery_task_id || '']?.status || job.status) }}>
                <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top' }}>{job.submitted_at ? new Date(job.submitted_at).toLocaleString() : 'N/A'}</td>
                <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top' }}>{renderJobStatus(job)}</td>
                {renderJobDetails(job)}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default JobsPage; 