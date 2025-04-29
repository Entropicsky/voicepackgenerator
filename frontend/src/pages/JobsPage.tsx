import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { GenerationJob /*, TaskStatus */ } from '../types'; // Remove TaskStatus import
import { Button } from '@mantine/core';

const JOB_LIST_REFRESH_INTERVAL = 15000; // Refresh full list every 15s
// REMOVE LIVE_STATUS_REFRESH_INTERVAL
// const LIVE_STATUS_REFRESH_INTERVAL = 5000;

const JobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<GenerationJob[]>([]);
  // REMOVE liveStatuses state
  // const [liveStatuses, setLiveStatuses] = useState<Record<string, TaskStatus>>({}); 
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // REMOVE activeJobTaskIds ref
  // const activeJobTaskIds = useRef<Set<string>>(new Set()); 

  const fetchJobs = useCallback(async () => {
    // setError(null); // Reset error on fetch
    try {
      console.log("Fetching job list from DB...");
      const fetchedJobs = await api.getJobs();
      setJobs(fetchedJobs);
      // REMOVE logic related to activeJobTaskIds and fetchLiveStatuses
    } catch (err: any) {
      setError(`Failed to load jobs: ${err.message}`);
      console.error(err);
    } finally {
      if (loading) setLoading(false); // Only set loading false after initial fetch
    }
  // }, [loading]); // Original deps
  }, [loading]); // Update deps
  
  // REMOVE fetchLiveStatuses function
  /*
  const fetchLiveStatuses = useCallback(async () => { ... }, []);
  */

  // Fetch jobs list periodically
  useEffect(() => {
    fetchJobs(); // Initial fetch
    const jobListIntervalId = setInterval(fetchJobs, JOB_LIST_REFRESH_INTERVAL);
    return () => clearInterval(jobListIntervalId);
  // }, [fetchJobs]); // Original deps
  }, [fetchJobs]); // Update deps

  // REMOVE useEffect for polling live statuses
  /*
  useEffect(() => { ... }, [fetchLiveStatuses, activeJobTaskIds.current.size]); 
  */

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

  // UPDATED: Render status based only on DB Job status
  const renderJobStatus = (job: GenerationJob): React.ReactNode => {
      // Fallback to DB status
      return <span style={{fontWeight: 'bold'}}>{job.status}</span>;
  }

  // UPDATED: Render details based only on DB Job status/data
  const renderJobDetails = (job: GenerationJob) => {
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
        {/* Apply status color directly to TD based on job.status */}
        <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top', backgroundColor: getStatusColor(job.status) }}>
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
        {/* Apply status color directly to TD based on job.status */}
        <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top', backgroundColor: getStatusColor(job.status) }}>
          <small>
            <div><strong>Result:</strong> {job.result_message || 'N/A'}</div>
            
            {/* Separate Links based on Job Type */} 
            
            {/* Link for Successful/Partial Line Regen Jobs */}  
            {isLineRegen && (job.status === 'SUCCESS' || job.status === 'COMPLETED_WITH_ERRORS') && targetBatchId && (
                 <div>
                     <Link 
                        key={`${targetBatchId}-link`}
                        to={`/batch/${targetBatchId}`} 
                        // Add !important to color
                        style={{marginRight: '5px', fontWeight: 'bold', color: '#007bff !important', textDecoration: 'underline'}}
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
                                <Link 
                                  key={`${batchId}-rank`} 
                                  to={`/batch/${batchId}`} 
                                  // Add !important to color
                                  style={{ marginLeft: '5px', color: '#007bff !important', textDecoration: 'underline' }}>
                                  [Rank]
                                </Link>
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
      <h2>Monitor Generations</h2>
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
              <tr key={job.id}>
                {/* Apply status color directly to TD based on job.status */}
                <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top', backgroundColor: getStatusColor(job.status) }}>
                  {job.submitted_at ? new Date(job.submitted_at).toLocaleString() : 'N/A'}
                </td>
                {/* Apply status color directly to TD based on job.status */}
                <td style={{ border: '1px solid #ddd', padding: '8px', verticalAlign: 'top', backgroundColor: getStatusColor(job.status) }}>
                  {renderJobStatus(job)}
                </td>
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