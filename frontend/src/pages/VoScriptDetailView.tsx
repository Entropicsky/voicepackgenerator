import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
    Title, Text, Paper, Stack, Group, Button, LoadingOverlay, Alert, 
    Accordion, Textarea, ActionIcon, Tooltip, Badge, Table, Modal, TextInput, Progress, ScrollArea,
    Checkbox
} from '@mantine/core';
import { IconPlayerPlay, IconSend, IconRefresh, IconDeviceFloppy, IconSparkles, IconLock, IconLockOpen, IconTrash, IconPlus, IconHistory, IconCheck } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useDisclosure } from '@mantine/hooks';

// Import API functions
import { api } from '../api';
// Import types
import { VoScript, VoScriptLineData, JobSubmissionResponse, SubmitFeedbackPayload, RunAgentPayload, UpdateVoScriptPayload, UpdateVoScriptTemplateCategoryPayload, VoScriptCategoryData, RefineLinePayload, RefineLineResponse, RefineCategoryPayload, RefineMultipleLinesResponse, RefineScriptPayload, DeleteResponse, AddVoScriptLinePayload } from '../types';

const VoScriptDetailView: React.FC = () => {
  const { scriptId } = useParams<{ scriptId: string }>();
  const queryClient = useQueryClient();
  const numericScriptId = scriptId ? parseInt(scriptId, 10) : undefined;

  // --- State --- //
  const [feedbackInputs, setFeedbackInputs] = useState<Record<number, string>>({});
  // Removed categoryRefinementPrompts state - using transitory approach
  const [isDescriptionDirty, setIsDescriptionDirty] = useState<boolean>(false);
  // NEW: State for line refinement loading status
  const [refiningLineId, setRefiningLineId] = useState<number | null>(null);
  // NEW: State for category refinement loading status
  const [refiningCategoryId, setRefiningCategoryId] = useState<number | null>(null);
  // NEW: State for global script refinement loading status
  const [isRefiningScript, setIsRefiningScript] = useState<boolean>(false);
  // NEW: State for editable character description
  const [editedCharacterDescription, setEditedCharacterDescription] = useState<string>('');
  // NEW: State for inline text edits { lineId: editedText }
  const [editedLineText, setEditedLineText] = useState<Record<number, string>>({});
  // NEW: State for manual save loading
  const [savingLineId, setSavingLineId] = useState<number | null>(null);
  // NEW: State for delete loading
  const [deletingLineId, setDeletingLineId] = useState<number | null>(null);
  // NEW: State for Refine Line Modal
  const [refineModalOpened, { open: openRefineModal, close: closeRefineModal }] = useDisclosure(false);
  const [lineToRefine, setLineToRefine] = useState<VoScriptLineData | null>(null);
  const [refineLinePromptInput, setRefineLinePromptInput] = useState<string>('');
  // NEW: State for lock toggle loading
  const [togglingLockLineId, setTogglingLockLineId] = useState<number | null>(null);
  // State for Add Line Modal (needed later)
  const [addLineModalOpened, { open: openAddLineModal, close: closeAddLineModal }] = useDisclosure(false);
  const [categoryForNewLine, setCategoryForNewLine] = useState<VoScriptCategoryData | null>(null);
  // NEW: State for Add Line form inputs
  const [newLineKeyInput, setNewLineKeyInput] = useState<string>('');
  const [newLineTextInput, setNewLineTextInput] = useState<string>('');
  const [newLineOrderInput, setNewLineOrderInput] = useState<string>('0'); // Use string for input
  const [newLineHintInput, setNewLineHintInput] = useState<string>('');
  // NEW: State for detailed progress tracking
  const [refinementProgress, setRefinementProgress] = useState<{
    total: number;
    completed: number;
    currentKey: string | null;
    errors: string[];
    running: boolean; // Track if the process is active
  }>({ total: 0, completed: 0, currentKey: null, errors: [], running: false });
  // NEW: State for History Modal
  const [historyModalOpened, { open: openHistoryModal, close: closeHistoryModal }] = useDisclosure(false);
  const [lineToViewHistory, setLineToViewHistory] = useState<VoScriptLineData | null>(null);
  // NEW: State for controlled accordion
  const [openCategories, setOpenCategories] = useState<string[]>([]); 
  // NEW: State for Category Refine Modal
  const [categoryRefineModalOpened, { open: openCategoryRefineModal, close: closeCategoryRefineModal }] = useDisclosure(false);
  const [categoryToRefine, setCategoryToRefine] = useState<{ id: number | null, name: string } | null>(null);
  const [categoryRefinePromptInput, setCategoryRefinePromptInput] = useState<string>('');
  // NEW: State for Script Refine Modal
  const [scriptRefineModalOpened, { open: openScriptRefineModal, close: closeScriptRefineModal }] = useDisclosure(false);
  const [scriptRefinePromptInput, setScriptRefinePromptInput] = useState<string>('');
  // NEW: State for checkboxes
  const [applyRulesToLine, setApplyRulesToLine] = useState<boolean>(false);
  const [applyRulesToCategory, setApplyRulesToCategory] = useState<boolean>(false);
  const [applyRulesToScript, setApplyRulesToScript] = useState<boolean>(false);

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
        setEditedCharacterDescription(voScript.character_description || ''); 
        setIsDescriptionDirty(false);
        const allCategoryNames = voScript.categories?.map(c => c.name) || [];
        setOpenCategories(allCategoryNames);
    }
  }, [voScript]);

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

  // --- RE-ADD: Script Update Mutation (for Character Description) --- //
  const updateScriptPromptMutation = useMutation<VoScript, Error, UpdateVoScriptPayload>({
    mutationFn: (payload) => api.updateVoScript(numericScriptId!, payload),
    onSuccess: (updatedScript) => {
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => 
           oldData ? { 
               ...oldData, 
               // Only handle character_description update here
               character_description: updatedScript.character_description !== undefined ? updatedScript.character_description : oldData.character_description,
               updated_at: updatedScript.updated_at
            } : oldData
        );
        // Only handle description state update here
        if (updatedScript.character_description !== undefined) {
             setEditedCharacterDescription(updatedScript.character_description || '');
             setIsDescriptionDirty(false);
        }
        // Adjust notification if needed, or keep general
        notifications.show({ title: 'Script Updated', message: 'Script details saved successfully.', color: 'green' }); 
    },
    onError: (err) => {
        notifications.show({ title: 'Error Saving Script Details', message: err.message, color: 'red' });
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

  // --- NEW: Generate Single Line Mutation --- //
  const generateLineMutation = useMutation<VoScriptLineData, Error, { lineId: number }>({ 
      mutationFn: ({ lineId }) => api.generateVoScriptLine(numericScriptId!, lineId),
      // Note: onSuccess/onError/onSettled for individual lines during orchestration
      // will be handled within the loop calling mutateAsync, but we can define
      // generic handlers here if needed for other use cases later.
      onSuccess: (updatedLine) => {
        // Update cache for this single generated line
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
        // Don't show notification here, will be handled by orchestration
      },
      onError: (err, variables) => {
        // Error will be caught and logged by the orchestration loop
        console.error(`Error generating line ${variables.lineId} via mutation:`, err);
      },
      // No specific onMutate/onSettled needed here as loading is handled by orchestration state
  });

  // --- NEW: Script Refinement Mutation --- //
  const refineScriptMutation = useMutation<RefineMultipleLinesResponse, Error, { payload: RefineScriptPayload }>({
    mutationFn: ({ payload }) => api.refineVoScript(numericScriptId!, payload),
    onMutate: () => {
        // Set loading state
        setIsRefiningScript(true);
    },
    onSuccess: (response) => {
        // Update all returned lines in the React Query cache
        queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
            if (!oldData || !response.data) return oldData;
            
            // Create a map of updated lines for quick lookup
            const updatedLinesMap = new Map(response.data.map(line => [line.id, line]));
            
            return {
              ...oldData,
              categories: oldData.categories?.map(cat => ({
                 ...cat,
                 // Update lines that exist in the response map
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
          message: err.message || `Script refinement failed.`,
          color: 'red',
        });
    },
    onSettled: () => {
        // Clear loading state
        setIsRefiningScript(false);
    },
  });
  // --- END: Script Refinement Mutation --- //

  // --- NEW: Manual Text Update Mutation --- //
  const updateLineTextMutation = useMutation<VoScriptLineData, Error, { lineId: number; newText: string }>({
      mutationFn: ({ lineId, newText }) => api.updateLineText(numericScriptId!, lineId, newText),
      onMutate: (variables) => {
          setSavingLineId(variables.lineId);
      },
      onSuccess: (updatedLine) => {
          // Update cache
          queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
              if (!oldData) return oldData;
              const updatedLinesMap = new Map([[updatedLine.id, updatedLine]]);
              return {
                ...oldData,
                categories: oldData.categories?.map(cat => ({
                   ...cat,
                   lines: cat.lines.map(l => updatedLinesMap.has(l.id) ? { ...l, ...updatedLinesMap.get(l.id)! } : l)
                }))
              };
          });
          // Clear the edit state for this line on successful save
          setEditedLineText(prev => {
              const newState = { ...prev };
              delete newState[updatedLine.id];
              return newState;
          });
          notifications.show({
              title: 'Line Saved',
              message: `Manual edits for line ${updatedLine.id} saved successfully.`,
              color: 'green',
          });
      },
      onError: (err, variables) => {
          notifications.show({
              title: 'Error Saving Line',
              message: err.message || `Could not save manual edits for line ${variables.lineId}.`,
              color: 'red',
          });
      },
      onSettled: () => {
          setSavingLineId(null);
      },
  });
  // --- END: Manual Text Update Mutation --- //

  // --- NEW: Delete Line Mutation --- //
  const deleteLineMutation = useMutation<DeleteResponse, Error, { lineId: number }>({
      mutationFn: ({ lineId }) => api.deleteVoScriptLine(numericScriptId!, lineId),
      onMutate: (variables) => {
          setDeletingLineId(variables.lineId);
      },
      onSuccess: (response, variables) => {
           // Update cache by removing the line
           queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
              if (!oldData) return oldData;
              return {
                ...oldData,
                categories: oldData.categories?.map(cat => ({
                   ...cat,
                   // Filter out the deleted line
                   lines: cat.lines.filter(l => l.id !== variables.lineId)
                }))
              };
          });
          notifications.show({
              title: 'Line Deleted',
              message: response.message || `Line ${variables.lineId} deleted successfully.`,
              color: 'green',
          });
      },
      onError: (err, variables) => {
           notifications.show({
              title: 'Error Deleting Line',
              message: err.message || `Could not delete line ${variables.lineId}.`,
              color: 'red',
          });
      },
      onSettled: () => {
          setDeletingLineId(null);
      },
  });
  // --- END: Delete Line Mutation --- //

  // --- NEW: Toggle Lock Mutation --- //
  const toggleLockMutation = useMutation<{ id: number; is_locked: boolean; updated_at: string | null; }, Error, { lineId: number }>({
      mutationFn: ({ lineId }) => api.toggleLockVoScriptLine(numericScriptId!, lineId),
      onMutate: (variables) => {
          setTogglingLockLineId(variables.lineId);
      },
      onSuccess: (response, variables) => {
           // Update cache for the specific line
           queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
              if (!oldData) return oldData;
              // Response IS the data object now
              const updatedLineInfo = response; 
              return {
                ...oldData,
                categories: oldData.categories?.map(cat => ({
                   ...cat,
                   lines: cat.lines.map(l => 
                       l.id === updatedLineInfo.id 
                       ? { ...l, is_locked: updatedLineInfo.is_locked, updated_at: updatedLineInfo.updated_at } 
                       : l
                   )
                }))
              };
          });
          notifications.show({
              title: 'Lock Toggled',
              message: `Line ${variables.lineId} lock status updated.`,
              color: 'gray',
          });
      },
      onError: (err, variables) => {
          notifications.show({
              title: 'Error Toggling Lock',
              message: err.message || `Could not toggle lock for line ${variables.lineId}.`,
              color: 'red',
          });
      },
      onSettled: () => {
          setTogglingLockLineId(null);
      },
  });
  // --- END: Toggle Lock Mutation --- //

  // --- NEW: Add Line Mutation --- //
  const addLineMutation = useMutation<VoScriptLineData, Error, { payload: AddVoScriptLinePayload }>({
      mutationFn: ({ payload }) => api.addVoScriptLine(numericScriptId!, payload),
      onSuccess: (newLine) => {
          // Add the new line to the cache
          queryClient.setQueryData<VoScript>(['voScriptDetail', numericScriptId], (oldData) => {
              if (!oldData) return oldData;
              // Find the target category and add the line
              return {
                ...oldData,
                categories: oldData.categories?.map(cat => 
                    cat.id === newLine.category_id 
                    ? { ...cat, lines: [...cat.lines, newLine].sort((a,b) => (a.order_index ?? Infinity) - (b.order_index ?? Infinity)) } // Add and re-sort
                    : cat
                )
              };
          });
          notifications.show({
              title: 'Line Added',
              message: `New line '${newLine.line_key}' added successfully.`,
              color: 'green',
          });
          closeAddLineModal(); // Close modal on success
      },
      onError: (err, variables) => {
          notifications.show({
              title: 'Error Adding Line',
              message: err.message || `Could not add line '${variables.payload.line_key}'.`,
              color: 'red',
          });
      },
      // No need for onMutate/onSettled specific loading state for the modal itself,
      // the button's loading prop handles it.
  });
  // --- END: Add Line Mutation --- //

  // --- NEW: Accept Line Mutation --- //
  const acceptLineMutation = useMutation<VoScriptLineData, Error, { lineId: number }>({ 
      mutationFn: ({ lineId }) => api.acceptVoScriptLine(numericScriptId!, lineId),
      onSuccess: (updatedLine) => {
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
              title: 'Line Accepted',
              message: `Line ${updatedLine.id} status set to '${updatedLine.status}'.`,
              color: 'teal',
          });
      },
      onError: (err, variables) => {
          notifications.show({
              title: 'Error Accepting Line',
              message: err.message || `Could not accept line ${variables.lineId}.`,
              color: 'red',
          });
      },
       // Add onMutate/onSettled if specific loading state is desired for the accept button
       // onMutate: (variables) => { /* set loading state */ },
       // onSettled: () => { /* clear loading state */ },
  });

  // --- Helper Functions --- //

  // NEW: Helper to get color based on line status
  const getStatusColorForLine = (status: string): string => {
    switch (status?.toLowerCase()) {
        case 'generated': return 'blue';
        case 'review': return 'orange';
        case 'manual': return 'gray';
        case 'pending': return 'yellow';
        case 'failed': return 'red';
        default: return 'gray'; // Default color
    }
  };
  
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
  
  // REFACTORED: Generate Draft orchestrates on frontend
  const handleGenerateDraft = async () => { 
      if (numericScriptId === undefined || !voScript) return;

      console.log("Starting frontend draft generation orchestration...");
      setIsRefiningScript(true); // Re-use the global loading/progress state

      // 1. Identify pending lines
      const linesToProcess: VoScriptLineData[] = [];
      voScript.categories?.forEach(cat => {
          cat.lines.forEach(line => {
              // Target lines specifically in 'pending' status for initial generation
              if (line.status === 'pending') { 
                  linesToProcess.push(line);
              }
          });
      });

      if (linesToProcess.length === 0) {
          notifications.show({ message: 'No pending lines found to generate.', color: 'blue' });
          setIsRefiningScript(false); // Clear loading state
          return;
      }

      // 2. Initialize Progress State
      setRefinementProgress({
          total: linesToProcess.length,
          completed: 0,
          currentKey: null,
          errors: [],
          running: true 
      });

      // 3. Process lines sequentially
      const errorMessages: string[] = [];
      for (const line of linesToProcess) {
          setRefinementProgress(prev => ({ ...prev, currentKey: line.line_key || `ID: ${line.id}` }));
          
          try {
              // Call the NEW generate mutation for this line
              await generateLineMutation.mutateAsync({ lineId: line.id }); 
          } catch (error: any) { 
              console.error(`Error generating line ${line.id}:`, error);
              errorMessages.push(`Line ${line.line_key || line.id}: ${error.message || 'Unknown API error'}`); // Use API error if possible
          }
          
          // Update progress
           setRefinementProgress(prev => ({ 
                ...prev, 
                completed: prev.completed + 1, 
                currentKey: null, 
                errors: errorMessages 
            }));
      }

      // 4. Finalize
      setIsRefiningScript(false); 
      setRefinementProgress(prev => ({ ...prev, running: false, currentKey: null }));
      notifications.show({
          title: 'Draft Generation Complete',
          message: errorMessages.length > 0 
              ? `Finished with ${errorMessages.length} error(s). Check console/notifications for details.` 
              : `All ${linesToProcess.length} pending lines generated successfully.`,
          color: errorMessages.length > 0 ? 'orange' : 'green',
          autoClose: 6000
      });
  };

  // UPDATED: Opens Category Refine Modal
  const handleOpenCategoryRefineModal = (category: { id: number | null, name: string }) => {
    setCategoryToRefine(category);
    // MODIFIED: Always start with an empty prompt (transitory approach)
    setCategoryRefinePromptInput('');
    openCategoryRefineModal();
  };

  // UPDATED: Handles submission from Category Refine Modal
  const handleRefineCategory = async () => {
      // Validate: require either a prompt OR the checkbox to be checked
      if (!categoryToRefine || (!categoryRefinePromptInput.trim() && !applyRulesToCategory)) {
          notifications.show({ message: `Category refinement prompt cannot be empty unless "Apply ElevenLabs Best Practices" is checked.`, color: 'orange' });
          return;
      }
      if (numericScriptId === undefined) return; 
      
      console.log(`Triggering refinement mutation for category: ${categoryToRefine.name}`);
      refineCategoryMutation.mutate({
          categoryId: categoryToRefine.id,
          payload: { 
              category_name: categoryToRefine.name, 
              category_prompt: categoryRefinePromptInput, // Send prompt even if empty
              apply_best_practices: applyRulesToCategory // Send checkbox state
          }
      }, {
          onSuccess: () => closeCategoryRefineModal(), // Close modal on success
          onError: () => { /* Error already handled by mutation */ }
      });
  };

  // UPDATED: Opens Script Refine Modal (No longer pre-fills)
  const handleOpenScriptRefineModal = () => {
      setScriptRefinePromptInput(''); // Start with empty prompt
      openScriptRefineModal();
  };
  
  // UPDATED: Handles submission from Script Refine Modal
  const handleRefineScript = async () => {
      // Validate: require either a prompt OR the checkbox to be checked
      const globalPromptText = scriptRefinePromptInput;
      if ((!globalPromptText?.trim()) && !applyRulesToScript) {
          notifications.show({ message: `Overall script refinement prompt cannot be empty unless "Apply ElevenLabs Best Practices" is checked.`, color: 'orange' });
          return;
      }
      if (numericScriptId === undefined || !voScript) return;
      
      closeScriptRefineModal();
      
      // Use the mutation instead of direct API call
      refineScriptMutation.mutate({
          payload: {
              global_prompt: globalPromptText,
              apply_best_practices: applyRulesToScript
          }
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

  // NEW: Handler for inline text area changes
  const handleLineTextChange = (lineId: number, value: string) => {
      setEditedLineText(prev => ({ ...prev, [lineId]: value }));
  };
  
  // Helper function to check if a line has unsaved manual edits
  const isLineTextChanged = (line: VoScriptLineData): boolean => {
      return editedLineText[line.id] !== undefined && editedLineText[line.id] !== (line.generated_text || '');
  };

  // Handler for saving manual text edit
  const handleSaveLineText = (line: VoScriptLineData) => {
      const editedText = editedLineText[line.id];
      if (editedText === undefined || editedText === (line.generated_text || '')) {
          // No changes to save
          return; 
      }
      updateLineTextMutation.mutate({ lineId: line.id, newText: editedText });
  };

  // Handler for deleting a line
  const handleDeleteLine = (line: VoScriptLineData) => {
      if (window.confirm(`Are you sure you want to delete line '${line.line_key || line.id}'? This cannot be undone.`)) {
          deleteLineMutation.mutate({ lineId: line.id });
      }
  };

  // Handler to open the refine modal
  const handleOpenRefineModal = (line: VoScriptLineData) => {
      setLineToRefine(line);
      setRefineLinePromptInput(''); // Clear previous prompt
      openRefineModal();
  };

  // UPDATED: Handler to submit refinement from the line modal
  const handleSubmitRefineFromModal = () => {
      // Validate: require either a prompt OR the checkbox to be checked
      if (!lineToRefine || (!refineLinePromptInput.trim() && !applyRulesToLine)) {
           notifications.show({ message: `Refinement prompt cannot be empty unless 'Apply ElevenLabs Best Practices' is checked.`, color: 'orange'});
           return;
      }
      refineLineMutation.mutate(
          {
              lineId: lineToRefine.id,
              payload: { 
                  line_prompt: refineLinePromptInput, // Send prompt even if empty, backend handles it
                  apply_best_practices: applyRulesToLine // Send checkbox state
              } 
          },
          {
              onSuccess: () => {
                  closeRefineModal(); // Close modal on success
              }
          }
      );
  };

  // Handler for toggling lock
  const handleToggleLock = (lineId: number) => {
      toggleLockMutation.mutate({ lineId });
  };

  // Handler to open Add Line modal
  const handleOpenAddLineModal = (category: VoScriptCategoryData) => {
      setCategoryForNewLine(category);
      // Reset form fields when opening
      setNewLineKeyInput('');
      setNewLineTextInput('');
      setNewLineHintInput('');
      // Calculate default order index (last + 1?)
      const maxOrder = category.lines.reduce((max, line) => Math.max(max, line.order_index ?? -1), -1);
      setNewLineOrderInput(String(maxOrder + 1));
      
      openAddLineModal();
  };

  // Handler for submitting the new line
  const handleAddNewLineSubmit = () => {
      if (!categoryForNewLine?.name || !newLineKeyInput.trim() || newLineOrderInput.trim() === '') {
           notifications.show({ message: 'Line Key, Category, and Order Index are required.', color: 'orange'});
           return;
      }
      const orderIndexNum = parseInt(newLineOrderInput, 10);
      if (isNaN(orderIndexNum)) {
          notifications.show({ message: 'Order Index must be a valid number.', color: 'orange'});
           return;
      }
      
      const payload: AddVoScriptLinePayload = {
          line_key: newLineKeyInput.trim(),
          category_name: categoryForNewLine.name,
          order_index: orderIndexNum,
          initial_text: newLineTextInput.trim() || null, // Send null if empty
          prompt_hint: newLineHintInput.trim() || null
      };
      
      addLineMutation.mutate({ payload });
  };

  // NEW: Handler to open History Modal
  const handleOpenHistoryModal = (line: VoScriptLineData) => {
    setLineToViewHistory(line);
    openHistoryModal();
  };

  // NEW: Handlers for Expand/Collapse All
  const handleExpandAll = () => {
      const allCategoryNames = voScript?.categories?.map(c => c.name) || [];
      setOpenCategories(allCategoryNames);
  };

  const handleCollapseAll = () => {
      setOpenCategories([]);
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
  const isGenerating = false; // Basic check if agent is running
  const hasPending = voScript.categories?.some(cat => cat.lines.some(l => l.status === 'pending'));
  const hasFeedback = voScript.categories?.some(cat => cat.lines.some(l => !!l.latest_feedback));
  // Determine if any category refine is running for button states
  const refiningCategory = false;
  const refiningWhichCategory = refiningCategory ? 'N/A' : null;

  return (
    <Stack>
        {/* <Text>-- COMPONENT RENDER TEST --</Text> */}
        
        {/* UNCOMMENTING Progress and Header */}
        {/* <LoadingOverlay visible={isRefiningScript} overlayProps={{ radius: "sm", blur: 2 }} /> */}
        {refinementProgress.running && (
            <Paper withBorder p="sm" radius="sm" mb="md" bg="gray.0">
                <Text size="sm" fw={500}>Script Refinement Progress:</Text>
                <Progress 
                    value={(refinementProgress.completed / (refinementProgress.total || 1)) * 100}
                    mt={5} 
                    animated 
                    striped 
                />
                <Group justify="space-between" mt={5}>
                    <Text size="xs" c="dimmed">
                        {refinementProgress.currentKey 
                            ? `Processing: ${refinementProgress.currentKey}` 
                            : 'Preparing...'}
                    </Text>
                    <Text size="xs" c="dimmed">
                        {refinementProgress.completed} / {refinementProgress.total} lines completed
                    </Text>
                </Group>
                {refinementProgress.errors.length > 0 && (
                    <Alert title="Refinement Errors" color="orange" mt="sm" radius="xs" p="xs">
                        <Text size="xs">Encountered {refinementProgress.errors.length} error(s). See console/notifications for details.</Text>
                    </Alert>
                )}
            </Paper>
        )}
        <Group justify="space-between">
            <Stack gap="xs">
                <Title order={2}>{voScript.name}</Title>
                <Text c="dimmed">Template: {voScript.template_name || `ID ${voScript.template_id}`}</Text>
            </Stack>
            <Group>
                <Badge color={isGenerating ? "blue" : (hasPending ? "orange" : "green")} size="lg">
                    {isGenerating ? "Generating..." : (voScript.status || "Unknown")}
                </Badge>
                <Button 
                    leftSection={<IconPlayerPlay size={14} />} 
                    onClick={handleGenerateDraft}
                    disabled={isRefiningScript}
                    loading={isRefiningScript}
                    variant="gradient" gradient={{ from: 'blue', to: 'cyan' }}
                >
                    Generate Draft
                </Button>
                <Button 
                    leftSection={<IconSparkles size={14} />} 
                    onClick={handleOpenScriptRefineModal}
                    disabled={isRefiningScript}
                    loading={isRefiningScript}
                    variant="gradient" gradient={{ from: 'teal', to: 'lime' }}
                >
                    Refine Script
                </Button> 
                <Button size="xs" variant="outline" onClick={handleExpandAll} ml="lg">Expand All Categories</Button>
                <Button size="xs" variant="outline" onClick={handleCollapseAll}>Collapse All Categories</Button>
            </Group>
        </Group>
        
        {/* Display Character Description - NOW COLLAPSIBLE */}
        <Accordion> 
            <Accordion.Item value="character-description">
                <Accordion.Control>
                    <Title order={4}>Character Description</Title>
                 </Accordion.Control>
                 <Accordion.Panel>
                    <Paper withBorder p="md" mt="xs"> {/* Use mt=xs or remove if panel provides padding */} 
                        <Group justify="space-between" mb="xs">
                            {/* Removed Title from here as it's in Accordion.Control */}
                            {/* <Title order={4}>Character Description</Title> */}
                            {/* Use an empty span or fragment to push button right, or adjust Group props */}
                            <span /> {/* Keep button pushed right */} 
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
                            minRows={5} 
                            autosize
                            disabled={updateScriptPromptMutation.isPending || isRefiningScript}
                        />
                    </Paper>
                </Accordion.Panel>
            </Accordion.Item>
        </Accordion>

        {/* UNCOMMENTING Accordion */}
        <Accordion 
            multiple 
            value={openCategories} // Use state value
            onChange={setOpenCategories} // Use state setter
            // remove defaultValue={voScript?.categories?.map((c: VoScriptCategoryData) => c.name) || []}
        >
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
                                handleOpenCategoryRefineModal({ id: category.id, name: category.name });
                            }}
                            disabled={refineCategoryMutation.isPending && refiningCategoryId === category.id}
                            loading={refineCategoryMutation.isPending && refiningCategoryId === category.id}
                        >
                            Refine Category
                        </Button>
                    </Group>
                </Accordion.Control>
                <Accordion.Panel>
                    {/* Add Save Category button standalone */}
                    <Table striped highlightOnHover withTableBorder withColumnBorders mt="md">
                       <Table.Thead>
                            <Table.Tr>
                                <Table.Th style={{ width: '40px' }}>Lock</Table.Th>
                                <Table.Th style={{ width: '150px' }}>Line Key</Table.Th>
                                <Table.Th>Generated Text</Table.Th>
                                <Table.Th style={{ width: '120px' }}>Actions</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {category.lines.length === 0 ? (
                                <Table.Tr><Table.Td colSpan={4}><Text c="dimmed">No lines in this category.</Text></Table.Td></Table.Tr>
                            ) : (
                                category.lines.map((line) => {
                                    const hasUnsavedChanges = isLineTextChanged(line);
                                    const isBeingModified = (savingLineId === line.id || deletingLineId === line.id || refiningLineId === line.id || togglingLockLineId === line.id);
                                    return (
                                        <Table.Tr key={line.id} style={{ backgroundColor: line.is_locked ? 'var(--mantine-color-gray-1)' : undefined }}>
                                            <Table.Td ta="center">
                                                <Tooltip label={line.is_locked ? "Unlock Line" : "Lock Line (prevents AI edits)"}>
                                                    <ActionIcon 
                                                        size="sm" 
                                                        variant="subtle" 
                                                        title="Toggle Lock"
                                                        onClick={() => handleToggleLock(line.id)}
                                                        disabled={isBeingModified} 
                                                        loading={togglingLockLineId === line.id}
                                                    >
                                                        {line.is_locked ? <IconLock size={14}/> : <IconLockOpen size={14}/>}
                                                    </ActionIcon>
                                                </Tooltip>
                                            </Table.Td>
                                            <Table.Td>
                                                {/* Display Line Key and Status */}
                                                <Group wrap="nowrap" gap="xs">
                                                     <Text size="sm" fw={500}>{line.line_key || `(ID: ${line.id})`}</Text>
                                                     <Badge 
                                                        variant="light" 
                                                        size="xs" 
                                                        radius="sm"
                                                        color={getStatusColorForLine(line.status)}
                                                     >
                                                         {line.status}
                                                    </Badge>
                                                 </Group>
                                                {line.template_prompt_hint && <Text size="xs" c="dimmed" mt={2}>Hint: {line.template_prompt_hint}</Text>}
                                            </Table.Td>
                                            <Table.Td>
                                                <Textarea
                                                    value={editedLineText[line.id] ?? (line.generated_text || '')}
                                                    onChange={(event) => handleLineTextChange(line.id, event.currentTarget.value)}
                                                    placeholder="(No text generated)"
                                                    minRows={2}
                                                    autosize
                                                />
                                                {line.latest_feedback && (
                                                    <Alert title="Latest Feedback" color="yellow" variant="light" radius="xs" p="xs" mt="xs">
                                                        <Text size="sm">{line.latest_feedback}</Text>
                                                    </Alert>
                                                )}
                                            </Table.Td>
                                            <Table.Td>
                                                <Group gap="xs" wrap="nowrap">
                                                     {/* Add Accept Button Conditionally */} 
                                                     {line.status === 'review' && (
                                                        <Tooltip label="Accept Refined Text">
                                                            <ActionIcon 
                                                                size="sm" 
                                                                variant="filled"
                                                                color="teal" // Use a distinct color
                                                                onClick={() => acceptLineMutation.mutate({ lineId: line.id })}
                                                                disabled={isBeingModified} 
                                                                loading={acceptLineMutation.isPending && acceptLineMutation.variables?.lineId === line.id}
                                                            >
                                                                <IconCheck size={14} />
                                                            </ActionIcon>
                                                         </Tooltip>
                                                     )}
                                                     {/* Refine Button */}
                                                     <Tooltip label={line.is_locked ? "Line is locked" : "Refine Line"}>
                                                        <ActionIcon 
                                                            size="sm" 
                                                            variant="filled"
                                                            color="blue"
                                                            onClick={() => handleOpenRefineModal(line)} 
                                                            disabled={isBeingModified || line.is_locked}
                                                            loading={refineLineMutation.isPending && refiningLineId === line.id}
                                                        >
                                                            <IconSparkles size={14} />
                                                        </ActionIcon>
                                                     </Tooltip>
                                                     {/* Save Button */}
                                                     <Tooltip label="Save Manual Edit">
                                                        <ActionIcon 
                                                            size="sm" 
                                                            variant="filled"
                                                            color="green"
                                                            onClick={() => handleSaveLineText(line)}
                                                            disabled={!hasUnsavedChanges || isBeingModified}
                                                            loading={updateLineTextMutation.isPending && savingLineId === line.id}
                                                        >
                                                            <IconDeviceFloppy size={14} />
                                                        </ActionIcon>
                                                     </Tooltip>
                                                     {/* History Button */}
                                                     <Tooltip label="View History">
                                                        <ActionIcon 
                                                            size="sm" 
                                                            variant="subtle" 
                                                            color="gray"
                                                            onClick={() => handleOpenHistoryModal(line)}
                                                            disabled={isBeingModified}
                                                        >
                                                            <IconHistory size={14} />
                                                        </ActionIcon>
                                                     </Tooltip>
                                                     {/* Delete Button */}
                                                     <Tooltip label="Delete Line">
                                                        <ActionIcon 
                                                            size="sm" 
                                                            variant="filled"
                                                            color="red"
                                                            onClick={() => handleDeleteLine(line)}
                                                            disabled={isBeingModified}
                                                            loading={deleteLineMutation.isPending && deletingLineId === line.id}
                                                        >
                                                            <IconTrash size={14} />
                                                        </ActionIcon>
                                                     </Tooltip>
                                                </Group>
                                            </Table.Td>
                                        </Table.Tr>
                                    );
                                })
                            )}
                        </Table.Tbody>
                    </Table>
                    <Group justify="flex-start" mt="md">
                        <Button 
                            size="xs" 
                            variant="light"
                            leftSection={<IconPlus size={14} />}
                            onClick={() => handleOpenAddLineModal(category)}
                        >
                            Add New Line to {category.name}
                        </Button>
                    </Group>
                </Accordion.Panel>
            </Accordion.Item>
            ))}
            {(voScript.categories || []).length === 0 && (
                 <Text c="dimmed">No categories or lines found for this script.</Text>
            )}
        </Accordion>

        {/* --- Refine Line Modal --- */}
        <Modal 
            opened={refineModalOpened}
            onClose={closeRefineModal}
            title={`Refine Line: ${lineToRefine?.line_key || ''}`}
            centered
            size="lg"
            withinPortal={false}
        >
           <Stack>
                 <Text size="sm">Original Text:</Text>
                 <Paper withBorder p="xs" bg="gray.1">
                    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{lineToRefine?.generated_text || "(Empty)"}</Text>
                </Paper>
                <Textarea 
                    label="Refinement Prompt"
                    placeholder="Enter instructions to refine this line (e.g., 'make it sound more hesitant'). Leave blank to only apply best practices."
                    minRows={3}
                    autosize
                    value={refineLinePromptInput}
                    onChange={(e) => setRefineLinePromptInput(e.currentTarget.value)}
                    disabled={refineLineMutation.isPending && refiningLineId === lineToRefine?.id}
                />
                {/* NEW Checkbox */}
                <Checkbox
                    label="Apply ElevenLabs Best Practices (Pauses, Formatting, etc.)"
                    checked={applyRulesToLine}
                    onChange={(event) => setApplyRulesToLine(event.currentTarget.checked)}
                    disabled={refineLineMutation.isPending && refiningLineId === lineToRefine?.id}
                    mt="sm"
                />
                <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={closeRefineModal} disabled={refineLineMutation.isPending && refiningLineId === lineToRefine?.id}>
                        Cancel
                    </Button>
                    <Button 
                        onClick={handleSubmitRefineFromModal}
                        loading={refineLineMutation.isPending && refiningLineId === lineToRefine?.id}
                        disabled={!refineLinePromptInput.trim() && !applyRulesToLine} // Disable if both prompt and checkbox are empty/false
                    >
                        Submit Refinement
                    </Button>
                </Group> 
            </Stack>
        </Modal>
        {/* --- END: Refine Line Modal --- */}
        
        {/* Uncomment Add Line Modal */}
        
        <Modal // Add Line Modal
           opened={addLineModalOpened}
           onClose={closeAddLineModal}
           title={`Add New Line to Category: ${categoryForNewLine?.name || ''}`}
           centered
           size="lg"
           withinPortal={false} // Keep this prop
        >
           <Stack>
              <TextInput 
                  label="Line Key" 
                  placeholder="Unique key (e.g., TAUNT_CUSTOM_1)"
                  required
                  value={newLineKeyInput}
                  onChange={(e) => setNewLineKeyInput(e.currentTarget.value)}
              />
               <TextInput 
                  label="Order Index" 
                  type="number"
                  required
                  value={newLineOrderInput}
                  onChange={(e) => setNewLineOrderInput(e.currentTarget.value)}
              />
              <Textarea
                  label="Initial Line Text (Optional)"
                  placeholder="Enter the desired text for this line..."
                  minRows={3}
                  autosize
                  value={newLineTextInput}
                  onChange={(e) => setNewLineTextInput(e.currentTarget.value)}
              />
               <Textarea
                  label="Prompt Hint (Optional)"
                  placeholder="Enter any specific hints for AI generation/refinement..."
                  minRows={2}
                  autosize
                  value={newLineHintInput}
                  onChange={(e) => setNewLineHintInput(e.currentTarget.value)}
              />
              <Group justify="flex-end" mt="md">
                  <Button variant="default" onClick={closeAddLineModal} disabled={addLineMutation.isPending}>
                      Cancel
                  </Button>
                  <Button 
                      onClick={handleAddNewLineSubmit}
                      loading={addLineMutation.isPending} 
                      disabled={!newLineKeyInput.trim() || newLineOrderInput.trim() === '' || addLineMutation.isPending}
                  >
                      Add Line
                  </Button>
              </Group>
          </Stack>
        </Modal>
        
        {/* Uncomment History Modal */}
        
        <Modal // History Modal
           opened={historyModalOpened}
           onClose={closeHistoryModal}
           title={`History for Line: ${lineToViewHistory?.line_key || ''} (ID: ${lineToViewHistory?.id})`}
           centered
           size="xl"
           scrollAreaComponent={ScrollArea.Autosize}
           withinPortal={false} // Keep this prop
        >
            <Stack gap="xs">
                {/* Restore history mapping logic */}
                {(() => { // IIFE to allow console.log before map
                    const history = lineToViewHistory?.generation_history || [];
                    console.log('History Data in Modal:', history); // Log the history data
                    if (history.length === 0) {
                        return <Text c="dimmed">No generation history recorded for this line.</Text>;
                    }
                    return [...history].reverse().map((entry, index) => (
                        <Paper key={index} withBorder p="xs" radius="sm" bg={index === 0 ? "gray.0" : undefined}>
                            <Group justify="space-between">
                                <Stack gap={2}>
                                    <Text size="xs" c="dimmed">
                                        {new Date(entry.timestamp).toLocaleString()} 
                                        ({entry.type || 'unknown'} by {entry.model || 'unknown'})
                                    </Text>
                                    <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{entry.text}</Text>
                                </Stack>
                                {index > 0 && lineToViewHistory && ( 
                                    <Button 
                                        size="xs" 
                                        variant="outline"
                                        onClick={() => {
                                            // Directly trigger the update mutation with the historical text
                                            updateLineTextMutation.mutate({
                                                lineId: lineToViewHistory.id,
                                                newText: entry.text
                                            });
                                            closeHistoryModal(); // Close modal after initiating revert
                                        }}
                                        disabled={savingLineId === lineToViewHistory.id || deletingLineId === lineToViewHistory.id || refiningLineId === lineToViewHistory.id || togglingLockLineId === lineToViewHistory.id}
                                        // Add loading state specific to this revert action?
                                        // loading={updateLineTextMutation.isPending && savingLineId === lineToViewHistory.id} // Re-use saving state? 
                                    >
                                        Revert to this version
                                    </Button>
                                )}
                            </Group>
                        </Paper>
                    ));
                })()}
            </Stack>
            <Group justify="flex-end" mt="md">
                <Button variant="default" onClick={closeHistoryModal}>
                    Close
                </Button>
            </Group>
        </Modal>

        {/* --- NEW: Category Refine Modal --- */}
        <Modal
            opened={categoryRefineModalOpened}
            onClose={closeCategoryRefineModal}
            title={`Refine Category: ${categoryToRefine?.name || ''}`}
            centered
            size="lg"
            withinPortal={false}
        >
            <Stack>
                 <Textarea 
                    label="Category Refinement Prompt"
                    placeholder={`Enter instructions to refine all lines in the '${categoryToRefine?.name || ''}' category... Leave blank to only apply best practices.`}
                    minRows={4}
                    autosize
                    value={categoryRefinePromptInput}
                    onChange={(e) => setCategoryRefinePromptInput(e.currentTarget.value)}
                    disabled={refineCategoryMutation.isPending && refiningCategoryId === categoryToRefine?.id}
                 />
                 {/* NEW Checkbox */}
                 <Checkbox
                     label="Apply ElevenLabs Best Practices (Pauses, Formatting, etc.)"
                     checked={applyRulesToCategory}
                     onChange={(event) => setApplyRulesToCategory(event.currentTarget.checked)}
                     disabled={refineCategoryMutation.isPending && refiningCategoryId === categoryToRefine?.id}
                     mt="sm"
                 />
                 <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={closeCategoryRefineModal} disabled={refineCategoryMutation.isPending && refiningCategoryId === categoryToRefine?.id}>
                        Cancel
                    </Button>
                    <Button 
                        onClick={handleRefineCategory}
                        loading={refineCategoryMutation.isPending && refiningCategoryId === categoryToRefine?.id}
                        disabled={!categoryRefinePromptInput.trim() && !applyRulesToCategory} // Disable if both empty/false
                    >
                        Refine This Category
                    </Button>
                </Group>
            </Stack>
        </Modal>
        
        {/* --- NEW: Script Refine Modal --- */}
        <Modal
            opened={scriptRefineModalOpened}
            onClose={closeScriptRefineModal}
            title={`Refine Entire Script`}
            centered
            size="lg"
            withinPortal={false}
        >
             <Stack>
                 <Textarea 
                    label="Overall Script Refinement Prompt"
                    placeholder={`Enter instructions to refine the entire script... Leave blank to only apply best practices.`}
                    minRows={4}
                    autosize
                    value={scriptRefinePromptInput}
                    onChange={(e) => setScriptRefinePromptInput(e.currentTarget.value)}
                    disabled={isRefiningScript} // Disable if script refinement orchestration is running
                 />
                 {/* NEW Checkbox */}
                 <Checkbox
                     label="Apply ElevenLabs Best Practices (Pauses, Formatting, etc.)"
                     checked={applyRulesToScript}
                     onChange={(event) => setApplyRulesToScript(event.currentTarget.checked)}
                     disabled={isRefiningScript}
                     mt="sm"
                 />
                 <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={closeScriptRefineModal} disabled={isRefiningScript}>
                        Cancel
                    </Button>
                    <Button 
                        onClick={handleRefineScript} 
                        loading={isRefiningScript} 
                        disabled={!scriptRefinePromptInput.trim() && !applyRulesToScript} // Disable if both empty/false
                    >
                        Refine Entire Script
                    </Button>
                </Group>
            </Stack>
        </Modal>
    </Stack>
  );
};

export default VoScriptDetailView; 