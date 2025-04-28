import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
    Title, Text, Paper, Stack, Group, Button, LoadingOverlay, Alert, 
    Accordion, Textarea, ActionIcon, Tooltip, Badge 
} from '@mantine/core';
import { IconPlayerPlay, IconSend, IconRefresh, IconDeviceFloppy, IconSparkles } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

// Import API functions
import { api } from '../api';
// Import types
import { VoScript, VoScriptLineData, JobSubmissionResponse, SubmitFeedbackPayload, RunAgentPayload, UpdateVoScriptPayload, UpdateVoScriptTemplateCategoryPayload, VoScriptCategoryData, RefineLinePayload, RefineLineResponse, RefineCategoryPayload, RefineMultipleLinesResponse, RefineScriptPayload } from '../types';

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
  // NEW: State for line refinement loading status
  const [refiningLineId, setRefiningLineId] = useState<number | null>(null);
  // NEW: State for category refinement loading status
  const [refiningCategoryId, setRefiningCategoryId] = useState<number | null>(null);
  // NEW: State for global script refinement loading status
  const [isRefiningScript, setIsRefiningScript] = useState<boolean>(false);
  // NEW: State for editable character description
  const [editedCharacterDescription, setEditedCharacterDescription] = useState<string>('');
  const [isDescriptionDirty, setIsDescriptionDirty] = useState<boolean>(false);

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
        // Initialize editable description
        setEditedCharacterDescription(voScript.character_description || ''); 
        setIsScriptPromptDirty(false);
        setIsCategoryPromptDirty({});
        setIsDescriptionDirty(false); // Reset dirty flag for description
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
        // Update line data within its category
        return {
          ...oldData,
          categories: oldData.categories?.map(cat => ({
             ...cat,
             lines: cat.lines.map(l => l.id === updatedLine.id ? { ...l, ...updatedLine } : l)
          }))
        };
      });
      // Don't clear feedback input upon saving feedback, user might want to refine it
      // setFeedbackInputs(prev => ({ ...prev, [updatedLine.id]: '' })); 
      notifications.show({
        title: 'Feedback Submitted',
        message: `Feedback saved for line ID ${updatedLine.id}. You can now refine based on this feedback.`, // Updated message
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
           oldData ? { 
               ...oldData, 
               refinement_prompt: updatedScript.refinement_prompt !== undefined ? updatedScript.refinement_prompt : oldData.refinement_prompt,
               character_description: updatedScript.character_description !== undefined ? updatedScript.character_description : oldData.character_description,
               updated_at: updatedScript.updated_at
            } : oldData
        );
        if (updatedScript.refinement_prompt !== undefined) {
            setScriptRefinementPrompt(updatedScript.refinement_prompt || '');
            setIsScriptPromptDirty(false); 
        }
        if (updatedScript.character_description !== undefined) {
             setEditedCharacterDescription(updatedScript.character_description || '');
             setIsDescriptionDirty(false);
        }
        notifications.show({ title: 'Script Updated', message: 'Script details saved successfully.', color: 'green' });
    },
    onError: (err) => {
        notifications.show({ title: 'Error Saving Script Details', message: err.message, color: 'red' });
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

  // --- NEW: Line Refinement Mutation --- //
  const refineLineMutation = useMutation<RefineLineResponse, Error, { lineId: number; payload: RefineLinePayload }>({
      mutationFn: ({ lineId, payload }) => api.refineVoScriptLine(numericScriptId!, lineId, payload),
      onMutate: (variables) => {
        // Set loading state for the specific line being refined
        setRefiningLineId(variables.lineId);
      },
      onSuccess: (updatedLine) => {
        // Update the specific line in the React Query cache
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
            if (!oldData) return oldData;
            return {
              ...oldData,
              categories: oldData.categories?.map(cat => ({
                 ...cat,
                 lines: cat.lines.map(l => l.id === updatedLine.id ? { ...l, ...updatedLine } : l)
              }))
            };
        });
        notifications.show({
          title: 'Line Refined',
          message: `Line ${updatedLine.id} refined successfully. Status set to '${updatedLine.status}'.`,
          color: 'blue',
        });
      },
      onError: (err, variables) => {
        notifications.show({
          title: 'Error Refining Line',
          message: err.message || `Could not refine line ${variables.lineId}.`,
          color: 'red',
        });
      },
      onSettled: () => {
         // Clear loading state regardless of success or error
        setRefiningLineId(null);
      },
  });
  // --- END: Line Refinement Mutation --- //

  // --- NEW: Category Refinement Mutation --- //
  const refineCategoryMutation = useMutation<RefineMultipleLinesResponse, Error, { categoryId: number | null; payload: RefineCategoryPayload }>({
    mutationFn: ({ payload }) => api.refineVoScriptCategory(numericScriptId!, payload),
    onMutate: (variables) => {
        // Set loading state for the specific category being refined
        setRefiningCategoryId(variables.categoryId); // Use category ID for state
    },
    onSuccess: (response, variables) => {
        // Update all returned lines in the React Query cache
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
            if (!oldData || !response.data) return oldData;
            
            // Create a map of updated lines for quick lookup
            const updatedLinesMap = new Map(response.data.map(line => [line.id, line]));
            
            return {
              ...oldData,
              categories: oldData.categories?.map(cat => ({
                 ...cat,
                 // Update lines within this category if they exist in the response map
                 lines: cat.lines.map(l => updatedLinesMap.has(l.id) ? { ...l, ...updatedLinesMap.get(l.id)! } : l)
              }))
            };
        });
        notifications.show({
          title: 'Category Refined',
          message: response.message || `Category '${variables.payload.category_name}' refined successfully. (${response.data.length} lines updated).`,
          color: 'blue',
        });
    },
    onError: (err, variables) => {
        notifications.show({
          title: 'Error Refining Category',
          message: err.message || `Could not refine category '${variables.payload.category_name}'.`,
          color: 'red',
        });
    },
    onSettled: () => {
        // Clear loading state
        setRefiningCategoryId(null);
    },
  });
  // --- END: Category Refinement Mutation --- //

  // --- NEW: Script Refinement Mutation --- //
  const refineScriptMutation = useMutation<RefineMultipleLinesResponse, Error, { payload: RefineScriptPayload }>({
      mutationFn: ({ payload }) => api.refineVoScript(numericScriptId!, payload),
      onMutate: () => {
          setIsRefiningScript(true); // Set global loading state
      },
      onSuccess: (response) => {
          // Update all returned lines in the React Query cache
          queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
              if (!oldData || !response.data) return oldData;
              const updatedLinesMap = new Map(response.data.map(line => [line.id, line]));
              return {
                ...oldData,
                categories: oldData.categories?.map(cat => ({
                   ...cat,
                   lines: cat.lines.map(l => updatedLinesMap.has(l.id) ? { ...l, ...updatedLinesMap.get(l.id)! } : l)
                }))
              };
          });
          notifications.show({
            title: 'Script Refined',
            message: response.message || `Script refined successfully. (${response.data.length} lines updated).`,
            color: 'blue',
          });
      },
      onError: (err) => {
          notifications.show({
            title: 'Error Refining Script',
            message: err.message || `Could not refine the script.`,
            color: 'red',
          });
      },
      onSettled: () => {
          setIsRefiningScript(false); // Clear global loading state
      },
    });
  // --- END: Script Refinement Mutation --- //

  // --- Helper Functions --- //
  const handleFeedbackChange = (lineId: number, value: string) => {
    setFeedbackInputs(prev => ({ ...prev, [lineId]: value }));
  };

  const handleFeedbackSubmit = (lineId: number) => {
    const feedbackText = feedbackInputs[lineId];
    if (feedbackText === undefined || feedbackText.trim() === '') {
        notifications.show({ message: 'Feedback cannot be empty (or just whitespace). If you want to clear feedback, submit empty text after saving.', color: 'orange'});
        return;
    }
    submitFeedbackMutation.mutate({ line_id: lineId, feedback_text: feedbackText });
  };
  
  const handleRunAgent = (taskType: 'generate_draft') => { 
      let payload: RunAgentPayload = { task_type: taskType };
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

  // Reworked: Now triggers line refinement
  const handleRefineLine = (lineId: number) => {
      const promptText = feedbackInputs[lineId]; // Use feedback input as the prompt
      if (promptText === undefined || promptText.trim() === '') {
          notifications.show({ message: 'Refinement prompt cannot be empty. Please enter instructions in the text area first.', color: 'orange'});
          return;
      }
      refineLineMutation.mutate({ lineId, payload: { line_prompt: promptText } });
  };

  // Reworked: Triggers category refinement API call
  const handleRefineCategory = (categoryId: number | null, categoryName: string) => {
      const promptText = categoryRefinementPrompts[categoryName];
      if (!promptText?.trim()) {
          notifications.show({ message: `Category refinement prompt for '${categoryName}' cannot be empty.`, color: 'orange' });
          return;
      }
      if (numericScriptId === undefined) return; // Should not happen
      
      // TODO: Optionally gather visible line prompts within this category?
      // const linePromptsInCategory = ... gather from feedbackInputs ...
      
      refineCategoryMutation.mutate({ 
          categoryId,
          payload: { category_name: categoryName, category_prompt: promptText }
      });
  };

  // NEW: Triggers script refinement API call
  const handleRefineScript = () => {
      const promptText = scriptRefinementPrompt;
      if (!promptText?.trim()) {
          notifications.show({ message: `Overall script refinement prompt cannot be empty.`, color: 'orange' });
          return;
      }
      if (numericScriptId === undefined) return;
      
      // TODO: Optionally gather visible category/line prompts?
      
      refineScriptMutation.mutate({ 
          payload: { global_prompt: promptText }
      });
  };

  // NEW: Handler for description change
  const handleDescriptionChange = (value: string) => {
      setEditedCharacterDescription(value);
      // Check if different from original (fetched) description
      setIsDescriptionDirty(value !== (voScript?.character_description || ''));
  };

  // NEW: Handler for saving description
  const handleSaveDescription = () => {
      if (!isDescriptionDirty) return; // Don't save if no changes
      // Use the existing updateVoScript mutation, passing only the description
      updateScriptPromptMutation.mutate({ character_description: editedCharacterDescription });
      // Note: updateScriptPromptMutation onSuccess needs to handle description update in cache
      // OR create a dedicated mutation for description update.
      // For now, reusing existing mutation assuming it handles partial updates correctly
      // and its onSuccess updates the cache appropriately. We may need to adjust this.
      setIsDescriptionDirty(false); // Optimistically reset dirty flag
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
      <LoadingOverlay visible={isRefiningScript} overlayProps={{ radius: "sm", blur: 2 }} />
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
                disabled={runAgentMutation.isPending || isRefiningScript}
                loading={runAgentMutation.isPending && runAgentMutation.variables?.task_type === 'generate_draft'}
                variant="gradient" gradient={{ from: 'blue', to: 'cyan' }}
            >
                Generate Draft
            </Button>
            <Button 
                leftSection={<IconSparkles size={14} />}
                onClick={handleRefineScript}
                disabled={isRefiningScript || runAgentMutation.isPending}
                loading={isRefiningScript}
                variant="gradient" gradient={{ from: 'teal', to: 'lime' }}
            >
                Refine Script
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
                disabled={!isScriptPromptDirty || updateScriptPromptMutation.isPending || isRefiningScript}
                loading={updateScriptPromptMutation.isPending}
            >
                Save Script Prompt
            </Button>
          </Group>
          <Textarea
            placeholder="Enter overall instructions... Click 'Refine Script' above to apply."
            value={scriptRefinementPrompt}
            onChange={(e) => handleScriptPromptChange(e.currentTarget.value)}
            minRows={3}
            autosize
            disabled={updateScriptPromptMutation.isPending || isRefiningScript}
          />
      </Paper>
      {/* --- End Script Refinement Prompt --- */}

      {/* Display Character Description - MODIFIED */}
      <Paper withBorder p="md" mt="md">
          <Group justify="space-between" mb="xs">
              <Title order={4}>Character Description</Title>
              <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconDeviceFloppy size={14}/>}
                  onClick={handleSaveDescription}
                  disabled={!isDescriptionDirty || updateScriptPromptMutation.isPending || isRefiningScript}
                  loading={updateScriptPromptMutation.isPending}
              >
                  Save Description
              </Button>
          </Group>
          <Textarea
              placeholder="Enter detailed character description..."
              value={editedCharacterDescription}
              onChange={(event) => handleDescriptionChange(event.currentTarget.value)}
              minRows={5} // Adjust rows as needed
              autosize
              disabled={updateScriptPromptMutation.isPending || isRefiningScript}
          />
          {/* <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: '200px', overflowY: 'auto', background: '#f9f9f9', padding: '10px', borderRadius: '4px', fontFamily: 'monospace' }}>
              {voScript.character_description} 
          </pre> */}
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
                            e.stopPropagation(); 
                            handleRefineCategory(category.id, category.name); // Call new handler
                        }}
                        disabled={refineCategoryMutation.isPending && refiningCategoryId === category.id}
                        loading={refineCategoryMutation.isPending && refiningCategoryId === category.id}
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
                            disabled={!isCategoryPromptDirty[category.name] || updateCategoryPromptMutation.isPending || category.id === null || (refineCategoryMutation.isPending && refiningCategoryId === category.id)}
                            loading={updateCategoryPromptMutation.isPending && updateCategoryPromptMutation.variables?.categoryId === category.id}
                        >
                            Save Category Prompt
                        </Button>
                    </Group>
                    <Textarea
                        placeholder={`Enter instructions specific to refining the '${category.name}' category... Click \"Refine Category\" above to apply.`}
                        value={categoryRefinementPrompts[category.name] || ''}
                        onChange={(e) => handleCategoryPromptChange(category.name, e.currentTarget.value)}
                        minRows={2}
                        autosize
                        disabled={updateCategoryPromptMutation.isPending || (refineCategoryMutation.isPending && refiningCategoryId === category.id)}
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
                                    label="Feedback / Refinement Prompt"
                                    placeholder="Provide feedback or enter a prompt to refine this line..."
                                    value={feedbackInputs[line.id] || ''}
                                    onChange={(e) => handleFeedbackChange(line.id, e.currentTarget.value)}
                                    minRows={1}
                                    autosize
                                    style={{ flexGrow: 1 }}
                                    disabled={submitFeedbackMutation.isPending && submitFeedbackMutation.variables?.line_id === line.id 
                                              || refineLineMutation.isPending && refiningLineId === line.id
                                             }
                                />
                                <Tooltip label="Save Feedback">
                                    <ActionIcon 
                                        onClick={() => handleFeedbackSubmit(line.id)} 
                                        variant="filled" 
                                        color="yellow"
                                        size="lg"
                                        loading={submitFeedbackMutation.isPending && submitFeedbackMutation.variables?.line_id === line.id}
                                        disabled={!feedbackInputs[line.id]?.trim() 
                                                  || refineLineMutation.isPending && refiningLineId === line.id
                                                 }
                                    >
                                        <IconDeviceFloppy size={18} />
                                    </ActionIcon>
                                </Tooltip>
                                <Tooltip label="Refine Line (uses text above as prompt)">
                                     <ActionIcon 
                                        onClick={() => handleRefineLine(line.id)} 
                                        variant="filled" 
                                        color="blue"
                                        size="lg"
                                        loading={refineLineMutation.isPending && refiningLineId === line.id}
                                        disabled={!feedbackInputs[line.id]?.trim() 
                                                  || submitFeedbackMutation.isPending && submitFeedbackMutation.variables?.line_id === line.id
                                                 }
                                    >
                                        <IconSparkles size={18} />
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