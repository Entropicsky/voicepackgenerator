import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api';
import { BatchListInfo } from '../types';
import { Table, Button, Anchor } from '@mantine/core';

type SortableBatchColumn = 'id' | 'skin_name' | 'voice_name' | 'generated_at_utc';
type SortDirection = 'asc' | 'desc';

const BatchesPage: React.FC = () => {
  const [batches, setBatches] = useState<BatchListInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [sortColumn, setSortColumn] = useState<SortableBatchColumn>('id');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  useEffect(() => {
    const fetchBatches = async () => {
      setLoading(true);
      setError(null);
      try {
        const fetchedBatches = await api.listBatches();
        const batchesWithSortKey = fetchedBatches.map(b => ({
           ...b,
           created_at_sortkey: new Date(b.id.split('-')[0]).getTime() || 0
        }));
        setBatches(batchesWithSortKey);
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
      let valA: any = a[sortColumn];
      let valB: any = b[sortColumn];
      
      if (sortColumn === 'generated_at_utc' && a.created_at_sortkey && b.created_at_sortkey) {
          valA = a.created_at_sortkey;
          valB = b.created_at_sortkey;
      } else if (sortColumn === 'id') {
          try {
             valA = new Date(a.id.split('-')[0]).getTime();
             valB = new Date(b.id.split('-')[0]).getTime();
          } catch { 
             valA = a.id;
             valB = b.id; 
          }
      }
      
      const direction = sortDirection === 'asc' ? 1 : -1;

      if (typeof valA === 'string' && typeof valB === 'string') {
        return valA.localeCompare(valB) * direction;
      }
      if (typeof valA === 'number' && typeof valB === 'number') {
        return (valA - valB) * direction;
      }
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
      setSortDirection('asc');
    }
  };

  const renderSortArrow = (column: SortableBatchColumn) => {
      if (sortColumn !== column) return null;
      return sortDirection === 'asc' ? ' ▲' : ' ▼';
  };

  const thStyle: React.CSSProperties = { cursor: 'pointer', whiteSpace: 'nowrap' };

  if (loading) {
    return <p>Loading batches...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>{error}</p>;
  }

  return (
    <div style={{ width: '100%', maxWidth: '100%' }}>
      <h2>Edit Recordings</h2>
      {batches.length === 0 ? (
        <p>No batches found.</p>
      ) : (
        <Table striped highlightOnHover withTableBorder withColumnBorders>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={thStyle} onClick={() => handleSort('id')}>Session ID{renderSortArrow('id')}</Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('skin_name')}>Skin{renderSortArrow('skin_name')}</Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('voice_name')}>Voice{renderSortArrow('voice_name')}</Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('generated_at_utc')}>Created{renderSortArrow('generated_at_utc')}</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedBatches.map(batch => (
              <Table.Tr key={batch.batch_prefix}>
                <Table.Td>
                  <Anchor 
                    component={Link} 
                    to={`/batch/${encodeURIComponent(batch.batch_prefix)}`} 
                    underline="hover"
                    c="blue.6"
                  >
                    {batch.id}
                  </Anchor>
                </Table.Td>
                <Table.Td>{batch.skin_name}</Table.Td>
                <Table.Td>{batch.voice_name}</Table.Td>
                <Table.Td>{batch.generated_at_utc ? new Date(batch.generated_at_utc).toLocaleString() : 'N/A'}</Table.Td>
                <Table.Td ta="center">
                  <Button 
                    component="a"
                    href={`/api/batch/${encodeURIComponent(batch.batch_prefix)}/download`}
                    download={`${batch.voice_name}.zip`}
                    variant="outline"
                    size="xs"
                    title={`Download ZIP for ${batch.batch_prefix}`}
                  >
                    Download ZIP
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </div>
  );
};

export default BatchesPage; 