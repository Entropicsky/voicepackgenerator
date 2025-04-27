import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Table, Title, Text, Group, ActionIcon, Stack, LoadingOverlay, Alert } from '@mantine/core';
import { IconTrash, IconPencil, IconPlayerPlay } from '@tabler/icons-react'; // Example icons
import { notifications } from '@mantine/notifications'; // Import notifications
// Import API functions
import { api } from '../api'; // Import the api object
import { VoScriptListItem, DeleteResponse } from '../types'; // Import types

// TODO: Define the expected shape of a VO Script list item
// interface VoScriptListItem { ... }

const VoScriptListView: React.FC = () => {
  const queryClient = useQueryClient();

  // 1. Fetch VO Scripts using React Query
  const { data: voScripts, isLoading, error, isError } = useQuery<VoScriptListItem[], Error>({
    queryKey: ['voScripts'],
    queryFn: api.listVoScripts, // Use the actual API function
  });

  // 2. Setup Mutation for Deleting a Script
  const deleteMutation = useMutation<DeleteResponse, Error, number>({ // Use DeleteResponse type
    mutationFn: api.deleteVoScript, // Use the actual API function
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['voScripts'] });
      notifications.show({ // Add success notification
          title: 'Script Deleted',
          message: data.message || 'VO Script deleted successfully.',
          color: 'green',
      });
    },
    onError: (err) => {
      notifications.show({ // Add error notification
          title: 'Error Deleting Script',
          message: err.message || 'Could not delete the script.',
          color: 'red',
      });
      console.error("Error deleting script:", err.message);
    },
  });

  // Handle delete confirmation
  const handleDelete = (scriptId: number, scriptName: string) => {
    if (window.confirm(`Are you sure you want to delete the VO Script "${scriptName}"? This cannot be undone.`)) {
      deleteMutation.mutate(scriptId);
    }
  };

  // 3. Render the View
  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>VO Scripts</Title>
        <Button component={Link} to="/vo-scripts/new">
          Create New VO Script
        </Button>
      </Group>

      <Text>Manage your Voice Over Scripts generated from templates.</Text>

      {/* Loading and Error States */}
      <LoadingOverlay visible={isLoading || deleteMutation.isPending} overlayProps={{ radius: "sm", blur: 2 }} />
      
      {isError && (
        <Alert title="Error Loading Scripts" color="red" withCloseButton>
          {error?.message || 'Could not fetch VO scripts from the server.'}
        </Alert>
      )}

      {/* 4. Display Scripts in a Table */}
      {voScripts && (
        <Table striped highlightOnHover withTableBorder withColumnBorders>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Template</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Last Updated</Table.Th>
              <Table.Th>Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {voScripts.length === 0 && (
                <Table.Tr>
                    <Table.Td colSpan={5}><Text ta="center">No VO Scripts found.</Text></Table.Td>
                </Table.Tr>
            )}
            {voScripts.map((script) => (
              <Table.Tr key={script.id}>
                <Table.Td>
                    <Link to={`/vo-scripts/${script.id}`}>{script.name}</Link>
                </Table.Td>
                <Table.Td>{script.template_name || `ID: ${script.template_id}`}</Table.Td>
                <Table.Td>{script.status}</Table.Td>
                <Table.Td>{new Date(script.updated_at).toLocaleString()}</Table.Td>
                <Table.Td>
                  {/* 5. Action Buttons (View/Edit, Delete) */}
                  <Group gap="xs">
                    {/* Link to Detail/Edit View */}
                    <ActionIcon component={Link} to={`/vo-scripts/${script.id}`} variant="subtle" color="blue" title="View/Edit Script">
                       <IconPencil size={16} />
                    </ActionIcon>
                    {/* Delete Button */}
                    <ActionIcon 
                        variant="subtle" 
                        color="red" 
                        title="Delete Script" 
                        onClick={() => handleDelete(script.id, script.name)}
                        loading={deleteMutation.isPending && deleteMutation.variables === script.id} // Show loading on the specific icon clicked
                    >
                      <IconTrash size={16} />
                    </ActionIcon>
                     {/* Optional: Quick Run Agent Button? */}
                     {/* 
                     <ActionIcon variant="subtle" color="green" title="Run Generation Agent">
                       <IconPlayerPlay size={16} />
                     </ActionIcon> 
                     */}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
};

export default VoScriptListView; 