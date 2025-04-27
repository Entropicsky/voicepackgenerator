import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
    Title, Text, Paper, Stack, Group, Button, LoadingOverlay, Alert, 
    Accordion, Textarea, ActionIcon, Tooltip, Badge 
} from '@mantine/core';
import { IconPlayerPlay, IconSend, IconRefresh, IconDeviceFloppy } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

// Import API functions
import { api } from '../api';
// Import types
import { VoScript, VoScriptLineData, JobSubmissionResponse, SubmitFeedbackPayload, RunAgentPayload, UpdateVoScriptPayload, UpdateVoScriptTemplateCategoryPayload, VoScriptCategoryData } from '../types';

const VoScriptDetailView: React.FC = () => {
  const { scriptId } = useParams<{ scriptId: string }>();
  const queryClient = useQueryClient();
  const numericScriptId = scriptId ? parseInt(scriptId, 10) : undefined;

  // --- State --- //
  const [feedbackInputs, setFeedbackInputs] = useState<Record<number, string>>({}); 
  const [scriptRefinementPrompt, setScriptRefinementPrompt] = useState<string>('');
  const [categoryRefinementPrompts, setCategoryRefinementPrompts] = useState<Record<string, string>>({}); // { categoryName: promptText }
  const [isScriptPromptDirty, setIsScriptPromptDirty] = useState(false);
  const [isCategoryPromptDirty, setIsCategoryPromptDirty] = useState<Record<string, boolean>>({}); // { categoryName: boolean }

  // --- 1. Fetch VO Script Details --- //
  const { 
    data: voScript, 
    isLoading: isLoadingScript, 
    error: scriptError, 
    isError: isScriptError, 
    refetch: refetchScript 
  } = useQuery<VoScript, Error>({
    queryKey: ['voScriptDetail', numericScriptId],
    queryFn: () => api.getVoScript(numericScriptId!),
    enabled: !!numericScriptId, 
  });

  // --- Initialize state based on fetched data --- //
  useEffect(() => {
    if (voScript) {
        setScriptRefinementPrompt(voScript.refinement_prompt || '');
        const initialCategoryPrompts: Record<string, string> = {};
        voScript.categories?.forEach((cat: VoScriptCategoryData) => {
            initialCategoryPrompts[cat.name] = cat.refinement_prompt || '';
        });
        setCategoryRefinementPrompts(initialCategoryPrompts);
        setIsScriptPromptDirty(false);
        setIsCategoryPromptDirty({});
    }
  }, [voScript]);

  // --- 2. Mutation for Running the Agent --- //
  const runAgentMutation = useMutation<JobSubmissionResponse, Error, RunAgentPayload>({
    mutationFn: (payload) => api.runVoScriptAgent(numericScriptId!, payload), // Use actual API function
    onSuccess: (data, variables) => {
      notifications.show({
        title: 'Agent Job Submitted',
        message: `Agent task '${variables.task_type}' (Job ID: ${data.job_id}) submitted successfully. Monitor progress on the Jobs page.`,
        color: 'blue',
      });
      // Consider invalidating or refetching after a delay?
      // setTimeout(() => queryClient.invalidateQueries({ queryKey: ['voScriptDetail', numericScriptId] }), 5000);
    },
    onError: (err, variables) => {
       notifications.show({
        title: 'Error Running Agent',
        message: err.message || `Could not submit agent task '${variables.task_type}'.`,
        color: 'red',
      });
    },
  });

  // --- 3. Mutation for Submitting Feedback --- //
  const submitFeedbackMutation = useMutation<VoScriptLineData, Error, SubmitFeedbackPayload>({
    mutationFn: (payload) => api.submitVoScriptFeedback(numericScriptId!, payload), // Use actual API function
    onSuccess: (updatedLine) => {
      // Update the specific line in the cache for instant UI update
      queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          categories: oldData.categories?.map(cat => 
            cat.id === updatedLine.id ? { ...cat, ...updatedLine } : cat
          )
        };
      });
      setFeedbackInputs(prev => ({ ...prev, [updatedLine.id]: '' })); 
      notifications.show({
        title: 'Feedback Submitted',
        message: `Feedback submitted successfully.`,
        color: 'green',
      });
    },
    onError: (err, variables) => {
      notifications.show({
        title: 'Error Submitting Feedback',
        message: err.message || `Could not submit feedback for line ${variables.line_id}.`,
        color: 'red',
      });
    },
  });

  // --- NEW: Script Prompt Update Mutation --- //
  const updateScriptPromptMutation = useMutation<VoScript, Error, UpdateVoScriptPayload>({
    mutationFn: (payload) => api.updateVoScript(numericScriptId!, payload),
    onSuccess: (updatedScript) => {
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => 
           oldData ? { ...oldData, refinement_prompt: updatedScript.refinement_prompt, updated_at: updatedScript.updated_at } : oldData
        );
        setScriptRefinementPrompt(updatedScript.refinement_prompt || ''); // Update local state
        setIsScriptPromptDirty(false); // Reset dirty flag
        notifications.show({ title: 'Script Prompt Saved', message: 'Overall script refinement prompt updated.', color: 'green' });
    },
    onError: (err) => {
        notifications.show({ title: 'Error Saving Script Prompt', message: err.message, color: 'red' });
    }
  });

  // --- NEW: Category Prompt Update Mutation --- //
  // We need the category ID for the API call, but we might only have the name easily available
  // Fetching category details or adding ID to the category data structure in getVoScript might be needed
  // For now, assuming we can get category ID somehow (e.g., if added to VoScriptCategoryData type)
  // TODO: Refactor this if category ID isn't readily available
  const updateCategoryPromptMutation = useMutation<VoScriptCategoryData, Error, { categoryId: number; payload: UpdateVoScriptTemplateCategoryPayload }>({
    mutationFn: ({ categoryId, payload }) => api.updateVoScriptTemplateCategory(categoryId, payload),
    onSuccess: (updatedCategory) => {
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
            if (!oldData) return oldData;
            return {
                ...oldData,
                categories: oldData.categories?.map((cat: VoScriptCategoryData) => 
                    cat.id === updatedCategory.id 
                    ? { ...cat, refinement_prompt: updatedCategory.refinement_prompt } 
                    : cat
                )
            };
        });
        setCategoryRefinementPrompts(prev => ({ ...prev, [updatedCategory.name]: updatedCategory.refinement_prompt || '' }));
        setIsCategoryPromptDirty(prev => ({ ...prev, [updatedCategory.name]: false })); 
        notifications.show({ title: 'Category Prompt Saved', message: `Refinement prompt for category '${updatedCategory.name}' updated.`, color: 'green' });
    },
    onError: (err) => {
        notifications.show({ title: 'Error Saving Category Prompt', message: err.message, color: 'red' });
    }
  });

  // --- Helper Functions --- //
  const handleFeedbackChange = (lineId: number, value: string) => {
    setFeedbackInputs(prev => ({ ...prev, [lineId]: value }));
  };

  const handleFeedbackSubmit = (lineId: number) => {
    const feedbackText = feedbackInputs[lineId];
    if (feedbackText === undefined || feedbackText.trim() === '') {
        notifications.show({ message: 'Feedback cannot be empty.', color: 'orange'});
        return;
    }
    submitFeedbackMutation.mutate({ line_id: lineId, feedback_text: feedbackText });
  };
  
  const handleRunAgent = (taskType: 'generate_draft' | 'refine_feedback' | 'refine_category', categoryName?: string) => {
      let payload: RunAgentPayload = { task_type: taskType };
      
      if (taskType === 'refine_category') {
          if (!categoryName) {
              console.error("Category name is required for refine_category task type.");
              notifications.show({ title: 'Error', message: 'Category name missing for refinement.', color: 'red' });
              return;
          }
          payload.category_name = categoryName;
          // TODO: Gather feedback specific to this category if needed?
      } else if (taskType === 'refine_feedback') {
           // TODO: Gather all feedback across the script?
           // For now, sending null feedback for this task type.
           payload.feedback = null; 
      }
      
      console.log("Running agent with payload:", payload);
      runAgentMutation.mutate(payload);
  }

  const handleScriptPromptChange = (value: string) => {
    setScriptRefinementPrompt(value);
    setIsScriptPromptDirty(true);
  };

  const handleSaveScriptPrompt = () => {
    updateScriptPromptMutation.mutate({ refinement_prompt: scriptRefinementPrompt });
  };

  const handleCategoryPromptChange = (categoryName: string, value: string) => {
    setCategoryRefinementPrompts(prev => ({ ...prev, [categoryName]: value }));
    setIsCategoryPromptDirty(prev => ({ ...prev, [categoryName]: true }));
  };

  const handleSaveCategoryPrompt = (categoryName: string, categoryId?: number) => {
    if (categoryId === undefined) {
         console.error("Cannot save category prompt without category ID.");
         notifications.show({ title: 'Error', message: 'Cannot save prompt, category ID missing.', color: 'red' });
         return;
    }
    const promptText = categoryRefinementPrompts[categoryName];
    updateCategoryPromptMutation.mutate({ 
        categoryId: categoryId,
        payload: { refinement_prompt: promptText }
    });
  };

  // --- 4. Render View --- //
  if (!numericScriptId) {
    return <Alert color="red">Invalid Script ID provided in URL.</Alert>;
  }

  if (isLoadingScript) {
    return <LoadingOverlay visible={true} overlayProps={{ radius: "sm", blur: 2 }} />;
  }

  if (isScriptError) {
    return <Alert color="red" title="Error">{scriptError.message || 'Failed to load VO Script details.'}</Alert>;
  }

  if (!voScript) {
      return <Alert color="orange">VO Script not found.</Alert>;
  }

  // Determine overall script generation status (simplified)
  const isGenerating = runAgentMutation.isPending; // Basic check if agent is running
  const hasPending = voScript.categories?.some(cat => cat.lines.some(l => l.status === 'pending'));
  const hasFeedback = voScript.categories?.some(cat => cat.lines.some(l => !!l.latest_feedback));
  // Determine if any category refine is running for button states
  const refiningCategory = runAgentMutation.isPending && runAgentMutation.variables?.task_type === 'refine_category';
  const refiningWhichCategory = refiningCategory ? runAgentMutation.variables?.category_name : null;

  return (
    <Stack>
      <LoadingOverlay visible={runAgentMutation.isPending} overlayProps={{ radius: "sm", blur: 2 }} />
      {/* Header: Title, Status, Actions */}
      <Group justify="space-between">
        <Stack gap="xs">
            <Title order={2}>{voScript.name}</Title>
            <Text c="dimmed">Template: {voScript.template_name || `ID ${voScript.template_id}`}</Text>
            {/* TODO: Add more metadata display? Character description? */}
        </Stack>
        <Group>
            <Badge color={isGenerating ? "blue" : (hasPending ? "orange" : "green")} size="lg">
                {isGenerating ? "Generating..." : (voScript.status || "Unknown")}
            </Badge>
            {/* TODO: Add other script-level actions? Edit metadata? */}
            <Button 
                leftSection={<IconPlayerPlay size={14} />} 
                onClick={() => handleRunAgent('generate_draft')} 
                disabled={runAgentMutation.isPending || !hasPending}
                loading={runAgentMutation.isPending && runAgentMutation.variables?.task_type === 'generate_draft'}
                variant="gradient" gradient={{ from: 'blue', to: 'cyan' }}
            >
                Generate Draft
            </Button>
             <Button 
                leftSection={<IconRefresh size={14} />} 
                onClick={() => handleRunAgent('refine_feedback')} 
                disabled={runAgentMutation.isPending}
                loading={runAgentMutation.isPending && runAgentMutation.variables?.task_type === 'refine_feedback'}
                variant="gradient" gradient={{ from: 'teal', to: 'lime' }}
            >
                Refine All (Feedback)
            </Button>
        </Group>
      </Group>

      {/* --- NEW: Script Refinement Prompt --- */}
      <Paper withBorder p="md" mt="md">
          <Group justify="space-between" mb="xs">
            <Title order={4}>Overall Script Refinement Prompt</Title>
            <Button 
                size="xs" 
                variant="light" 
                leftSection={<IconDeviceFloppy size={14}/>}
                onClick={handleSaveScriptPrompt}
                disabled={!isScriptPromptDirty || updateScriptPromptMutation.isPending}
                loading={updateScriptPromptMutation.isPending}
            >
                Save Script Prompt
            </Button>
          </Group>
          <Textarea
            placeholder="Enter overall instructions for refining the entire script (e.g., 'Make all lines more aggressive')"
            value={scriptRefinementPrompt}
            onChange={(e) => handleScriptPromptChange(e.currentTarget.value)}
            minRows={3}
            autosize
            disabled={updateScriptPromptMutation.isPending}
          />
      </Paper>
      {/* --- End Script Refinement Prompt --- */}

      {/* Display Character Description */}
      <Paper withBorder p="md" mt="md">
          <Title order={4} mb="xs">Character Description</Title>
          <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '200px', overflowY: 'auto', background: '#f9f9f9', padding: '10px', borderRadius: '4px', fontFamily: 'monospace' }}>
              {voScript.character_description} 
          </pre>
      </Paper>

      {/* Lines Accordion (Grouped by Category) */}
      <Accordion multiple defaultValue={voScript?.categories?.map((c: VoScriptCategoryData) => c.name) || []}> 
        {(voScript?.categories || []).map((category: VoScriptCategoryData) => ( 
          <Accordion.Item key={category.name} value={category.name}>
            <Accordion.Control>
                <Group justify="space-between">
                    <Stack gap={0}>
                        <Title order={4}>{category.name}</Title>
                        {category.instructions && <Text size="sm" c="dimmed">{category.instructions}</Text>}
                    </Stack>
                    <Button 
                        size="xs" 
                        variant="light" 
                        color="grape"
                        leftSection={<IconRefresh size={12} />} 
                        onClick={(e) => { 
                            e.stopPropagation(); // Prevent accordion toggle
                            handleRunAgent('refine_category', category.name);
                        }}
                        disabled={runAgentMutation.isPending} // Disable if any agent task is running
                        loading={refiningCategory && refiningWhichCategory === category.name}
                    >
                        Refine Category
                    </Button>
                </Group>
            </Accordion.Control>
            <Accordion.Panel>
                {/* Category Refinement Prompt Paper */}
                <Paper withBorder p="sm" radius="sm" mb="md" bg="gray.0">
                    <Group justify="space-between" mb="xs">
                        <Title order={5}>Category Refinement Prompt</Title>
                        <Button 
                            size="xs" 
                            variant="outline" 
                            leftSection={<IconDeviceFloppy size={12}/>}
                            onClick={() => category.id !== null && handleSaveCategoryPrompt(category.name, category.id)}
                            disabled={!isCategoryPromptDirty[category.name] || updateCategoryPromptMutation.isPending || category.id === null}
                            loading={updateCategoryPromptMutation.isPending && updateCategoryPromptMutation.variables?.categoryId === category.id}
                        >
                            Save Category Prompt
                        </Button>
                    </Group>
                    <Textarea
                        placeholder={`Enter instructions specific to refining the '${category.name}' category...`}
                        value={categoryRefinementPrompts[category.name] || ''}
                        onChange={(e) => handleCategoryPromptChange(category.name, e.currentTarget.value)}
                        minRows={2}
                        autosize
                        disabled={updateCategoryPromptMutation.isPending}
                        />
                </Paper>
                {/* Stack for lines */}
                <Stack>
                    {category.lines.map((line) => (
                      <Paper key={line.id} withBorder p="sm" radius="md">
                        <Stack>
                            <Group justify="space-between">
                                <Text fw={500}>{line.line_key || `Line ID: ${line.id}`}</Text>
                                <Badge size="sm" variant="light" color={line.status === 'pending' ? 'gray' : (line.status === 'generated' ? 'green' : 'blue')}>
                                    {line.status}
                                </Badge>
                            </Group>
                            {line.template_prompt_hint && <Text size="xs" c="dimmed">Hint: {line.template_prompt_hint}</Text>}
                            
                            {/* Display Generated Text (if available) */}
                            {line.generated_text ? (
                                <Textarea value={line.generated_text} readOnly minRows={2} autosize label="Generated Text" />
                            ) : (
                                <Text c="dimmed" size="sm">No text generated yet.</Text>
                            )}
                            
                            {/* Display Latest Feedback (if available) */}
                            {line.latest_feedback && (
                                <Alert title="Latest Feedback" color="yellow" variant="light" radius="xs" p="xs">
                                    <Text size="sm">{line.latest_feedback}</Text>
                                </Alert>
                            )}

                            {/* Feedback Input Area */}
                            <Group align="flex-end">
                                <Textarea
                                    placeholder="Provide feedback for this line..."
                                    value={feedbackInputs[line.id] || ''}
                                    onChange={(e) => handleFeedbackChange(line.id, e.currentTarget.value)}
                                    minRows={1}
                                    autosize
                                    style={{ flexGrow: 1 }}
                                    disabled={submitFeedbackMutation.isPending && submitFeedbackMutation.variables?.line_id === line.id}
                                />
                                <Tooltip label="Submit Feedback">
                                    <ActionIcon 
                                        onClick={() => handleFeedbackSubmit(line.id)} 
                                        variant="filled" 
                                        color="blue"
                                        size="lg"
                                        loading={submitFeedbackMutation.isPending && submitFeedbackMutation.variables?.line_id === line.id}
                                        disabled={!feedbackInputs[line.id]?.trim()}
                                    >
                                        <IconSend size={18} />
                                    </ActionIcon>
                                </Tooltip>
                            </Group>
                            
                            {/* TODO: Add Audio Player if audio exists */}
                            {/* TODO: Add Regenerate button per line? */}
                            {/* TODO: Display Generation History? */}

                        </Stack>
                      </Paper>
                    ))}
                    {category.lines.length === 0 && <Text c="dimmed">No lines in this category.</Text>}
                </Stack>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
        {(voScript.categories || []).length === 0 && (
             <Text c="dimmed">No categories or lines found for this script.</Text>
        )}
      </Accordion>

    </Stack>
  );
};

export default VoScriptDetailView; 