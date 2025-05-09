import { Text, Stack, Textarea, Button, Group, ScrollArea, Paper, Loader, Alert, Card, ActionIcon, Box, Tooltip, Grid, Tabs, Modal, Code } from '@mantine/core';
import { IconSend, IconX, IconBulb, IconCheck, IconEdit, IconTrash, IconAlertCircle, IconClearAll, IconMessage, IconNotebook, IconPhoto } from '@tabler/icons-react';
import { useChatStore, ChatState, ChatMessage, getChatHistoryForContext } from '../../stores/chatStore';
import { ChatTaskResult, ProposedModificationDetail, ModificationType, VoScriptLineData, InitiateChatPayload, ChatHistoryItem, StagedCharacterDescriptionData, ScriptNoteData, VoScriptCategoryData, VoScript } from '../../types';
import { api } from '../../api';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import { ScratchpadModal } from './ScratchpadModal';
import { CodeHighlight } from '@mantine/code-highlight';

const POLLING_INTERVAL = 3000;
const MAX_POLLING_ATTEMPTS = 40; // Approx 2 minutes (40 attempts * 3 seconds/attempt)

// Define Props for the component
interface ChatPanelContentProps {
  // voScriptData prop is no longer needed here as the component will fetch its own
  // voScriptData: VoScript | null | undefined; 
}

export function ChatPanelContent(/* { voScriptData }: ChatPanelContentProps */) {
    const {
        isChatOpen, toggleChatOpen, chatDisplayHistory, currentMessage, setCurrentMessage,
        isLoading, setLoading, error, setError, currentFocus, currentAgentTaskID,
        setCurrentAgentTaskID, addMessageToHistory, activeProposals, setActiveProposals, removeProposal,
        setChatDisplayHistory,
        stagedDescriptionUpdate,
        setStagedDescriptionUpdate,
        clearStagedDescriptionUpdate,
        scratchpadNotes,
        setScratchpadNotes
    } = useChatStore((state: ChatState) => state);

    console.log("[ChatPanelContent] Rendering. Active proposals from store:", JSON.parse(JSON.stringify(activeProposals)));
    console.log("[ChatPanelContent] isLoading state:", isLoading);

    const queryClient = useQueryClient();
    const viewport = useRef<HTMLDivElement>(null);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // --- Fetch voScriptData for the current script in focus ---
    const numericScriptIdForQuery = currentFocus.scriptId ? parseInt(currentFocus.scriptId.toString(), 10) : undefined;
    const { 
        data: voScriptData, // This will now be the source of voScript data
        isLoading: isLoadingVoScript, 
        // error: voScriptError, // Optionally handle voScript fetch error
    } = useQuery<VoScript, Error>({
        queryKey: ['voScriptDetail', numericScriptIdForQuery],
        queryFn: () => api.getVoScript(numericScriptIdForQuery!),
        enabled: !!numericScriptIdForQuery,
        // staleTime: 1000 * 60 * 5, // Optional: 5 minutes
    });
    // --- End fetch voScriptData ---

    // NEW state for managing inline editing of proposals
    const [editingProposalId, setEditingProposalId] = useState<string | null>(null);
    const [editedProposalText, setEditedProposalText] = useState<string>('');
    const [editingProposals, setEditingProposals] = useState<Record<string, string>>({});
    const [isAcceptingAll, setIsAcceptingAll] = useState(false);

    // Add state for initial history loading
    const [isHistoryLoading, setIsHistoryLoading] = useState(false);
    const [historyError, setHistoryError] = useState<string | null>(null);

    // Get clearChat from store with explicit state typing
    const storeClearChat = useChatStore((state: ChatState) => state.clearChat);

    const [isCommittingDescription, setIsCommittingDescription] = useState(false);
    const [currentProgressMessage, setCurrentProgressMessage] = useState<string | null>(null);

    const [isScratchpadOpen, setIsScratchpadOpen] = useState(false);

    // NEW: State for selected image file and its preview URL
    const [selectedImageFile, setSelectedImageFile] = useState<File | null>(null);
    const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null); // Ref for hidden file input

    useEffect(() => {
        if (viewport.current) {
            // Delay scroll slightly to allow DOM to update with new elements like loaders
            const timer = setTimeout(() => {
                if (viewport.current) { // Check ref again in case component unmounted
                    viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' });
                }
            }, 0); // 0ms delay pushes to next event loop tick
            return () => clearTimeout(timer); // Cleanup timer on unmount or re-run
        }
    }, [chatDisplayHistory, activeProposals, isHistoryLoading, isLoading, currentMessage]);

    // --- Fetch Chat History on Mount/Script Change --- //
    useEffect(() => {
        if (currentFocus.scriptId) {
            console.log(`[ChatPanelContent] Script ID changed to ${currentFocus.scriptId}, fetching history...`);
            setIsHistoryLoading(true);
            setHistoryError(null);
            setChatDisplayHistory([]); 
            setActiveProposals([]);
            // voScriptData will be refetched by its own useQuery hook due to numericScriptIdForQuery change

            api.getChatHistory(currentFocus.scriptId)
                .then(history => {
                    console.log(`[ChatPanelContent] SUCCESSFULLY FETCHED ${history.length} history messages for script ${currentFocus.scriptId}.`);
                    const formattedHistory: ChatMessage[] = history.map(item => ({ 
                        role: item.role as 'user' | 'assistant',
                        content: item.content 
                    }));
                    setChatDisplayHistory(formattedHistory); // UNCOMMENTED
                })
                .catch(err => {
                    console.error("[ChatPanelContent] Failed to fetch chat history:", err);
                    setHistoryError(`Failed to load chat history: ${err.message}`);
                    setChatDisplayHistory([]); // Ensure history is empty on error
                })
                .finally(() => {
                    setIsHistoryLoading(false);
                });
        } else {
             console.log("[ChatPanelContent] No script ID in focus, clearing display states.");
             setChatDisplayHistory([]); 
             setActiveProposals([]);
             setIsHistoryLoading(false);
             setHistoryError(null);
        }
    }, [currentFocus.scriptId, setChatDisplayHistory, setActiveProposals]);

    const handleSendMessage = async () => {
        if ((!currentMessage.trim() && !selectedImageFile) || isLoading || isHistoryLoading || isLoadingVoScript || !currentFocus.scriptId) return;
        
        const userMessageText = currentMessage.trim();
        let imageBase64Data: string | null = null;
        let localImagePreviewForHistory: string | null = imagePreviewUrl; // Capture current preview for history

        if (selectedImageFile) {
            imageBase64Data = await new Promise<string | null>((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result as string);
                reader.onerror = () => resolve(null);
                reader.readAsDataURL(selectedImageFile);
            });
            if (!imageBase64Data) {
                notifications.show({ title: 'Image Error', message: 'Could not process image file.', color: 'red' });
                setLoading(false);
                return;
            }
        }

        const messageToSend = userMessageText || (imageBase64Data ? "[Image uploaded]" : "");
        if (!messageToSend && !localImagePreviewForHistory) return; // Ensure there's something to send/show

        // Add to history with image preview if available
        const userMessageForHistory: ChatMessage = { 
            role: 'user', 
            content: messageToSend || "", // Ensure content is always string
            imagePreviewUrl: localImagePreviewForHistory // Add preview URL to history item
        };
        addMessageToHistory(userMessageForHistory); 
        
        setCurrentMessage('');
        setSelectedImageFile(null);
        if (imagePreviewUrl) { // Keep this to revoke the current main preview
            URL.revokeObjectURL(imagePreviewUrl);
            setImagePreviewUrl(null);
        }

        setLoading(true);
        setError(null);
        setActiveProposals([]);
        setCurrentProgressMessage(null);

        try {
            const payload: InitiateChatPayload = {
                user_message: messageToSend || "", // Ensure content is always string for payload
                current_context: { category_id: currentFocus.categoryId, line_id: currentFocus.lineId },
                image_base64_data: imageBase64Data
            };
            const response = await api.initiateChatSession(currentFocus.scriptId!, payload);
            setCurrentAgentTaskID(response.task_id);
        } catch (err: any) {
            setError(err.message || 'Failed to send message.');
            setLoading(false);
            setCurrentProgressMessage(null);
        }
    };

    useEffect(() => {
        const stopPolling = () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
                console.log("[ChatPanelContent] Polling stopped."); // Log stop
            }
        };
        let attempts = 0; 
        let initialDelayTimer: NodeJS.Timeout | null = null;

        if (currentAgentTaskID) {
            const taskIdBeingPolled = currentAgentTaskID; 
            console.log(`[ChatPanelContent] New task ID detected: ${taskIdBeingPolled}. Setting up polling with initial delay.`);
            setLoading(true); // Set loading immediately
            setError(null); // Clear previous errors
            setActiveProposals([]); // Clear previous proposals

            // --- Add Initial Delay --- 
            initialDelayTimer = setTimeout(() => {
                console.log(`[ChatPanelContent] Initial delay finished for ${taskIdBeingPolled}. Starting interval polling.`);
                // Start the interval polling ONLY after the delay
                pollingIntervalRef.current = setInterval(async () => {
                    // Early exit if the task ID has changed or cleared 
                    if (useChatStore.getState().currentAgentTaskID !== taskIdBeingPolled || !taskIdBeingPolled) {
                        console.log(`[ChatPanelContent] Task ID mismatch or cleared (${useChatStore.getState().currentAgentTaskID} vs ${taskIdBeingPolled}). Stopping polling interval.`);
                        stopPolling(); 
                        return;
                    }
                    
                    attempts++; 

                    if (attempts > MAX_POLLING_ATTEMPTS) {
                         console.log(`[ChatPanelContent] Max polling attempts reached for ${taskIdBeingPolled}.`);
                        stopPolling();
                        setLoading(false);
                        const timeoutMessage = "The AI is taking longer than expected to respond. Please try sending your message again shortly.";
                        setError(timeoutMessage);
                        addMessageToHistory({role: 'assistant', content: timeoutMessage});
                        setCurrentAgentTaskID(null); 
                        return; 
                    }

                    try {
                        console.log(`[ChatPanelContent] Polling task: ${taskIdBeingPolled}, Attempt: ${attempts}`); 
                        const statusResponse = await api.getChatTaskStatus(taskIdBeingPolled);
                        console.log(`[ChatPanelContent] Poll response for ${taskIdBeingPolled}:`, statusResponse); // Log response
                        
                        // Re-check task ID after await 
                        if (useChatStore.getState().currentAgentTaskID !== taskIdBeingPolled) {
                            console.log(`[ChatPanelContent] Task ID changed during poll for ${taskIdBeingPolled}, aborting processing.`);
                            stopPolling();
                            return;
                        }
                        
                        // Process status ONLY if the status field exists
                        if (statusResponse && typeof statusResponse.status !== 'undefined') {
                            if (statusResponse.status === 'PROGRESS' && statusResponse.info && typeof statusResponse.info.status_message === 'string') {
                                console.log(`[ChatPanelContent] PROGRESS for task ${taskIdBeingPolled}: ${statusResponse.info.status_message}`);
                                setCurrentProgressMessage(statusResponse.info.status_message);
                                if (!isLoading) setLoading(true); // Ensure loading spinner stays if it somehow got turned off
                            } else if (statusResponse.status === 'SUCCESS' && statusResponse.info) {
                                console.log(`[ChatPanelContent] SUCCESS received for task ${taskIdBeingPolled}`); 
                                stopPolling();
                                setCurrentAgentTaskID(null); 
                                setLoading(false);
                                setCurrentProgressMessage(null); // Clear progress on final success

                                const successInfo = statusResponse.info as ChatTaskResult;
                                
                                console.log("[ChatPanelContent] Task SUCCESS. Raw successInfo:", JSON.parse(JSON.stringify(successInfo)));

                                const aiResponse: ChatMessage = {
                                    role: 'assistant',
                                    content: successInfo.ai_response_text || "(AI did not provide a text response)"
                                };
                                addMessageToHistory(aiResponse);

                                if (successInfo.proposed_modifications && successInfo.proposed_modifications.length > 0) {
                                    console.log("[ChatPanelContent] Received proposals to sort and set:", JSON.parse(JSON.stringify(successInfo.proposed_modifications)));
                                    const sortedProposals = [...successInfo.proposed_modifications].sort((a, b) => {
                                        const orderA = a.suggested_order_index ?? Infinity;
                                        const orderB = b.suggested_order_index ?? Infinity;

                                        if (orderA !== orderB) {
                                            return orderA - orderB;
                                        }

                                        const keyA = a.suggested_line_key || '';
                                        const keyB = b.suggested_line_key || '';
                                        return keyA.localeCompare(keyB);
                                    });
                                    setActiveProposals(sortedProposals);
                                } else {
                                    console.log("[ChatPanelContent] No proposals received, or array empty. Setting loading to false.");
                                    setActiveProposals([]);
                                }

                                // --- NEW: Handle staged description update --- 
                                if (successInfo.staged_description_update) {
                                    console.log("[ChatPanelContent] Received staged description update:", successInfo.staged_description_update);
                                    setStagedDescriptionUpdate(successInfo.staged_description_update);
                                } else {
                                    // If no new staged update, clear any existing one (e.g., if it was committed/dismissed by another means)
                                    // Or, only clear if there were proposals/other actions, to avoid clearing if agent is just talking.
                                    // For now, let's be simple: if the response *doesn't* have a new staged update, don't clear an existing one.
                                    // The commit/dismiss actions below will handle clearing.
                                }
                            } else if (statusResponse.status === 'FAILURE') {
                                console.log(`[ChatPanelContent] FAILURE received for task ${taskIdBeingPolled}`); 
                                stopPolling(); 
                                setLoading(false); 
                                setCurrentAgentTaskID(null);
                                setCurrentProgressMessage(null); // Clear progress on final failure
                                const errorInfo = statusResponse.info as { error?: string; message?: string; };
                                const errorMessage = errorInfo?.error || errorInfo?.message || 'Task failed.';
                                setError(errorMessage);
                                addMessageToHistory({role: 'assistant', content: `Sorry, I encountered an error: ${errorMessage}`});
                            } else if (statusResponse.status === 'PENDING' || statusResponse.status === 'STARTED'){
                                console.log(`Task ${taskIdBeingPolled} is ${statusResponse.status}`);
                                if (!useChatStore.getState().isLoading) setLoading(true);
                            } else {
                                console.warn(`[ChatPanelContent] Unexpected task status for ${taskIdBeingPolled}:`, statusResponse.status);
                            }
                        } else {
                             console.error(`[ChatPanelContent] Received invalid status response for ${taskIdBeingPolled}:`, statusResponse);
                             // Optionally stop polling on invalid response or just log and continue?
                             // stopPolling();
                             // setLoading(false);
                             // setError("Received an invalid status response from the server.");
                             // setCurrentAgentTaskID(null);
                        }
                    } catch (err: any) {
                        console.error(`[ChatPanelContent] Error polling task ${taskIdBeingPolled}:`, err); // Add logging
                        // --- Re-check task ID after await/error --- 
                        if (useChatStore.getState().currentAgentTaskID !== taskIdBeingPolled) {
                             console.log(`[ChatPanelContent] Task ID changed during error handling for ${taskIdBeingPolled}, aborting state update.`);
                             stopPolling(); // Stop this interval
                             return;
                        }
                        // --- End Re-check --- 
                        stopPolling(); 
                        setLoading(false); 
                        setCurrentAgentTaskID(null);
                        setError(err.message || 'Failed to get task update.');
                        setCurrentProgressMessage(null); // Clear on error
                    }
                }, POLLING_INTERVAL);
            }, 500); // Start polling after 500ms delay
        }
        
        // Cleanup function
        return () => {
            console.log("[ChatPanelContent] Cleanup polling useEffect.");
            if (initialDelayTimer) clearTimeout(initialDelayTimer);
            stopPolling(); // Ensure interval is cleared on unmount or dependency change
            setCurrentProgressMessage(null); // Clear progress on component unmount / task ID change
        };
    }, [currentAgentTaskID, addMessageToHistory, setLoading, setError, setCurrentAgentTaskID, setActiveProposals, setStagedDescriptionUpdate, setCurrentProgressMessage]);

    const prevScriptIdRef = useRef<number | null>(null);
    useEffect(() => {
        if (isChatOpen && currentFocus.scriptId !== prevScriptIdRef.current) {
            if (prevScriptIdRef.current !== null && prevScriptIdRef.current !== undefined) { 
                 useChatStore.getState().clearChat(); 
                 useChatStore.getState().clearActiveProposals();
            }
        }
        prevScriptIdRef.current = currentFocus.scriptId;
    }, [isChatOpen, currentFocus.scriptId]);

    const updateLineTextMutation = useMutation<
        VoScriptLineData,
        Error, 
        { lineId: number; newText: string }
    >({
        mutationFn: ({ lineId, newText }) => 
            api.updateLineText(currentFocus.scriptId!, lineId, newText),
        onSuccess: (updatedLine) => {
            queryClient.invalidateQueries({ queryKey: ['voScriptDetail', currentFocus.scriptId] });
            notifications.show({
                title: 'Line Updated (Test)',
                message: `Line ${updatedLine.id} text updated successfully via chat proposal.`,
                color: 'green',
                autoClose: 7000
            });
            console.log("Notification for line update should have been shown.");
        },
        onError: (error, variables) => {
            notifications.show({ title: 'Error Updating Line', message: error.message || `Could not update line ${variables.lineId}.`, color: 'red' });
        },
    });

    const addLineMutation = useMutation<
        VoScriptLineData,
        Error,
        { 
            scriptId: number; 
            payload: {
                line_key: string;
                category_name: string;
                order_index: number;
                initial_text?: string | null;
                prompt_hint?: string | null;
            } 
        }
    >({
        mutationFn: ({ scriptId, payload }) => api.addVoScriptLine(scriptId, payload),
        onSuccess: (newLine) => {
            queryClient.invalidateQueries({ queryKey: ['voScriptDetail', currentFocus.scriptId] });
            notifications.show({
                title: 'Line Added',
                message: `Line '${newLine.line_key}' added successfully.`,
                color: 'green'
            });
        },
        onError: (error) => {
            notifications.show({ title: 'Error Adding Line', message: error.message, color: 'red' });
        },
    });

    const handleAcceptProposal = async (proposal: ProposedModificationDetail) => {
        if (!currentFocus.scriptId || !voScriptData) {
            notifications.show({ title: 'Error', message: 'Cannot accept proposal: Script data not loaded.', color: 'red' });
            return;
        }

        if (proposal.modification_type === ModificationType.REPLACE_LINE && proposal.new_text != null) {
            setLoading(true);
            try { 
                await updateLineTextMutation.mutateAsync({ lineId: proposal.target_id, newText: proposal.new_text }); 
                removeProposal(proposal.proposal_id); 
            } catch (e) { /* error handled by mutation */ } 
            finally { setLoading(false); }
        }
        else if (proposal.modification_type === ModificationType.NEW_LINE_IN_CATEGORY && proposal.new_text && proposal.suggested_line_key) {
            setLoading(true);
            try {
                const category = voScriptData?.categories?.find((cat: VoScriptCategoryData) => cat.id === proposal.target_id);
                if (!category || !category.lines) {
                    throw new Error(`Could not find category details or lines for ID ${proposal.target_id} to add line.`);
                }
                const maxOrderIndex = category.lines.reduce((max: number, line: VoScriptLineData) => Math.max(max, line.order_index ?? -1), -1);
                const newOrderIndex = maxOrderIndex + 1;
                
                const payload = {
                    line_key: proposal.suggested_line_key,
                    category_name: category.name,
                    order_index: proposal.suggested_order_index ?? newOrderIndex,
                    initial_text: proposal.new_text,
                    prompt_hint: null
                };

                await addLineMutation.mutateAsync({ scriptId: currentFocus.scriptId, payload });
                removeProposal(proposal.proposal_id);
            } catch (err: any) {
                setError(err.message || 'Failed to add new line.');
                notifications.show({ title: 'Error Adding Line', message: err.message || 'Could not add line based on proposal.', color: 'red' });
            } finally {
                setLoading(false);
            }
        }
        else {
            notifications.show({ title: 'Action Error', message: 'Cannot accept this proposal type yet or missing required data.', color: 'orange' });
        }
    };

    const handleEditProposal = (proposal: ProposedModificationDetail) => {
        console.log("Editing proposal:", proposal.proposal_id);
        notifications.show({ title: 'Edit Proposal (Not Implemented)', message: `Editing ${proposal.proposal_id}`, color: 'yellow' });
    };
    const handleDismissProposal = (proposalId: string) => {
        removeProposal(proposalId);
        notifications.show({ title: 'Proposal Dismissed', message: `Dismissed ${proposalId}`, color: 'gray' });
    };

    const handleStartEditProposal = (proposal: ProposedModificationDetail) => {
        setEditingProposalId(proposal.proposal_id);
        setEditedProposalText(proposal.new_text || '');
    };

    const handleCancelEditProposal = () => {
        setEditingProposalId(null);
        setEditedProposalText('');
    };

    const handleSaveEditedProposal = () => {
        if (!editingProposalId || !currentFocus.scriptId) return;
        
        const originalProposal = activeProposals.find((p: ProposedModificationDetail) => p.proposal_id === editingProposalId);
        if (!originalProposal) {
            notifications.show({ title: 'Error', message: 'Original proposal not found to save edit.', color: 'red' });
            handleCancelEditProposal();
            return;
        }

        // Create a new proposal object with the edited text
        const modifiedProposal: ProposedModificationDetail = {
            ...originalProposal,
            new_text: editedProposalText
        };

        handleAcceptProposal(modifiedProposal); // Reuse the accept logic
        handleCancelEditProposal(); // Clear editing state
    };

    const handleCloseChat = () => {
        console.log('[ChatPanelContent] Before toggleChatOpen, isChatOpen from store:', useChatStore.getState().isChatOpen);
        toggleChatOpen();
        // Zustand updates are synchronous, but React render might be batched.
        // Let's log the state directly after the call for immediate feedback.
        console.log('[ChatPanelContent] After toggleChatOpen called, current isChatOpen in component scope:', isChatOpen); 
        // The component scope 'isChatOpen' will update on next render. getState() is immediate.
        setTimeout(() => {
             console.log('[ChatPanelContent] State from store after toggle (async check):', useChatStore.getState().isChatOpen);
        }, 0);
    };

    const handleAcceptAllProposals = async () => {
        if (activeProposals.length === 0) {
            notifications.show({
                title: 'No Proposals',
                message: 'There are no active proposals to accept.',
                color: 'yellow',
            });
            return;
        }

        setIsAcceptingAll(true);
        let acceptedCount = 0;
        let failedCount = 0;

        notifications.show({
            id: 'accept-all-process',
            title: 'Accepting All Proposals',
            message: `Starting to process ${activeProposals.length} proposals...`,
            loading: true,
            autoClose: false,
        });

        for (const currentProposal of activeProposals) {
            // If this proposal was being edited, use the edited text.
            // Otherwise, use its original new_text.
            const textForThisProposal = editingProposals[currentProposal.proposal_id] ?? currentProposal.new_text;
            
            // Construct the proposal object to be accepted, ensuring it has the correct text.
            const proposalToAccept: ProposedModificationDetail = {
                ...currentProposal,
                new_text: textForThisProposal,
            };

            try {
                await handleAcceptProposal(proposalToAccept); // Pass the correct proposal object
                acceptedCount++;
            } catch (e) {
                failedCount++;
                console.error(`Error accepting proposal ${currentProposal.proposal_id} during Accept All:`, e);
                // Individual failure notification is expected from handleAcceptProposal itself.
            }
        }

        // Clear any editing state that might have been active for proposals now processed
        setEditingProposals({});

        setIsAcceptingAll(false);
        notifications.update({
            id: 'accept-all-process',
            title: 'Accept All Complete',
            message: `Processed ${activeProposals.length} proposals. Accepted: ${acceptedCount}, Failed: ${failedCount}.`,
            color: failedCount > 0 ? (acceptedCount > 0 ? 'orange' : 'red') : 'green',
            loading: false,
            autoClose: 5000,
        });
    };

    const handleClearHistory = async () => {
        if (!currentFocus.scriptId) {
            notifications.show({
                title: 'Cannot Clear History',
                message: 'No active script selected.',
                color: 'orange'
            });
            return;
        }
        // Optional: Add a confirmation dialog here (e.g., using Mantine Modals service)
        // For now, direct clear.
        console.log(`[ChatPanelContent] Clearing history for script ID: ${currentFocus.scriptId}`);
        setLoading(true); // Use general loading state or a specific one for this action
        try {
            await api.clearChatHistory(currentFocus.scriptId);
            storeClearChat(); // Clears display history in Zustand store
            setActiveProposals([]); // Also clear any active proposals
            notifications.show({
                title: 'Chat History Cleared',
                message: `History for the current script has been cleared.`, 
                color: 'green'
            });
        } catch (err: any) {
            console.error("[ChatPanelContent] Failed to clear chat history:", err);
            notifications.show({
                title: 'Error Clearing History',
                message: err.message || 'Could not clear chat history.',
                color: 'red'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleCommitDescription = async () => {
        if (!stagedDescriptionUpdate || !currentFocus.scriptId) return;
        setIsCommittingDescription(true);
        try {
            await api.commitCharacterDescription(currentFocus.scriptId, stagedDescriptionUpdate.new_description);
            notifications.show({
                title: 'Character Description Updated',
                message: 'The character description has been successfully updated.',
                color: 'green'
            });
            queryClient.invalidateQueries({ queryKey: ['voScriptDetail', currentFocus.scriptId] });
            clearStagedDescriptionUpdate(); // Clear from store
            addMessageToHistory({ role: 'assistant', content: "Okay, I've updated the character description in the script!" });
        } catch (err: any) {
            notifications.show({
                title: 'Update Failed',
                message: err.message || 'Could not update character description.',
                color: 'red'
            });
        } finally {
            setIsCommittingDescription(false);
        }
    };

    const handleDismissStagedDescription = () => {
        clearStagedDescriptionUpdate();
        notifications.show({
            title: 'Update Dismissed',
            message: 'The proposed character description update has been dismissed.',
            color: 'gray'
        });
        addMessageToHistory({ role: 'assistant', content: "Alright, I'll discard that description update." });
    };

    // Add final check log before returning JSX
    console.log(`[ChatPanelContent] FINAL RENDER CHECK - isLoading: ${isLoading}, isHistoryLoading: ${isHistoryLoading}, historyError: ${historyError}`);

    return (
        <Stack h="100%" justify="space-between" gap="xs">
            <Group justify="space-between" p="xs" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
                <Text fw={500}>AI Script Collaborator</Text>
                <Group gap="xs">
                    <Tooltip label="View Scratchpad">
                        <ActionIcon onClick={() => setIsScratchpadOpen(true)} variant="subtle" size="sm" color="blue" disabled={isLoading || isHistoryLoading}>
                            <IconNotebook />
                        </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Clear Chat History">
                        <ActionIcon onClick={handleClearHistory} variant="subtle" size="sm" color="red" disabled={isLoading || isHistoryLoading}>
                            <IconClearAll />
                        </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Close Chat">
                        <ActionIcon onClick={handleCloseChat} variant="subtle" size="sm">
                            <IconX />
                        </ActionIcon>
                    </Tooltip>
                </Group>
            </Group>
            
            <ScrollArea style={{ flex: 1 }} viewportRef={viewport} p="xs">
                {isHistoryLoading && <Group justify="center" mt="xl"><Loader size="sm" /> <Text size="sm" c="dimmed" ml="xs">Loading history...</Text></Group>}
                {historyError && <Alert color="orange" title="History Error" icon={<IconAlertCircle />}>{historyError}</Alert>}
                
                {!isHistoryLoading && !historyError && chatDisplayHistory.length === 0 && 
                    <Text c="dimmed" ta="center" mt="xl">Start conversation...</Text>
                }
                {!isHistoryLoading && !historyError && chatDisplayHistory.map((msg: ChatMessage, index: number) => (
                    <Paper key={index} shadow={msg.role === 'user' ? "xs" : "sm"} p="sm" mb="xs" radius="md" withBorder bg={msg.role === 'user' ? 'blue.0' : 'gray.0'}
                        style={{ marginLeft: msg.role === 'user' ? 'auto' : undefined, marginRight: msg.role === 'assistant' ? 'auto' : undefined, maxWidth: '80%',
                            borderBottomLeftRadius: msg.role === 'user' ? 'md' : 'sm', borderBottomRightRadius: msg.role === 'assistant' ? 'md' : 'sm' }}>
                       {msg.content && <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</Text>}
                       {/* NEW: Render image preview from history if available */}
                       {msg.role === 'user' && msg.imagePreviewUrl && (
                           <Box mt={msg.content ? "xs" : undefined} mb="xs">
                               <img src={msg.imagePreviewUrl} alt="Uploaded content" style={{ display: 'block', maxWidth: '200px', maxHeight: '200px', borderRadius: 'var(--mantine-radius-sm)' }} />
                           </Box>
                       )}
                        <Text size="xs" c="dimmed" ta={msg.role === 'user' ? 'right' : 'left'} mt={3}>
                            {msg.role === 'user' ? 'You' : 'AI Assistant'}
                        </Text>
                    </Paper>
                ))}
                {isLoading && !isHistoryLoading && !activeProposals.length && (
                    <Group justify="center" mt="md">
                        <Loader size="sm" />
                        {currentProgressMessage && <Text size="xs" c="dimmed" ml="xs">{currentProgressMessage}</Text>}
                    </Group>
                )}

                {stagedDescriptionUpdate && (
                    <Card withBorder p="sm" mt="sm" radius="md" shadow="sm">
                        <Text fw={500} mb="xs">Proposed Character Description Update:</Text>
                        <Textarea 
                            value={stagedDescriptionUpdate.new_description} 
                            readOnly 
                            minRows={3} 
                            autosize 
                            mb="xs"
                        />
                        {stagedDescriptionUpdate.reasoning && (
                            <Text size="xs" c="dimmed" mb="xs">Reasoning: {stagedDescriptionUpdate.reasoning}</Text>
                        )}
                        <Group justify="flex-end">
                            <Button variant="default" onClick={handleDismissStagedDescription} disabled={isCommittingDescription}>
                                Dismiss
                            </Button>
                            <Button onClick={handleCommitDescription} loading={isCommittingDescription} color="teal">
                                Commit Description
                            </Button>
                        </Group>
                    </Card>
                )}
            </ScrollArea>

            {activeProposals.length > 0 && (
                <Paper withBorder p="xs" radius="sm" mt="xs" shadow="sm" style={{maxHeight: '40%', overflowY: 'auto', flexShrink: 0}}>
                    <Group justify="flex-end" mb="xs">
                        <Button 
                            size="xs" 
                            variant="light" 
                            color="teal" 
                            onClick={handleAcceptAllProposals} 
                            loading={isAcceptingAll} 
                            disabled={isLoading || isHistoryLoading || isLoadingVoScript || isAcceptingAll}
                        >
                            Accept All Proposals
                        </Button>
                    </Group>

                    {activeProposals.map((proposal: ProposedModificationDetail) => {
                        // --- Determine the relevant line key to display --- 
                        let displayLineKey = '(Unknown Line Key)';
                        let displayActionText = 'Proposal';

                        if (proposal.modification_type === ModificationType.REPLACE_LINE) {
                            displayActionText = 'Replace Line:';
                            const originalLine = voScriptData?.categories?.flatMap(cat => cat.lines).find(line => line.id === proposal.target_id);
                            displayLineKey = originalLine?.line_key || `(Line ID: ${proposal.target_id})`;
                        } else if (proposal.modification_type === ModificationType.NEW_LINE_IN_CATEGORY) {
                            displayActionText = 'Add New Line:';
                            displayLineKey = proposal.suggested_line_key || '(Suggests New Key)';
                        } else if (proposal.modification_type === ModificationType.INSERT_LINE_AFTER) {
                            displayActionText = 'Insert After:';
                            const targetLine = voScriptData?.categories?.flatMap(cat => cat.lines).find(line => line.id === proposal.target_id);
                            displayLineKey = `${targetLine?.line_key || `(Line ID: ${proposal.target_id})`} (Suggests: ${proposal.suggested_line_key || 'New Key'})`;
                        } else if (proposal.modification_type === ModificationType.INSERT_LINE_BEFORE) {
                            displayActionText = 'Insert Before:';
                            const targetLine = voScriptData?.categories?.flatMap(cat => cat.lines).find(line => line.id === proposal.target_id);
                            displayLineKey = `${targetLine?.line_key || `(Line ID: ${proposal.target_id})`} (Suggests: ${proposal.suggested_line_key || 'New Key'})`;
                        }
                        // --- End determine line key --- 
                        
                        return (
                            <Paper key={proposal.proposal_id} withBorder p="sm" radius="sm" shadow="xs" mb="xs">
                                {/* Display Action and Line Key */}
                                <Group justify="space-between" mb={3}>
                                    <Text size="xs" fw={500}>{displayActionText}</Text>
                                    <Code style={{fontSize: 'var(--mantine-font-size-xs)'}}>{displayLineKey}</Code>
                                </Group>
                                {/* Display Proposed Text */}
                                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{proposal.new_text}</Text>
                                {proposal.reasoning && (
                                    <Text size="xs" c="dimmed" mt={5}>Reasoning: {proposal.reasoning}</Text>
                                )}
                                <Group justify="flex-end" mt="xs">
                                    <Button variant="subtle" size="xs" onClick={() => handleAcceptProposal(proposal)} disabled={isLoadingVoScript || isLoading || isAcceptingAll}>Accept</Button> 
                                    {proposal.modification_type === ModificationType.REPLACE_LINE && (
                                        <Button variant="subtle" size="xs" onClick={() => handleStartEditProposal(proposal)} disabled={isAcceptingAll}>Edit</Button>
                                    )}
                                    <Button variant="subtle" size="xs" onClick={() => handleDismissProposal(proposal.proposal_id)} disabled={isAcceptingAll}>Dismiss</Button>
                                </Group>
                            </Paper>
                        );
                    })}
                </Paper>
            )}
            
            {error && (
                <Alert variant="light" color="red" title="Chat Error" icon={<IconX />} withCloseButton onClose={() => setError(null)} mb="sm" p="xs" >
                    <Text size="xs">{error}</Text>
                </Alert>
            )}

            <Group wrap="nowrap" gap="xs" style={{padding: 'var(--mantine-spacing-xs)', borderTop: '1px solid var(--mantine-color-gray-3)'}}>
                {/* Hidden file input */}
                <input 
                    type="file" 
                    accept="image/*" 
                    style={{ display: 'none' }} 
                    ref={fileInputRef} 
                    onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                            setSelectedImageFile(file);
                            // Create object URL for preview
                            if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl); // Revoke old one
                            setImagePreviewUrl(URL.createObjectURL(file));
                        }
                        event.target.value = '' // Reset input to allow same file selection again
                    }}
                />
                {/* Image Attach Button */}
                <Tooltip label="Attach Image">
                    <ActionIcon 
                        onClick={() => fileInputRef.current?.click()} 
                        variant="subtle" 
                        disabled={isLoading || isHistoryLoading || isLoadingVoScript}
                    >
                        <IconPhoto size={18} />
                    </ActionIcon>
                </Tooltip>
                
                <Textarea 
                    placeholder="Type your message..." 
                    value={currentMessage} 
                    onChange={(event) => setCurrentMessage(event.currentTarget.value)}
                    style={{ flexGrow: 1 }} 
                    minRows={1} 
                    maxRows={4} 
                    autosize 
                    disabled={isLoading || isHistoryLoading || isLoadingVoScript}
                    onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSendMessage(); }}}
                />
                <Button 
                    onClick={handleSendMessage} 
                    disabled={!currentMessage.trim() || isLoading || isHistoryLoading || isLoadingVoScript}
                    loading={isLoading} 
                    variant="filled">
                    <IconSend size={18} />
                </Button>
            </Group>
            
            {imagePreviewUrl && (
                <Paper withBorder p="xs" radius="sm" mt="xs" shadow="xs" style={{maxWidth: '50%', alignSelf: 'flex-end'}}>
                    <img src={imagePreviewUrl} alt="Selected preview" style={{ display: 'block', maxWidth: '100px', maxHeight: '100px', borderRadius: 'var(--mantine-radius-sm)' }} />
                    <Text size="xs" c="dimmed" ta="right" mt={3}>Attached Image</Text>
                </Paper>
            )}
            
            <ScratchpadModal 
                opened={isScratchpadOpen} 
                onClose={() => setIsScratchpadOpen(false)} 
                scriptId={currentFocus.scriptId}
            />
        </Stack>
    );
} 