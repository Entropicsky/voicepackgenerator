import { Text, Stack, Textarea, Button, Group, ScrollArea, Paper, Loader, Alert, Card, ActionIcon, Box, Tooltip, Grid } from '@mantine/core';
import { IconSend, IconX, IconBulb, IconCheck, IconEdit, IconTrash } from '@tabler/icons-react';
import { useChatStore, ChatState, ChatMessage, getChatHistoryForContext } from '../../stores/chatStore';
import { ChatTaskResult, ProposedModificationDetail, ModificationType, VoScriptLineData } from '../../types';
import { api } from '../../api';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';

const POLLING_INTERVAL = 3000;
const MAX_POLLING_ATTEMPTS = 20; // Approx 1 minute (20 attempts * 3 seconds/attempt)

export function ChatPanelContent() {
    const {
        isChatOpen, toggleChatOpen, chatDisplayHistory, currentMessage, setCurrentMessage,
        isLoading, setLoading, error, setError, currentFocus, currentAgentTaskID,
        setCurrentAgentTaskID, addMessageToHistory, activeProposals, setActiveProposals, removeProposal
    } = useChatStore((state: ChatState) => state);

    console.log("[ChatPanelContent] Rendering. Active proposals from store:", JSON.parse(JSON.stringify(activeProposals)));
    console.log("[ChatPanelContent] isLoading state:", isLoading);

    const queryClient = useQueryClient();
    const viewport = useRef<HTMLDivElement>(null);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // NEW state for managing inline editing of proposals
    const [editingProposalId, setEditingProposalId] = useState<string | null>(null);
    const [editedProposalText, setEditedProposalText] = useState<string>('');
    const [editingProposals, setEditingProposals] = useState<Record<string, string>>({});
    const [isAcceptingAll, setIsAcceptingAll] = useState(false);

    useEffect(() => {
        if (viewport.current) {
            viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' });
        }
    }, [chatDisplayHistory, activeProposals]);

    const handleSendMessage = async () => {
        if (!currentMessage.trim() || isLoading || !currentFocus.scriptId) return;
        const userMessage: ChatMessage = { role: 'user', content: currentMessage.trim() };
        addMessageToHistory(userMessage);
        const messageForApi = currentMessage.trim();
        setCurrentMessage('');
        setLoading(true);
        setError(null);
        setActiveProposals([]);
        try {
            const recentHistory = getChatHistoryForContext(chatDisplayHistory, 6);
            const payload = {
                user_message: messageForApi,
                initial_prompt_context_from_prior_sessions: recentHistory,
                current_context: { category_id: currentFocus.categoryId, line_id: currentFocus.lineId }
            };
            const response = await api.initiateChatSession(currentFocus.scriptId, payload);
            setCurrentAgentTaskID(response.task_id);
        } catch (err: any) {
            setError(err.message || 'Failed to send message.');
            setLoading(false);
        }
    };

    useEffect(() => {
        const stopPolling = () => {
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
                pollingIntervalRef.current = null;
            }
        };
        let attempts = 0; // Initialize attempt counter

        if (currentAgentTaskID) {
            setLoading(true);
            pollingIntervalRef.current = setInterval(async () => {
                attempts++; // Increment on each polling execution

                if (attempts > MAX_POLLING_ATTEMPTS) {
                    stopPolling();
                    setLoading(false);
                    const timeoutMessage = "The AI is taking longer than expected to respond. Please try sending your message again shortly.";
                    setError(timeoutMessage);
                    // Add a message to chat history to inform the user in the chat UI
                    addMessageToHistory({role: 'assistant', content: timeoutMessage});
                    setCurrentAgentTaskID(null); // Clear the task ID as we've timed out on it
                    return; // Stop further execution in this interval
                }

                try {
                    const statusResponse = await api.getChatTaskStatus(currentAgentTaskID);
                    if (statusResponse.status === 'SUCCESS' && statusResponse.info) {
                        stopPolling();
                        setCurrentAgentTaskID(null);
                        setLoading(false);

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
                    } else if (statusResponse.status === 'FAILURE') {
                        stopPolling(); setLoading(false); setCurrentAgentTaskID(null);
                        const errorInfo = statusResponse.info as { error?: string; message?: string; };
                        const errorMessage = errorInfo?.error || errorInfo?.message || 'Task failed.';
                        setError(errorMessage);
                        addMessageToHistory({role: 'assistant', content: `Sorry, I encountered an error: ${errorMessage}`});
                    } else if (statusResponse.status === 'PENDING' || statusResponse.status === 'STARTED'){
                        console.log(`Task ${currentAgentTaskID} is ${statusResponse.status}`);
                    } else {
                         console.warn("Unexpected task status:", statusResponse.status);
                    }
                } catch (err: any) {
                    stopPolling(); setLoading(false); setCurrentAgentTaskID(null);
                    setError(err.message || 'Failed to get task update.');
                }
            }, POLLING_INTERVAL);
        }
        return () => stopPolling();
    }, [currentAgentTaskID, addMessageToHistory, setLoading, setError, setCurrentAgentTaskID, setActiveProposals]);

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

    const handleAcceptProposal = async (proposal: ProposedModificationDetail) => {
        if (!currentFocus.scriptId) return;
        if (proposal.modification_type === ModificationType.REPLACE_LINE && proposal.new_text != null) {
            setLoading(true);
            try { await updateLineTextMutation.mutateAsync({ lineId: proposal.target_id, newText: proposal.new_text }); removeProposal(proposal.proposal_id); } 
            catch (e) { /* error handled by mutation */ } 
            finally { setLoading(false); }
        } else { notifications.show({ title: 'Action Error', message: 'Cannot accept this proposal type or missing text.', color: 'orange' }); }
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

    return (
        <Stack h="100%" justify="space-between" gap="xs">
            <Group justify="space-between" p="xs" style={{ borderBottom: '1px solid var(--mantine-color-gray-3)' }}>
                <Text fw={500}>AI Script Collaborator</Text>
                <Tooltip label="Close Chat">
                    <ActionIcon onClick={handleCloseChat} variant="subtle" size="sm">
                        <IconX />
                    </ActionIcon>
                </Tooltip>
            </Group>
            
            <ScrollArea style={{ flex: 1 }} viewportRef={viewport} p="xs">
                {chatDisplayHistory.length === 0 && <Text c="dimmed" ta="center" mt="xl">Start conversation...</Text>}
                {chatDisplayHistory.map((msg: ChatMessage, index: number) => (
                    <Paper key={index} shadow={msg.role === 'user' ? "xs" : "sm"} p="sm" mb="xs" radius="md" withBorder bg={msg.role === 'user' ? 'blue.0' : 'gray.0'}
                        style={{ marginLeft: msg.role === 'user' ? 'auto' : undefined, marginRight: msg.role === 'assistant' ? 'auto' : undefined, maxWidth: '80%',
                            borderBottomLeftRadius: msg.role === 'user' ? 'md' : 'sm', borderBottomRightRadius: msg.role === 'assistant' ? 'md' : 'sm' }}>
                       <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</Text>
                        <Text size="xs" c="dimmed" ta={msg.role === 'user' ? 'right' : 'left'} mt={3}>
                            {msg.role === 'user' ? 'You' : 'AI Assistant'}
                        </Text>
                    </Paper>
                ))}
                {isLoading && !activeProposals.length && <Group justify="center" mt="md"><Loader size="sm" /></Group>}
            </ScrollArea>

            {/* Display Active Proposals - Restoring full card with buttons */}
            {activeProposals.length > 0 && (
                <Paper withBorder p="xs" radius="sm" mt="xs" shadow="sm" style={{maxHeight: '40%', overflowY: 'auto', flexShrink: 0}}>
                    <Group justify="space-between" mb="sm">
                        <Text fw={500}>AI Suggestions ({activeProposals.length})</Text>
                        {activeProposals.length > 1 && (
                            <Button 
                                size="xs" 
                                variant="gradient" 
                                gradient={{ from: 'teal', to: 'lime', deg: 105 }}
                                onClick={handleAcceptAllProposals}
                                disabled={isAcceptingAll || isLoading}
                                loading={isAcceptingAll}
                            >
                                Accept All
                            </Button>
                        )}
                    </Group>
                    <Stack gap="xs">
                        {activeProposals.map((proposal: ProposedModificationDetail, index: number) => {
                            const isEditingThis = editingProposals[proposal.proposal_id] !== undefined;
                            const isEditingThisProposal = editingProposals[proposal.proposal_id] !== undefined;
                            return (
                                <Card key={proposal.proposal_id || index} withBorder p="xs" radius="sm">
                                    <Text size="xs" fw={500}><IconBulb size={14} style={{ marginRight: 4, verticalAlign: 'middle'}} /> {proposal.modification_type.replace('_',' ')}</Text>
                                    
                                    {isEditingThis ? (
                                        <Textarea
                                            value={editedProposalText}
                                            onChange={(event) => setEditedProposalText(event.currentTarget.value)}
                                            minRows={2}
                                            autosize
                                            mt="xs"
                                            placeholder="Edit proposed text..."
                                        />
                                    ) : (
                                        proposal.new_text && <Text size="xs" mt={1}>New Text: <Text span style={{fontFamily: 'monospace', backgroundColor: 'var(--mantine-color-gray-1)', padding: '1px 3px', borderRadius: '2px'}}>{proposal.new_text}</Text></Text>
                                    )}
                                    
                                    <Text size="sm" c="dimmed" mb="xs">
                                        Reasoning: {proposal.reasoning || 'N/A'}
                                    </Text>
                                    {proposal.suggested_line_key && (
                                        <Text size="xs" c="blue" tt="uppercase" fw={700} mb="xs">
                                            Line Key: {proposal.suggested_line_key}
                                        </Text>
                                    )}
                                    
                                    {/* Main Action Buttons for the proposal card */}
                                    <Group justify="flex-end" mt="sm" gap="xs">
                                        <Button
                                            size="xs"
                                            onClick={() => {
                                                const textToCommit = editingProposals[proposal.proposal_id] ?? proposal.new_text;
                                                const proposalToAccept: ProposedModificationDetail = {
                                                    ...proposal,
                                                    new_text: textToCommit
                                                };
                                                if (isEditingThisProposal) {
                                                    // If it was being edited, commit this version then clear editing state for this specific proposal.
                                                    handleAcceptProposal(proposalToAccept).then(() => {
                                                        setEditingProposals(prev => {
                                                            const newState = {...prev};
                                                            delete newState[proposal.proposal_id];
                                                            return newState;
                                                        });
                                                    });
                                                } else {
                                                    handleAcceptProposal(proposalToAccept);
                                                }
                                            }}
                                            disabled={isAcceptingAll || isLoading || (isEditingThisProposal && !editingProposals[proposal.proposal_id]?.trim())}
                                            loading={isLoading && updateLineTextMutation.isPending && updateLineTextMutation.variables?.lineId === proposal.target_id} // Show loading on this specific button if its line is being updated
                                        >
                                            {isEditingThisProposal ? 'Save & Commit' : 'Accept & Commit'}
                                        </Button>
                                        <Tooltip label={isEditingThisProposal ? "Cancel Edit" : "Edit this suggestion before committing"}>
                                            <ActionIcon
                                                variant="outline"
                                                onClick={() => {
                                                    if (isEditingThisProposal) {
                                                        // Cancel edit for this specific proposal
                                                        setEditingProposals(prev => {
                                                            const newState = {...prev};
                                                            delete newState[proposal.proposal_id];
                                                            return newState;
                                                        });
                                                    } else {
                                                        // Start editing this specific proposal
                                                        setEditingProposals(prev => ({...prev, [proposal.proposal_id]: proposal.new_text || ''}));
                                                    }
                                                }}
                                                disabled={isAcceptingAll || isLoading}
                                            >
                                                {isEditingThisProposal ? <IconX size={16} /> : <IconEdit size={16} />}
                                            </ActionIcon>
                                        </Tooltip>
                                        <Tooltip label="Dismiss this suggestion">
                                            <ActionIcon
                                                variant="outline"
                                                color="red"
                                                onClick={() => handleDismissProposal(proposal.proposal_id)}
                                                disabled={isAcceptingAll || isLoading}
                                            >
                                                <IconTrash size={16} />
                                            </ActionIcon>
                                        </Tooltip>
                                    </Group>
                                </Card>
                            );
                        })}
                    </Stack>
                </Paper>
            )}
            
            {error && (
                <Alert variant="light" color="red" title="Chat Error" icon={<IconX />} withCloseButton onClose={() => setError(null)} mb="sm" p="xs" >
                    <Text size="xs">{error}</Text>
                </Alert>
            )}
            <Group wrap="nowrap" gap="xs" style={{padding: 'var(--mantine-spacing-xs)', borderTop: '1px solid var(--mantine-color-gray-3)'}}>
                <Textarea placeholder="Type your message..." value={currentMessage} onChange={(event) => setCurrentMessage(event.currentTarget.value)}
                    style={{ flexGrow: 1 }} minRows={1} maxRows={4} autosize disabled={isLoading}
                    onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSendMessage(); }}}
                />
                <Button onClick={handleSendMessage} disabled={!currentMessage.trim() || isLoading} loading={isLoading} variant="filled">
                    <IconSend size={18} />
                </Button>
            </Group>
        </Stack>
    );
} 