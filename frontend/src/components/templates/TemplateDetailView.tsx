import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Paper, Title, Loader, Alert, Button, Tabs, Space, Table, Group, ActionIcon, Text, ScrollArea, TextInput, Textarea, Stack, Select, Switch } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api'; // Adjust path as needed
import { VoScriptTemplate, VoScriptTemplateCategory, VoScriptTemplateLine } from '../../types'; // Adjust path as needed
import { IconAlertCircle, IconArrowLeft, IconPencil, IconTrash, IconPlus, IconDeviceFloppy } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import AppModal from '../common/AppModal';

interface TemplateDetailViewProps {
  templateId: number;
  onBackToList: () => void;
}

const TemplateDetailView: React.FC<TemplateDetailViewProps> = ({ templateId, onBackToList }) => {
  const queryClient = useQueryClient();
  
  // State for form values
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [promptHint, setPromptHint] = useState('');

  // State for Create Category Modal
  const [catModalOpened, { open: openCatModal, close: closeCatModal }] = useDisclosure(false);
  const [newCatName, setNewCatName] = useState('');
  const [newCatInstructions, setNewCatInstructions] = useState('');

  // --- State for Edit Category Modal ---
  const [editCatModalOpened, { open: openEditCatModal, close: closeEditCatModal }] = useDisclosure(false);
  const [editingCategory, setEditingCategory] = useState<VoScriptTemplateCategory | null>(null);
  const [editCatName, setEditCatName] = useState('');
  const [editCatInstructions, setEditCatInstructions] = useState('');
  // --- END State for Edit Category Modal ---

  // --- State for Line Modals --- 
  const [lineModalOpened, { open: openLineModal, close: closeLineModal }] = useDisclosure(false);
  const [newLineKey, setNewLineKey] = useState('');
  const [newLineCategoryId, setNewLineCategoryId] = useState<string | null>(null); // Use string for Select value
  const [newLineOrderIndex, setNewLineOrderIndex] = useState<number>(0);
  const [newLinePromptHint, setNewLinePromptHint] = useState('');

  const [editLineModalOpened, { open: openEditLineModal, close: closeEditLineModal }] = useDisclosure(false);
  const [editingLine, setEditingLine] = useState<VoScriptTemplateLine | null>(null);
  const [editLineKey, setEditLineKey] = useState('');
  const [editLineCategoryId, setEditLineCategoryId] = useState<string | null>(null);
  const [editLineOrderIndex, setEditLineOrderIndex] = useState<number>(0);
  const [editLinePromptHint, setEditLinePromptHint] = useState('');

  // Add state for new static text fields
  const [newLineStaticTextEnabled, setNewLineStaticTextEnabled] = useState(false);
  const [newLineStaticText, setNewLineStaticText] = useState('');
  const [editLineStaticTextEnabled, setEditLineStaticTextEnabled] = useState(false);
  const [editLineStaticText, setEditLineStaticText] = useState('');

  const { data: template, isLoading, error, isError, refetch } = useQuery<VoScriptTemplate, Error>({
    queryKey: ['voScriptTemplateDetail', templateId],
    queryFn: () => api.getVoScriptTemplate(templateId),
    enabled: !!templateId, 
  });

  // --- NEW: useEffect to populate state from fetched data --- 
  useEffect(() => {
      if (template) {
          setName(template.name || '');
          setDescription(template.description || '');
          setPromptHint(template.prompt_hint || '');
      }
  }, [template]); // Dependency array ensures this runs when template data changes
  // --- END useEffect --- 

  // Update Mutation (moved here)
  const updateMutation = useMutation({
      mutationFn: (payload: { templateId: number; data: { name?: string; description?: string | null; prompt_hint?: string | null; } }) => 
          api.updateVoScriptTemplate(payload.templateId, payload.data),
      onSuccess: (data, variables) => {
          // Invalidate both list and detail queries
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplates'] }); 
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', variables.templateId] });
          notifications.show({ 
              title: 'Success', 
              message: `Template updated successfully!`, 
              color: 'green' 
            });
      },
      onError: (error, variables) => {
          notifications.show({ 
              title: 'Error', 
              message: `Failed to update template: ${error.message}`,
              color: 'red' 
            });
          console.error(`Error updating template ${variables.templateId}:`, error);
      }
  });

  // --- NEW: Create Category Mutation --- 
  const createCategoryMutation = useMutation({
      mutationFn: api.createVoScriptTemplateCategory,
      onSuccess: () => {
          refetch();
          closeCatModal();
          setNewCatName('');
          setNewCatInstructions('');
          notifications.show({ 
              title: 'Success', 
              message: 'Category created successfully!', 
              color: 'green' 
          });
      },
      onError: (error) => {
           notifications.show({ 
              title: 'Error', 
              message: `Failed to create category: ${error.message}`,
              color: 'red' 
            });
          console.error("Error creating category:", error);
      }
  });
  // --- END: Create Category Mutation --- 

  // --- Delete Category Mutation --- 
  const deleteCategoryMutation = useMutation({
    mutationFn: api.deleteVoScriptTemplateCategory,
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', templateId] });
      notifications.show({ title: 'Success', message: data.message || `Category ID ${variables} deleted.`, color: 'green' });
    },
    onError: (error, variables) => {
       notifications.show({ title: 'Error', message: `Failed to delete category ID ${variables}: ${error.message}`, color: 'red' });
      console.error(`Error deleting category ${variables}:`, error);
    }
  });
  // --- END Delete Category Mutation --- 

  // --- Update Category Mutation --- 
  const updateCategoryMutation = useMutation({
      mutationFn: (payload: { categoryId: number; data: { name?: string; prompt_instructions?: string | null; } }) => 
          api.updateVoScriptTemplateCategory(payload.categoryId, payload.data),
      onSuccess: (data, variables) => {
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', templateId] });
          closeEditCatModal();
          notifications.show({ title: 'Success', message: `Category ID ${variables.categoryId} updated.`, color: 'green' });
      },
      onError: (error, variables) => {
          notifications.show({ title: 'Error', message: `Failed to update category ID ${variables.categoryId}: ${error.message}`, color: 'red' });
          console.error(`Error updating category ${variables.categoryId}:`, error);
      }
  });
  // --- END Update Category Mutation --- 

  // --- NEW: Line Mutations ---
  const createLineMutation = useMutation({
      mutationFn: api.createVoScriptTemplateLine,
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', templateId] });
          closeLineModal();
          // Reset form
          setNewLineKey('');
          setNewLineCategoryId(null);
          setNewLineOrderIndex(0);
          setNewLinePromptHint('');
          notifications.show({ title: 'Success', message: 'Template line created!', color: 'green' });
      },
      onError: (error) => {
          notifications.show({ title: 'Error', message: `Failed to create line: ${error.message}`, color: 'red' });
          console.error("Error creating line:", error);
      }
  });

  const updateLineMutation = useMutation({
      mutationFn: (payload: { lineId: number; data: { category_id?: number; line_key?: string; order_index?: number; prompt_hint?: string | null; } }) => 
          api.updateVoScriptTemplateLine(payload.lineId, payload.data),
      onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', templateId] });
          closeEditLineModal();
          notifications.show({ title: 'Success', message: 'Template line updated!', color: 'green' });
      },
      onError: (error, variables) => {
          notifications.show({ title: 'Error', message: `Failed to update line: ${error.message}`, color: 'red' });
          console.error(`Error updating line ${variables.lineId}:`, error);
      }
  });

  const deleteLineMutation = useMutation({
      mutationFn: api.deleteVoScriptTemplateLine,
      onSuccess: (data, variables) => {
          queryClient.invalidateQueries({ queryKey: ['voScriptTemplateDetail', templateId] });
          notifications.show({ title: 'Success', message: data.message || `Line ID ${variables} deleted.`, color: 'green' });
      },
      onError: (error, variables) => {
          notifications.show({ title: 'Error', message: `Failed to delete line ID ${variables}: ${error.message}`, color: 'red' });
          console.error(`Error deleting line ${variables}:`, error);
      }
  });
  // --- END: Line Mutations ---

  const handleDetailsSave = () => {
      if (!template || !name.trim()) {
          notifications.show({
              title: 'Validation Error',
              message: 'Template Name cannot be empty.',
              color: 'orange'
          });
          return;
      }
      
      const payload: { name?: string; description?: string | null; prompt_hint?: string | null; } = {};
      let changed = false;
      if (name !== template.name) { payload.name = name; changed = true; }
      if (description !== (template.description || '')) { payload.description = description; changed = true; }
      if (promptHint !== (template.prompt_hint || '')) { payload.prompt_hint = promptHint; changed = true; }

      if (changed) {
          updateMutation.mutate({ templateId: template.id, data: payload });
      } else {
          notifications.show({
              title: 'No Changes',
              message: 'No changes detected in template details.',
          });
      }
  };

  // --- NEW: Category Create Handler ---
  const handleCreateCategorySubmit = () => {
      if (!newCatName.trim()) {
          notifications.show({ title: 'Validation Error', message: 'Category Name cannot be empty.', color: 'orange' });
          return;
      }
      createCategoryMutation.mutate({ 
          template_id: templateId, 
          name: newCatName, 
          prompt_instructions: newCatInstructions 
      });
  };
  // --- END: Category Create Handler ---

  // --- Edit/Delete Category Handlers ---
   const handleEditCategoryClick = (category: VoScriptTemplateCategory) => {
    setEditingCategory(category);
    setEditCatName(category.name);
    setEditCatInstructions(category.prompt_instructions || '');
    openEditCatModal();
  };

  const handleEditCategorySubmit = () => {
      if (!editingCategory || !editCatName.trim()) {
          notifications.show({ title: 'Validation Error', message: 'Category Name cannot be empty.', color: 'orange' });
          return;
      }
      const payload: { name?: string; prompt_instructions?: string | null; } = {};
      let changed = false;
      if (editCatName !== editingCategory.name) { payload.name = editCatName; changed = true; }
      if (editCatInstructions !== (editingCategory.prompt_instructions || '')) { payload.prompt_instructions = editCatInstructions; changed = true; }

      if (changed) {
          updateCategoryMutation.mutate({ categoryId: editingCategory.id, data: payload });
      } else {
          closeEditCatModal(); // No changes
      }
  };

  const handleDeleteCategoryClick = (categoryId: number, categoryName: string) => {
    if (window.confirm(`Are you sure you want to delete category "${categoryName}"? This will also delete associated template lines.`)) {
      deleteCategoryMutation.mutate(categoryId);
    }
  };
  // --- END Edit/Delete Category Handlers ---

  // --- NEW: Line Handlers --- 
  const handleCreateLineSubmit = () => {
    if (!newLineKey.trim() || !newLineCategoryId || newLineOrderIndex < 0) {
      notifications.show({ title: 'Validation Error', message: 'Line Key, Category, and Order Index are required.', color: 'orange' });
      return;
    }
    
    // Add validation for static text if enabled
    if (newLineStaticTextEnabled && !newLineStaticText.trim()) {
      notifications.show({ title: 'Validation Error', message: 'Static Text cannot be empty when enabled.', color: 'orange' });
      return;
    }
    
    createLineMutation.mutate({ 
        template_id: templateId,
        category_id: parseInt(newLineCategoryId, 10),
        line_key: newLineKey,
        order_index: newLineOrderIndex,
        prompt_hint: newLinePromptHint,
        static_text: newLineStaticTextEnabled ? newLineStaticText : undefined
    });
  };

  const handleEditLineClick = (line: VoScriptTemplateLine) => {
    setEditingLine(line);
    setEditLineKey(line.line_key);
    setEditLineCategoryId(String(line.category_id)); // Convert to string for Select
    setEditLineOrderIndex(line.order_index);
    setEditLinePromptHint(line.prompt_hint || '');
    
    // Set static text fields
    const hasStaticText = !!line.static_text;
    setEditLineStaticTextEnabled(hasStaticText);
    setEditLineStaticText(line.static_text || '');
    
    openEditLineModal();
  };

  const handleEditLineSubmit = () => {
    if (!editingLine || !editLineKey.trim() || !editLineCategoryId || editLineOrderIndex < 0) {
      notifications.show({ title: 'Validation Error', message: 'Line Key, Category, and Order Index are required.', color: 'orange' });
      return;
    }
    
    // Add validation for static text if enabled
    if (editLineStaticTextEnabled && !editLineStaticText.trim()) {
      notifications.show({ title: 'Validation Error', message: 'Static Text cannot be empty when enabled.', color: 'orange' });
      return;
    }
    
    const payload: { 
      category_id?: number; 
      line_key?: string; 
      order_index?: number; 
      prompt_hint?: string | null;
      static_text?: string | null;
    } = {};
    
    let changed = false;
    const newCatId = parseInt(editLineCategoryId, 10);

    if (editLineKey !== editingLine.line_key) { payload.line_key = editLineKey; changed = true; }
    if (newCatId !== editingLine.category_id) { payload.category_id = newCatId; changed = true; }
    if (editLineOrderIndex !== editingLine.order_index) { payload.order_index = editLineOrderIndex; changed = true; }
    if (editLinePromptHint !== (editingLine.prompt_hint || '')) { payload.prompt_hint = editLinePromptHint; changed = true; }
    
    // Handle static text changes
    const currentStaticText = editingLine.static_text || null;
    const newStaticText = editLineStaticTextEnabled ? editLineStaticText : null;
    
    if (newStaticText !== currentStaticText) {
      payload.static_text = newStaticText;
      changed = true;
    }

    if (changed) {
        updateLineMutation.mutate({ lineId: editingLine.id, data: payload });
    } else {
        closeEditLineModal();
    }
  };

  const handleDeleteLineClick = (lineId: number, lineKey: string) => {
    if (window.confirm(`Are you sure you want to delete line "${lineKey}"?`)) {
      deleteLineMutation.mutate(lineId);
    }
  };
  // --- END: Line Handlers --- 

  if (isLoading) {
    return <Loader />;
  }

  if (isError) {
    return (
        <Container size="xl">
            <Button variant="subtle" onClick={onBackToList} leftSection={<IconArrowLeft size={14}/>} mb="md">
                Back to List
            </Button>
            <Alert icon={<IconAlertCircle size="1rem" />} title="Error Loading Template" color="red">
                {error?.message || 'Could not load template details.'}
            </Alert>
        </Container>
    );
  }

  if (!template) {
      return (
         <Container size="xl">
            <Button variant="subtle" onClick={onBackToList} leftSection={<IconArrowLeft size={14}/>} mb="md">
                Back to List
            </Button>
            <Alert icon={<IconAlertCircle size="1rem" />} title="Not Found" color="orange">
                Template data not found.
            </Alert>
        </Container>
      );
  }

  // --- Render Logic for Categories --- 
  const categoryRows = template.categories?.map((cat) => (
    <Table.Tr key={cat.id}>
      <Table.Td>{cat.id}</Table.Td>
      <Table.Td>{cat.name}</Table.Td>
      <Table.Td>
          <Text truncate="end" maw={300}>{cat.prompt_instructions || '-'}</Text>
      </Table.Td>
      <Table.Td>
          <Group gap="xs">
              <ActionIcon variant="subtle" color="blue" onClick={() => handleEditCategoryClick(cat)}> 
                  <IconPencil size={16} /> 
              </ActionIcon>
              <ActionIcon 
                variant="subtle" 
                color="red" 
                onClick={() => handleDeleteCategoryClick(cat.id, cat.name)}
                loading={deleteCategoryMutation.isPending && deleteCategoryMutation.variables === cat.id}
              > 
                  <IconTrash size={16} /> 
              </ActionIcon>
          </Group>
      </Table.Td>
    </Table.Tr>
  ));

  // --- Render Logic for Lines --- 
  const lineRows = template.template_lines?.map((line) => (
    <Table.Tr key={line.id}>
      <Table.Td>{line.id}</Table.Td>
      <Table.Td>{line.line_key}</Table.Td>
      {/* Find category name - might be inefficient, consider joining in backend API later */}
      <Table.Td>{template.categories?.find(c => c.id === line.category_id)?.name || '-'}</Table.Td>
      <Table.Td>{line.order_index}</Table.Td>
      <Table.Td>
           <Text truncate="end" maw={300}>{line.prompt_hint || '-'}</Text>
      </Table.Td>
      <Table.Td>
        {line.static_text ? (
          <Text truncate="end" maw={300} fw={500} c="blue">{line.static_text}</Text>
        ) : (
          <Text c="dimmed" size="sm">Dynamic (LLM Generated)</Text>
        )}
      </Table.Td>
      <Table.Td>
          <Group gap="xs">
              <ActionIcon variant="subtle" color="blue" onClick={() => handleEditLineClick(line)}> 
                  <IconPencil size={16} /> 
              </ActionIcon>
              <ActionIcon 
                variant="subtle" 
                color="red" 
                onClick={() => handleDeleteLineClick(line.id, line.line_key)}
                loading={deleteLineMutation.isPending && deleteLineMutation.variables === line.id}
              > 
                  <IconTrash size={16} /> 
              </ActionIcon>
          </Group>
      </Table.Td>
    </Table.Tr>
  ));

  // --- Category Options for Select --- 
  const categoryOptions = template?.categories?.map(cat => ({ value: String(cat.id), label: cat.name })) || [];

  // --- ADD LOGGING --- 
  console.log("[TemplateDetailView Render] lineModalOpened:", lineModalOpened);
  // --- END LOGGING --- 

  return (
    <Container size="xl">
        <Button variant="subtle" onClick={onBackToList} leftSection={<IconArrowLeft size={14}/>} mb="md">
            Back to List
        </Button>
      <Paper shadow="xs" p="md" withBorder>
        <Title order={2} mb="lg">
          Template: {template.name} (ID: {template.id})
        </Title>

        <Tabs defaultValue="details">
          <Tabs.List>
            <Tabs.Tab value="details">
              Details
            </Tabs.Tab>
            <Tabs.Tab value="categories">
              Categories ({template.categories?.length || 0})
            </Tabs.Tab>
            <Tabs.Tab value="lines">
              Lines ({template.template_lines?.length || 0})
            </Tabs.Tab>
          </Tabs.List>

          <Space h="md" />

          <Tabs.Panel value="details">
            <Stack>
                <TextInput
                    label="Template Name"
                    required
                    value={name}
                    onChange={(event) => setName(event.currentTarget.value)}
                />
                <Textarea
                    label="Description (Optional)"
                    value={description}
                    onChange={(event) => setDescription(event.currentTarget.value)}
                    autosize
                    minRows={2}
                />
                <Textarea
                    label="General Prompt Hint (Optional)"
                    value={promptHint}
                    onChange={(event) => setPromptHint(event.currentTarget.value)}
                    autosize
                    minRows={4}
                />
                <Group justify="flex-end" mt="md">
                    <Button 
                        leftSection={<IconDeviceFloppy size={14}/>} 
                        onClick={handleDetailsSave}
                        loading={updateMutation.isPending}
                        disabled={!template || (name === template.name && description === (template.description || '') && promptHint === (template.prompt_hint || ''))}
                    >
                        Save Details
                    </Button>
                </Group>
            </Stack>
          </Tabs.Panel>

          <Tabs.Panel value="categories">
            <Group justify="flex-end" mb="sm">
                <Button size="xs" leftSection={<IconPlus size={14} />} onClick={openCatModal}>
                    Add Category
                </Button>
            </Group>
            <ScrollArea>
               <Table striped highlightOnHover withTableBorder withColumnBorders miw={700}>
                 <Table.Thead>
                   <Table.Tr>
                     <Table.Th>ID</Table.Th>
                     <Table.Th>Name</Table.Th>
                     <Table.Th>Instructions</Table.Th>
                     <Table.Th>Actions</Table.Th>
                   </Table.Tr>
                 </Table.Thead>
                 <Table.Tbody>
                    {categoryRows && categoryRows.length > 0 ? categoryRows : <Table.Tr><Table.Td colSpan={4}>No categories defined for this template.</Table.Td></Table.Tr>}
                </Table.Tbody>
               </Table>
            </ScrollArea>
          </Tabs.Panel>

          <Tabs.Panel value="lines">
            <Group justify="flex-end" mb="sm">
                <Button size="xs" leftSection={<IconPlus size={14} />} onClick={openLineModal}>
                    Add Line
                </Button>
            </Group>
             <ScrollArea>
               <Table striped highlightOnHover withTableBorder withColumnBorders miw={800}>
                 <Table.Thead>
                   <Table.Tr>
                     <Table.Th>ID</Table.Th>
                     <Table.Th>Line Key</Table.Th>
                     <Table.Th>Category</Table.Th>
                     <Table.Th>Order</Table.Th>
                     <Table.Th>Hint</Table.Th>
                     <Table.Th>Static Text</Table.Th>
                     <Table.Th>Actions</Table.Th>
                   </Table.Tr>
                 </Table.Thead>
                 <Table.Tbody>
                     {lineRows && lineRows.length > 0 ? lineRows : <Table.Tr><Table.Td colSpan={7}>No lines defined for this template.</Table.Td></Table.Tr>}
                 </Table.Tbody>
               </Table>
             </ScrollArea>
          </Tabs.Panel>
        </Tabs>
      </Paper>
      
      {/* --- NEW: Create Category Modal --- */}
      <AppModal 
          opened={catModalOpened} 
          onClose={closeCatModal} 
          title="Add New Category" 
          size="md" 
          centered 
          withinPortal
          styles={{
            inner: {
              left: 'calc(50% + 100px)',
              transform: 'translateX(-50%)',
            },
          }}
        >
            <Stack>
                <TextInput
                    label="Category Name"
                    placeholder="e.g., Abilities, Taunts"
                    required
                    value={newCatName}
                    onChange={(event) => setNewCatName(event.currentTarget.value)}
                />
                <Textarea
                    label="Prompt Instructions (Optional)"
                    placeholder="General instructions for AI generating lines in this category..."
                    value={newCatInstructions}
                    onChange={(event) => setNewCatInstructions(event.currentTarget.value)}
                    autosize
                    minRows={3}
                />
                <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={closeCatModal}>Cancel</Button>
                    <Button onClick={handleCreateCategorySubmit} loading={createCategoryMutation.isPending}>
                        Create Category
                    </Button>
                </Group>
            </Stack>
        </AppModal>
      {/* --- END: Create Category Modal --- */}

      {/* --- NEW: Edit Category Modal --- */}
      <AppModal 
          opened={editCatModalOpened} 
          onClose={closeEditCatModal} 
          title={`Edit Category: ${editingCategory?.name || ''}`} 
          size="md" 
          centered 
          withinPortal
          styles={{
            inner: {
              left: 'calc(50% + 100px)',
              transform: 'translateX(-50%)',
            },
          }}
        >
            {editingCategory && (
                 <Stack> 
                    <TextInput
                        label="Category Name"
                        required
                        value={editCatName}
                        onChange={(event) => setEditCatName(event.currentTarget.value)}
                    />
                    <Textarea
                        label="Prompt Instructions (Optional)"
                        placeholder="General instructions for AI generating lines in this category..."
                        value={editCatInstructions}
                        onChange={(event) => setEditCatInstructions(event.currentTarget.value)}
                        autosize
                        minRows={3}
                    />
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={closeEditCatModal}>Cancel</Button>
                        <Button onClick={handleEditCategorySubmit} loading={updateCategoryMutation.isPending}>
                            Save Changes
                        </Button>
                    </Group>
                </Stack>
            )}
        </AppModal>
      {/* --- END: Edit Category Modal --- */}

      {/* --- NEW: Create Line Modal --- */}
       <AppModal 
          opened={lineModalOpened} 
          onClose={closeLineModal} 
          title="Add New Template Line" 
          size="md" 
          centered 
          withinPortal
          styles={{
            inner: {
              left: 'calc(50% + 100px)',
              transform: 'translateX(-50%)',
            },
          }}
        >
            <Stack>
                 <TextInput 
                    label="Line Key"
                    placeholder="e.g., HeroSelection"
                    required
                    value={newLineKey}
                    onChange={(event) => setNewLineKey(event.currentTarget.value)}
                 />
                 <Select 
                    label="Category"
                    placeholder="Select category"
                    data={categoryOptions}
                    value={newLineCategoryId}
                    onChange={setNewLineCategoryId}
                    required
                    searchable
                 /> 
                  <TextInput 
                    label="Order Index"
                    type="number"
                    required
                    value={String(newLineOrderIndex)}
                    onChange={(event) => setNewLineOrderIndex(Number(event.currentTarget.value) || 0)}
                  />
                 <Textarea 
                    label="Prompt Hint (Optional)"
                    value={newLinePromptHint}
                    onChange={(event) => setNewLinePromptHint(event.currentTarget.value)}
                    autosize
                    minRows={3}
                 />
                 <Switch 
                    label="Use Static Text (bypass LLM generation)"
                    checked={newLineStaticTextEnabled}
                    onChange={(event) => setNewLineStaticTextEnabled(event.currentTarget.checked)}
                 />
                 {newLineStaticTextEnabled && (
                    <Textarea
                        label="Static Text"
                        required
                        placeholder="Fixed text to use for this line"
                        value={newLineStaticText}
                        onChange={(event) => setNewLineStaticText(event.currentTarget.value)}
                        autosize
                        minRows={3}
                    />
                 )}
                 <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={closeLineModal}>Cancel</Button>
                    <Button onClick={handleCreateLineSubmit} loading={createLineMutation.isPending}>
                        Create Line
                    </Button>
                 </Group>
            </Stack>
            
        </AppModal>
      {/* --- END: Create Line Modal --- */}

      {/* --- NEW: Edit Line Modal --- */}
      <AppModal 
          opened={editLineModalOpened} 
          onClose={closeEditLineModal} 
          title={`Edit Line: ${editingLine?.line_key || ''}`} 
          size="md" 
          centered 
          withinPortal
          styles={{
            inner: {
              left: 'calc(50% + 100px)',
              transform: 'translateX(-50%)',
            },
          }}
        >
           {editingLine && (
                <Stack>
                    <TextInput
                        label="Line Key"
                        required
                        value={editLineKey}
                        onChange={(event) => setEditLineKey(event.currentTarget.value)}
                    />
                    <Select
                        label="Category"
                        placeholder="Select category"
                        data={categoryOptions}
                        value={editLineCategoryId}
                        onChange={setEditLineCategoryId}
                        required
                        searchable
                    />
                    <TextInput 
                        label="Order Index"
                        type="number"
                        required
                        value={String(editLineOrderIndex)}
                        onChange={(event) => setEditLineOrderIndex(Number(event.currentTarget.value) || 0)}
                    />
                    <Textarea
                        label="Prompt Hint (Optional)"
                        value={editLinePromptHint}
                        onChange={(event) => setEditLinePromptHint(event.currentTarget.value)}
                        autosize
                        minRows={3}
                    />
                    <Switch 
                        label="Use Static Text (bypass LLM generation)"
                        checked={editLineStaticTextEnabled}
                        onChange={(event) => setEditLineStaticTextEnabled(event.currentTarget.checked)}
                    />
                    {editLineStaticTextEnabled && (
                      <Textarea
                          label="Static Text"
                          required
                          placeholder="Fixed text to use for this line"
                          value={editLineStaticText}
                          onChange={(event) => setEditLineStaticText(event.currentTarget.value)}
                          autosize
                          minRows={3}
                      />
                    )}
                    <Group justify="flex-end" mt="md">
                        <Button variant="default" onClick={closeEditLineModal}>Cancel</Button>
                        <Button onClick={handleEditLineSubmit} loading={updateLineMutation.isPending}>
                            Save Changes
                        </Button>
                    </Group>
                </Stack>
           )}
        </AppModal>
      {/* --- END: Edit Line Modal --- */}

    </Container>
  );
};

export default TemplateDetailView; 