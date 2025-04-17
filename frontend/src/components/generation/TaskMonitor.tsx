import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../api';
import { TaskStatus } from '../../types';
import usePolling from '../../hooks/usePolling';
import { Link } from 'react-router-dom';

interface TaskMonitorProps {
  submittedTaskIds: string[]; // IDs passed from the parent page
}

const POLLING_INTERVAL = 5000; // Poll every 5 seconds

const TaskMonitor: React.FC<TaskMonitorProps> = ({ submittedTaskIds }) => {
  const [taskStatuses, setTaskStatuses] = useState<Record<string, TaskStatus>>({});
  const [activePolling, setActivePolling] = useState<boolean>(false);

  // Function to fetch status for all submitted tasks
  const pollStatuses = useCallback(async () => {
    if (submittedTaskIds.length === 0) {
      setActivePolling(false);
      return;
    }

    console.log("Polling task statuses...");
    let hasPendingTasks = false;
    const newStatuses: Record<string, TaskStatus> = { ...taskStatuses }; // Start with current

    for (const taskId of submittedTaskIds) {
      // Only poll if status is not already terminal (SUCCESS/FAILURE)
      if (!taskStatuses[taskId] || !['SUCCESS', 'FAILURE'].includes(taskStatuses[taskId].status)) {
        try {
          const status = await api.getTaskStatus(taskId);
          newStatuses[taskId] = status;
          if (!['SUCCESS', 'FAILURE'].includes(status.status)) {
            hasPendingTasks = true;
          }
        } catch (error: any) {
          console.error(`Failed to get status for task ${taskId}:`, error);
          // Store error status? Maybe add an 'ERROR' state
          newStatuses[taskId] = { ...(newStatuses[taskId] || {}), status: 'POLL_ERROR', info: { error: error.message } } as TaskStatus;
          // Optionally stop polling on error, or keep trying?
        }
      }
    }
    setTaskStatuses(newStatuses);
    setActivePolling(hasPendingTasks); // Keep polling if any task is still active

  }, [submittedTaskIds, taskStatuses]); // Dependencies for useCallback

  // Update activePolling based on submittedTaskIds
  useEffect(() => {
    const hasActiveTasks = submittedTaskIds.some(id =>
        !taskStatuses[id] || !['SUCCESS', 'FAILURE'].includes(taskStatuses[id].status)
    );
    setActivePolling(hasActiveTasks);
  }, [submittedTaskIds, taskStatuses]);

  // Setup polling using the hook
  usePolling(pollStatuses, activePolling ? POLLING_INTERVAL : null);

  const renderTaskInfo = (status: TaskStatus) => {
    if (!status.info) return '...';

    switch (status.status) {
      case 'STARTED':
      case 'PROGRESS':
        return typeof status.info === 'object' ? status.info.status || 'Processing...' : 'Processing...';
      case 'SUCCESS':
        return typeof status.info === 'object' ? status.info.message || 'Completed' : 'Completed';
      case 'FAILURE':
        return typeof status.info === 'object' ? `Error: ${status.info.error}` : 'Failed';
      case 'PENDING':
        return 'Waiting for worker...';
      case 'POLL_ERROR':
         return typeof status.info === 'object' ? `Polling Error: ${status.info.error}` : 'Polling Error';
      default:
        return 'Unknown status';
    }
  };

  const renderBatchLinks = (status: TaskStatus) => {
      if (status.status === 'SUCCESS' && status.info && Array.isArray(status.info.generated_batches)) {
          return (
              <ul>
                  {status.info.generated_batches.map((batch: any) => (
                      <li key={batch.batch_id}>
                          <Link to={`/batch/${batch.batch_id}`}>
                              Rank Batch: {batch.skin} / {batch.voice} ({batch.batch_id})
                          </Link>
                      </li>
                  ))}
              </ul>
          );
      }
      return null;
  }

  return (
    <div style={{ border: '1px solid #eee', padding: '15px', marginTop: '15px' }}>
      <h4>Generation Job Status:</h4>
      {submittedTaskIds.length === 0 ? (
        <p>No generation jobs submitted yet.</p>
      ) : (
        <ul>
          {submittedTaskIds.map(taskId => {
            const status = taskStatuses[taskId];
            return (
              <li key={taskId} style={{ marginBottom: '10px' }}>
                <strong>Task ID:</strong> {taskId}<br />
                <strong>Status:</strong> {status ? status.status : 'Loading...'}<br />
                <strong>Info:</strong> {status ? renderTaskInfo(status) : '...'}
                {status && renderBatchLinks(status)}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};

export default TaskMonitor; 