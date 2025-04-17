import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { BatchDetailInfo } from '../types';

type SortableBatchColumn = 'batch_id' | 'skin' | 'voice' | 'num_lines' | 'takes_per_line' | 'created_at_sortkey' | 'status';
type SortDirection = 'asc' | 'desc';

const BatchesPage: React.FC = () => {
  const [batches, setBatches] = useState<BatchDetailInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<SortableBatchColumn>('created_at_sortkey');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  useEffect(() => {
    const fetchBatches = async () => {
      setLoading(true);
      setError(null);
      try {
        const fetchedBatches = await api.listBatches();
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

  const sortedBatches = useMemo(() => {
    return [...batches].sort((a, b) => {
      const valA = a[sortColumn];
      const valB = b[sortColumn];
      const direction = sortDirection === 'asc' ? 1 : -1;

      if (typeof valA === 'string' && typeof valB === 'string') {
        return valA.localeCompare(valB) * direction;
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return (valA - valB) * direction;
      }
      // Fallback for null/undefined or different types
      if (valA === null || valA === undefined) return 1 * direction;
      if (valB === null || valB === undefined) return -1 * direction;
      return 0;
    });
  }, [batches, sortColumn, sortDirection]);

  const handleSort = (column: SortableBatchColumn) => {
    if (sortColumn === column) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc'); // Default to ascending on new column
    }
  };

  const renderSortArrow = (column: SortableBatchColumn) => {
      if (sortColumn !== column) return null;
      return sortDirection === 'asc' ? ' ▲' : ' ▼';
  };

  const thStyle: React.CSSProperties = {
      border: '1px solid #ddd', 
      padding: '8px', 
      textAlign: 'left', 
      cursor: 'pointer', 
      whiteSpace: 'nowrap'
  };
  const tdStyle: React.CSSProperties = {
      border: '1px solid #ddd', 
      padding: '8px', 
      verticalAlign: 'top'
  };
  const actionCellStyle: React.CSSProperties = {
      ...tdStyle, // Inherit base style
      textAlign: 'center'
  };
  const downloadLinkStyle: React.CSSProperties = {
      display: 'inline-block',
      padding: '4px 8px',
      border: '1px solid #0d6efd',
      borderRadius: '4px',
      textDecoration: 'none',
      color: '#0d6efd',
      fontSize: '0.9em'
  }

  if (loading) {
    return <p>Loading batches...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div>
      <h2>Available Batches</h2>
      {batches.length === 0 ? (
        <p>No batches found in the output directory.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
                <tr>
                    <th style={thStyle} onClick={() => handleSort('batch_id')}>Batch ID{renderSortArrow('batch_id')}</th>
                    <th style={thStyle} onClick={() => handleSort('skin')}>Skin{renderSortArrow('skin')}</th>
                    <th style={thStyle} onClick={() => handleSort('voice')}>Voice{renderSortArrow('voice')}</th>
                    <th style={thStyle} onClick={() => handleSort('num_lines')}>Lines{renderSortArrow('num_lines')}</th>
                    <th style={thStyle} onClick={() => handleSort('takes_per_line')}>Takes/Line{renderSortArrow('takes_per_line')}</th>
                    <th style={thStyle} onClick={() => handleSort('created_at_sortkey')}>Created{renderSortArrow('created_at_sortkey')}</th>
                    <th style={thStyle} onClick={() => handleSort('status')}>Status{renderSortArrow('status')}</th>
                    <th style={{...thStyle, cursor: 'default'}}>Actions</th>
                </tr>
            </thead>
            <tbody>
                {sortedBatches.map(batch => (
                    <tr key={batch.batch_id}>
                         <td style={tdStyle}><Link to={`/batch/${batch.batch_id}`}>{batch.batch_id}</Link></td>
                         <td style={tdStyle}>{batch.skin}</td>
                         <td style={tdStyle}>{batch.voice}</td>
                         <td style={tdStyle}>{batch.num_lines}</td>
                         <td style={tdStyle}>{batch.takes_per_line}</td>
                         <td style={tdStyle}>{batch.created_at ? new Date(batch.created_at).toLocaleString() : 'N/A'}</td>
                         <td style={tdStyle}>{batch.status}</td>
                         <td style={actionCellStyle}>
                            <a 
                                href={`/api/batch/${batch.batch_id}/download`} 
                                download={`${batch.voice}.zip`}
                                style={downloadLinkStyle}
                                title={`Download ZIP for ${batch.batch_id} (${batch.voice})`}
                            >
                                Download ZIP
                            </a>
                         </td>
                    </tr>
                ))}
            </tbody>
        </table>
      )}
    </div>
  );
};

export default BatchesPage; 