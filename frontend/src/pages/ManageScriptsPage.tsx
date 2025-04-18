import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { ScriptMetadata } from '../types';
import { Table, Button, Loader, Alert, Group, ActionIcon, Text, Tooltip, Switch } from '@mantine/core';
import { IconPencil, IconTrash, IconAlertCircle, IconArchive, IconArchiveOff } from '@tabler/icons-react';
// import { formatDistanceToNow } from 'date-fns/formatDistanceToNow'; // Comment out problematic import

const ManageScriptsPage: React.FC = () => {
  const navigate = useNavigate();
  const [scripts, setScripts] = useState<ScriptMetadata[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState<boolean>(false);

  const fetchScripts = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log(`[ManageScriptsPage] fetchScripts: Value of showArchived STATE = ${showArchived} (Type: ${typeof showArchived})`);
      console.log(`[ManageScriptsPage] fetchScripts: Checking api object before call...`, api);
      console.log(`[ManageScriptsPage] fetchScripts: CALLING api.listScripts with showArchived =`, showArchived, `(Type: ${typeof showArchived})`);
      const data = await api.listScripts(showArchived);
      setScripts(data);
    } catch (err: any) {
      console.error("Error fetching scripts:", err);
      setError(`Failed to load scripts: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    console.log(`[ManageScriptsPage useEffect] PRE-CALL Value of showArchived =`, showArchived, `(Type: ${typeof showArchived})`);
    fetchScripts();
  }, [showArchived]);

  const handleDelete = async (scriptId: number, scriptName: string) => {
    if (window.confirm(`Are you sure you want to delete the script "${scriptName}"? This action cannot be undone.`)) {
      setError(null);
      try {
        await api.deleteScript(scriptId);
        setScripts(currentScripts => currentScripts.filter(s => s.id !== scriptId));
        alert(`Script "${scriptName}" deleted successfully.`);
      } catch (err: any) {
        console.error(`Error deleting script ${scriptId}:`, err);
        setError(`Failed to delete script "${scriptName}": ${err.message}`);
      }
    }
  };

  const handleToggleArchive = async (scriptId: number, scriptName: string, archive: boolean) => {
      const action = archive ? 'archive' : 'unarchive';
      if (window.confirm(`Are you sure you want to ${action} the script "${scriptName}"?`)) {
        setError(null);
        try {
          await api.toggleScriptArchive(scriptId, archive);
          fetchScripts(); 
          alert(`Script "${scriptName}" ${action}d successfully.`);
        } catch (err: any) {
          console.error(`Error ${action}ing script ${scriptId}:`, err);
          setError(`Failed to ${action} script "${scriptName}": ${err.message}`);
        }
      }
  };

  if (loading) {
    return <Loader />;
  }

  const rows = scripts.map((script) => (
    <Table.Tr key={script.id}>
      <Table.Td>
        <Link to={`/scripts/${script.id}`}>{script.name}</Link>
        {script.is_archived && <Text size="xs" c="dimmed" ml={5}>(Archived)</Text>} 
      </Table.Td>
      <Table.Td>{script.description || '-'}</Table.Td>
      <Table.Td>{script.line_count}</Table.Td>
      {/* <Table.Td>{formatDistanceToNow(new Date(script.updated_at), { addSuffix: true })}</Table.Td> */}
      <Table.Td>{new Date(script.updated_at).toLocaleDateString()}</Table.Td> {/* Replace with simple formatting */}
      <Table.Td>
        <Group gap="xs" wrap="nowrap">
          <Tooltip label="Edit Script">
            <ActionIcon variant="subtle" onClick={() => navigate(`/scripts/${script.id}`)}>
              <IconPencil size={16} />
            </ActionIcon>
          </Tooltip>
          {script.is_archived ? (
            <Tooltip label="Unarchive Script">
                <ActionIcon 
                    variant="subtle" 
                    color="yellow"
                    onClick={() => handleToggleArchive(script.id, script.name, false)}
                >
                    <IconArchiveOff size={16} />
                </ActionIcon>
            </Tooltip>
          ) : (
             <Tooltip label="Archive Script">
                <ActionIcon 
                    variant="subtle" 
                    color="gray"
                    onClick={() => handleToggleArchive(script.id, script.name, true)}
                >
                    <IconArchive size={16} />
                </ActionIcon>
            </Tooltip>
          )}
          <Tooltip label="Delete Script">
            <ActionIcon variant="subtle" color="red" onClick={() => handleDelete(script.id, script.name)}>
              <IconTrash size={16} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Table.Td>
    </Table.Tr>
  ));

  return (
    <div>
      <h2>Manage Scripts</h2>
      {error && (
        <Alert icon={<IconAlertCircle size="1rem" />} title="Error" color="red" withCloseButton onClose={() => setError(null)} mb="md">
          {error}
        </Alert>
      )}
      <Group justify="space-between" mb="md">
        <Button onClick={() => navigate('/scripts/new')}>Create New Script</Button>
        <Switch 
            checked={showArchived}
            onChange={(event) => setShowArchived(event.currentTarget.checked)}
            label="Show Archived Scripts"
        />
      </Group>
      <Table withTableBorder withColumnBorders highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Name</Table.Th>
            <Table.Th>Description</Table.Th>
            <Table.Th>Lines</Table.Th>
            <Table.Th>Last Updated</Table.Th>
            <Table.Th>Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>{rows.length > 0 ? rows : <Table.Tr><Table.Td colSpan={5}>No scripts found.</Table.Td></Table.Tr>}</Table.Tbody>
      </Table>
    </div>
  );
};

export default ManageScriptsPage; 