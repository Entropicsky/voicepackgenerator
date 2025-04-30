import React, { useState, useEffect } from 'react';
import { 
    Title, 
    Container, 
    Paper, 
    Table, 
    Loader, 
    Alert, 
    Button, 
    Modal, 
    TextInput, 
    Textarea,
    Stack,
    Group,
    ActionIcon,
    Anchor
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { IconAlertCircle, IconPlus, IconPencil, IconTrash } from '@tabler/icons-react';
import { api } from '../api'; // Import the api functions
import { VoScriptTemplateMetadata } from '../types'; // Import the type
import { notifications } from '@mantine/notifications'; // Import notifications
import TemplateDetailView from '../components/templates/TemplateDetailView'; // <-- Import Detail View

function TemplateManagerPage() {
  const queryClient = useQueryClient();
  const [openedCreateModal, { open: openCreateModal, close: closeCreateModal }] = useDisclosure(false);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateDesc, setNewTemplateDesc] = useState('');
  const [newTemplateHint, setNewTemplateHint] = useState('');

  // State for selected template ID
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);

  // Fetch templates using react-query
  const { data: templates, isLoading, error, isError } = useQuery<VoScriptTemplateMetadata[], Error>({
    queryKey: ['voScriptTemplates'],
    queryFn: api.fetchVoScriptTemplates,
  });

  // Mutation for creating templates
  const createMutation = useMutation({
    mutationFn: api.createVoScriptTemplate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['voScriptTemplates'] }); // Refetch list after creation
      closeCreateModal(); // Close modal on success
      // Reset form
      setNewTemplateName('');
      setNewTemplateDesc('');
      setNewTemplateHint('');
      notifications.show({ 
        title: 'Success', 
        message: 'Template created successfully!', 
        color: 'green' 
      });
    },
    onError: (error) => {
      notifications.show({ 
        title: 'Error', 
        message: `Failed to create template: ${error.message}`,
        color: 'red' 
      });
      console.error("Error creating template:", error);
    }
  });

  // Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: api.deleteVoScriptTemplate,
    onSuccess: (data, variables) => {
      // variables holds the templateId passed to mutate
      queryClient.invalidateQueries({ queryKey: ['voScriptTemplates'] }); 
      notifications.show({ 
        title: 'Success', 
        message: data.message || `Template ID ${variables} deleted.`, // Use backend message
        color: 'green' 
      });
    },
    onError: (error, variables) => {
       notifications.show({ 
        title: 'Error', 
        message: `Failed to delete template ID ${variables}: ${error.message}`,
        color: 'red' 
      });
      console.error(`Error deleting template ${variables}:`, error);
    }
  });

  const handleDeleteClick = (templateId: number, templateName: string) => {
    if (window.confirm(`Are you sure you want to delete the template "${templateName}" (ID: ${templateId})? This cannot be undone.`)) {
      deleteMutation.mutate(templateId);
    }
  };

  const handleCreateSubmit = () => {
    if (!newTemplateName.trim()) {
        // Basic validation
        // TODO: Show validation error notification
        return;
    }
    createMutation.mutate({ 
        name: newTemplateName, 
        description: newTemplateDesc, 
        prompt_hint: newTemplateHint 
    });
  };

  const rows = templates?.map((template) => (
    <Table.Tr 
        key={template.id} 
        onClick={() => setSelectedTemplateId(template.id)} 
        style={{ cursor: 'pointer' }}
    >
      <Table.Td>{template.id}</Table.Td>
      <Table.Td>
          <Anchor component="button" type="button" onClick={(e) => { e.stopPropagation(); setSelectedTemplateId(template.id); }}>
              {template.name}
          </Anchor>
      </Table.Td>
      <Table.Td>{template.description || '-'}</Table.Td>
      <Table.Td>
          <Group gap="xs">
              <ActionIcon variant="subtle" color="blue" onClick={(e) => { e.stopPropagation(); setSelectedTemplateId(template.id); }}> 
                <IconPencil size={16} /> 
              </ActionIcon>
              <ActionIcon 
                variant="subtle" 
                color="red" 
                onClick={(e) => { e.stopPropagation(); handleDeleteClick(template.id, template.name); }} 
                loading={deleteMutation.isPending && deleteMutation.variables === template.id}
              > 
                <IconTrash size={16} /> 
              </ActionIcon>
          </Group>
      </Table.Td>
    </Table.Tr>
  ));

  // Conditional Rendering Logic
  if (selectedTemplateId) {
      return (
          <TemplateDetailView 
              templateId={selectedTemplateId} 
              onBackToList={() => setSelectedTemplateId(null)} 
          />
      );
  }

  return (
    <Container size="xl">
      <Paper shadow="xs" p="md" withBorder>
        <Group justify="space-between" mb="lg">
             <Title order={2}>
              VO Script Templates
            </Title>
            <Button leftSection={<IconPlus size={14} />} onClick={openCreateModal}>
                Create New Template
            </Button>
        </Group>

        {isLoading && <Loader />} 
        
        {isError && error && (
          <Alert icon={<IconAlertCircle size="1rem" />} title="Error Loading Templates" color="red">
            {error.message}
          </Alert>
        )}

        {!isLoading && !isError && templates && (
           <Table striped highlightOnHover withTableBorder withColumnBorders>
             <Table.Thead>
               <Table.Tr>
                 <Table.Th>ID</Table.Th>
                 <Table.Th>Name</Table.Th>
                 <Table.Th>Description</Table.Th>
                 <Table.Th>Actions</Table.Th>
               </Table.Tr>
             </Table.Thead>
             <Table.Tbody>
                {rows && rows.length > 0 ? rows : <Table.Tr><Table.Td colSpan={4}>No templates found.</Table.Td></Table.Tr>}
            </Table.Tbody>
           </Table>
        )}
      </Paper>
      
      {/* Create Template Modal - MOVED OUTSIDE Paper/Container */}
       <Modal 
         opened={openedCreateModal} 
         onClose={closeCreateModal} 
         title="Create New VO Script Template" 
         size="lg" 
         centered 
         withinPortal={true}
         styles={{
           inner: {
             left: 'calc(50% + 100px)',
             transform: 'translateX(-50%)',
           },
         }}
       >
            <Stack> 
                <TextInput
                    label="Template Name"
                    placeholder="e.g., SMITE 2 Skin"
                    required
                    value={newTemplateName}
                    onChange={(event) => setNewTemplateName(event.currentTarget.value)}
                    error={!newTemplateName.trim() && createMutation.isIdle === false ? "Name is required" : null} // Show error only after attempt
                />
                <Textarea
                    label="Description (Optional)"
                    placeholder="Purpose of this template..."
                    value={newTemplateDesc}
                    onChange={(event) => setNewTemplateDesc(event.currentTarget.value)}
                />
                <Textarea
                    label="General Prompt Hint (Optional)"
                    placeholder="General rules or guidance for lines using this template..."
                    autosize
                    minRows={3}
                    value={newTemplateHint}
                    onChange={(event) => setNewTemplateHint(event.currentTarget.value)}
                />
                <Group justify="flex-end" mt="auto">
                    <Button variant="default" onClick={closeCreateModal}>Cancel</Button>
                    <Button onClick={handleCreateSubmit} loading={createMutation.isPending}>Create Template</Button>
                </Group>
            </Stack>
        </Modal>

    </Container>
  );
}

export default TemplateManagerPage; 