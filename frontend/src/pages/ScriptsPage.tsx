import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { ScriptMetadata } from '../types';
import { Button, Table, Loader, Alert, Group } from '@mantine/core';
import { IconAlertCircle, IconTrash, IconEdit, IconPlus } from '@tabler/icons-react';

const ScriptsPage: React.FC = () => {
  const [scripts, setScripts] = useState<ScriptMetadata[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchScripts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // FIX: Pass boolean (false = don't include archived)
      const fetchedScripts = await api.listScripts(false);
      setScripts(fetchedScripts);
    } catch (err: any) {
      console.error("Failed to load scripts:", err);
      setError(`Failed to load scripts: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchScripts();
  }, [fetchScripts]);

  const handleDelete = async (scriptId: number, scriptName: string) => {
    if (window.confirm(`Are you sure you want to delete the script "${scriptName}"? This cannot be undone.`)) {
      setError(null);
      try {
        await api.deleteScript(scriptId);
        // Refresh the list after deletion
        fetchScripts(); 
        // Optionally show a success notification here
      } catch (err: any) {
        console.error("Failed to delete script:", err);
        setError(`Failed to delete script "${scriptName}": ${err.message}`);
      }
    }
  };

  const handleCreateNew = () => {
      navigate('/scripts/new');
  };

  if (loading) {
    return <Loader />; 
  }

  return (
    <div>
      <Group justify="space-between" mb="md">
        <h2>Manage Scripts</h2>
        <Button leftSection={<IconPlus size={14} />} onClick={handleCreateNew}>
            Create New Script
        </Button>
      </Group>

      {error && (
        <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red" withCloseButton onClose={() => setError(null)} mb="md">
          {error}
        </Alert>
      )}

      {scripts.length === 0 && !loading ? (
        <p>No scripts found. Create one to get started!</p>
      ) : (
        <Table striped highlightOnHover withTableBorder withColumnBorders>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Lines</Table.Th>
              <Table.Th>Last Updated</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {scripts.map((script) => (
              <Table.Tr key={script.id}>
                <Table.Td>
                    <Link to={`/scripts/${script.id}`}>{script.name}</Link>
                </Table.Td>
                <Table.Td>{script.description || '-'}</Table.Td>
                <Table.Td>{script.line_count}</Table.Td>
                <Table.Td>{new Date(script.updated_at).toLocaleString()}</Table.Td>
                <Table.Td>
                  <Group gap="xs" wrap="nowrap">
                    <Button 
                      component={Link} 
                      to={`/scripts/${script.id}`} 
                      variant="outline" 
                      size="xs" 
                      leftSection={<IconEdit size={14} />}
                    >
                        Edit
                    </Button>
                    <Button 
                      variant="outline" 
                      color="red" 
                      size="xs" 
                      onClick={() => handleDelete(script.id, script.name)}
                      leftSection={<IconTrash size={14} />}
                    >
                      Delete
                    </Button>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </div>
  );
};

export default ScriptsPage; 