import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, TextInput, Textarea, Select, Title, Paper, Group, Stack, LoadingOverlay, Alert } from '@mantine/core';
import { notifications } from '@mantine/notifications';
// Import API functions
import { api } from '../api'; 
// Import types
import { VoScriptTemplateMetadata, VoScript, CreateVoScriptPayload } from '../types';


const VoScriptCreateView: React.FC = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // 1. Form State
  const [scriptName, setScriptName] = useState('');
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [characterDescription, setCharacterDescription] = useState('SMITE God:\nSkin:\nTheme/Visual Design:\nSex:\nAge:\nGeneral Vibe:\nLanguage Accent:\nPersonality/Story:\nVoice Casting Notes:');

  // 2. Fetch available VO Script Templates for the dropdown
  const { data: templates, isLoading: isLoadingTemplates, error: templatesError } = useQuery<VoScriptTemplateMetadata[], Error>({
    queryKey: ['voScriptTemplatesMetadata'], 
    queryFn: api.fetchVoScriptTemplates, // Use actual API function
  });

  // 3. Setup Mutation for Creating the Script
  const createMutation = useMutation<VoScript, Error, CreateVoScriptPayload>({
    mutationFn: api.createVoScript, // Use actual API function
    onSuccess: (newScript) => {
      queryClient.invalidateQueries({ queryKey: ['voScripts'] }); // Invalidate the list view query
      notifications.show({
        title: 'Script Created',
        message: `VO Script "${newScript.name}" created successfully.`,
        color: 'green',
      });
      // Navigate to the new script's detail page
      navigate(`/vo-scripts/${newScript.id}`);
    },
    onError: (err) => {
      notifications.show({
        title: 'Error Creating Script',
        message: err.message || 'Could not create the VO script.',
        color: 'red',
      });
      console.error("Error creating script:", err.message);
    },
  });

  // 4. Handle Form Submission
  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!scriptName || !selectedTemplateId || characterDescription === null) {
      notifications.show({
          title: 'Validation Error',
          message: 'Please fill in all required fields (Name, Template, Description).',
          color: 'orange',
      });
      return;
    }

    createMutation.mutate({ 
        name: scriptName, 
        template_id: parseInt(selectedTemplateId, 10),
        character_description: characterDescription
    });
  };

  // 5. Render the Form
  const templateOptions = templates?.map(t => ({ value: String(t.id), label: t.name })) || [];

  return (
    <Paper shadow="md" p="xl" withBorder>
        <LoadingOverlay visible={createMutation.isPending || isLoadingTemplates} overlayProps={{ radius: "sm", blur: 2 }} />
        <Title order={2} mb="lg">Create New VO Script</Title>
        
        {templatesError && (
            <Alert title="Error Loading Templates" color="red" mb="md">
            {templatesError.message || 'Could not fetch script templates.'}
            </Alert>
        )}

        <form onSubmit={handleSubmit}>
            <Stack>
                <TextInput
                    required
                    label="Script Name"
                    placeholder="Enter a name for this VO script"
                    value={scriptName}
                    onChange={(event) => setScriptName(event.currentTarget.value)}
                    disabled={createMutation.isPending}
                />

                <Select
                    required
                    label="Select Template"
                    placeholder="Choose the template to base this script on"
                    data={templateOptions}
                    value={selectedTemplateId}
                    onChange={setSelectedTemplateId}
                    disabled={isLoadingTemplates || createMutation.isPending || !templates}
                    searchable
                />
                
                <Textarea
                    required
                    label="Character Description"
                    description="Provide detailed character context (traits, background, personality, specific format if desired)."
                    placeholder='Example:\nSMITE God: Odin\nSkin: Bratwurst\nTheme: 80s Gym Bro\nPersonality: ...'
                    value={characterDescription}
                    onChange={(event) => setCharacterDescription(event.currentTarget.value)}
                    minRows={8}
                    autosize
                    disabled={createMutation.isPending}
                />

                <Group justify="flex-end" mt="lg">
                    <Button variant="default" onClick={() => navigate('/vo-scripts')} disabled={createMutation.isPending}>
                        Cancel
                    </Button>
                    <Button type="submit" loading={createMutation.isPending} disabled={isLoadingTemplates}>
                        Create Script
                    </Button>
                </Group>
            </Stack>
        </form>
    </Paper>
  );
};

export default VoScriptCreateView; 