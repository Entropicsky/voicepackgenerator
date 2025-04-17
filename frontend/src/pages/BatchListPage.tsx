import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { BatchInfo } from '../types';

const BatchListPage: React.FC = () => {
  const [batches, setBatches] = useState<BatchInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchBatches = async () => {
      setLoading(true);
      setError(null);
      try {
        const fetchedBatches = await api.listBatches();
        // Sort batches perhaps? Maybe by date derived from batch_id?
        // For now, just use the fetched order.
        setBatches(fetchedBatches);
      } catch (err: any) {
        setError(`Failed to load batches: ${err.message}`);
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchBatches();
  }, []);

  if (loading) {
    return <p>Loading batches...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <h2>Available Batches for Ranking</h2>
      {batches.length === 0 ? (
        <p>No batches found in the output directory.</p>
      ) : (
        <ul>
          {batches.map(batch => (
            <li key={batch.batch_id}> {/* Use batch_id as key */}
              <Link to={`/batch/${batch.batch_id}`}>
                {batch.skin} / {batch.voice} / {batch.batch_id}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default BatchListPage; 