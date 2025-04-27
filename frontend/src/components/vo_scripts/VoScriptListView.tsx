import React from 'react';
import { Link } from 'react-router-dom';
import { Container, Title, Loader, Alert, Button, Table, Group } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../api'; // Adjust path as needed
import { VoScript } from '../../types'; // Adjust path as needed
import { IconAlertCircle, IconPlus, IconPencil, IconTrash } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

const VoScriptListView: React.FC = () => {
  // TODO: Implement useQuery to fetch VO Scripts
  const isLoading = false; // Placeholder
  const isError = false; // Placeholder
  const error: Error | null = null; // Placeholder
  const data: VoScript[] | undefined = []; // Placeholder

  // TODO: Implement Delete Mutation

  const handleDeleteClick = (scriptId: number, scriptName: string) => {
    if (window.confirm(`Are you sure you want to delete VO Script "${scriptName}"?`)) {
      // TODO: Call delete mutation
      console.log(`TODO: Delete script ${scriptId}`);
       notifications.show({ 
            title: 'TODO', 
            message: `Deletion for ${scriptName} not implemented yet.`, 
            color: 'yellow' 
       });
    }
  };

  if (isLoading) {
    return <Container><Loader /></Container>;
  }

  if (isError) {
    return (
      <Container>
        <Alert icon={<IconAlertCircle size="1rem" />} title="Error Loading VO Scripts" color="red">
          {error?.message || 'Could not load VO scripts.'}
        </Alert>
      </Container>
    );
  }

  const rows = data?.map((script) => (
    <Table.Tr key={script.id}>
      <Table.Td>{script.id}</Table.Td>
      <Table.Td>
         <Link to={`/vo-scripts/${script.id}`}>{script.name}</Link>
      </Table.Td>
      <Table.Td>{script.description || '-'}</Table.Td>
      {/* TODO: Display Template Name? Needs fetching template data or joining in backend */}
      <Table.Td>{script.template_id}</Table.Td> 
      <Table.Td>{script.status || 'Unknown'}</Table.Td>
      <Table.Td>{new Date(script.created_at).toLocaleString()}</Table.Td>
      <Table.Td>{new Date(script.updated_at).toLocaleString()}</Table.Td>
      <Table.Td>
        <Group gap="xs">
          <Button 
             component={Link} 
             to={`/vo-scripts/${script.id}`} 
             variant="subtle" 
             size="xs" 
             leftSection={<IconPencil size={14}/>}
           >
            View/Edit
          </Button>
          <Button 
             variant="subtle" 
             color="red" 
             size="xs" 
             leftSection={<IconTrash size={14}/>}
             onClick={() => handleDeleteClick(script.id, script.name)}
             // loading={deleteMutation.isPending && deleteMutation.variables === script.id} // TODO
           >
            Delete
          </Button>
        </Group>
      </Table.Td>
    </Table.Tr>
  ));

  return (
    <Container size="xl">
      <Group justify="space-between" mb="lg">
        <Title order={2}>VO Scripts</Title>
        <Button component={Link} to="/vo-scripts/new" leftSection={<IconPlus size={14} />}>
          Create New VO Script
        </Button>
      </Group>

      <Table striped highlightOnHover withTableBorder withColumnBorders>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>ID</Table.Th>
            <Table.Th>Name</Table.Th>
            <Table.Th>Description</Table.Th>
            <Table.Th>Template ID</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Created</Table.Th>
            <Table.Th>Updated</Table.Th>
            <Table.Th>Actions</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows && rows.length > 0 ? rows : <Table.Tr><Table.Td colSpan={8}>No VO scripts found.</Table.Td></Table.Tr>}
        </Table.Tbody>
      </Table>
    </Container>
  );
};

export default VoScriptListView; 