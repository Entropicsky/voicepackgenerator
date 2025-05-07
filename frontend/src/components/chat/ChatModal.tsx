import { Modal, Text, Stack, Textarea, Button, Group, ScrollArea, Paper, Loader, Alert, Card, Badge } from '@mantine/core';
import { IconSend, IconX, IconBulb, IconCheck, IconEdit, IconTrash } from '@tabler/icons-react';
import AppModal from '../common/AppModal';
import { useChatStore, ChatState, ChatMessage, getChatHistoryForContext } from '../../stores/chatStore';
import { ChatTaskResult, ProposedModificationDetail, ModificationType, VoScriptLineData, AddVoScriptLinePayload } from '../../types'; // Import VoScriptLineData for mutation response
import { api } from '../../api';
import { useEffect, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query'; // Import query client hooks
import { notifications } from '@mantine/notifications';

const POLLING_INTERVAL = 3000;

export function ChatModal() {
    const {
        isChatOpen, toggleChatOpen, chatDisplayHistory, currentMessage, setCurrentMessage,
        isLoading, setLoading, error, setError, currentFocus, currentAgentTaskID,
        setCurrentAgentTaskID, addMessageToHistory, activeProposals, setActiveProposals, removeProposal
    } = useChatStore((state: ChatState) => state);

    const queryClient = useQueryClient();
    const viewport = useRef<HTMLDivElement>(null);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    useEffect(() => {
        if (isChatOpen && viewport.current) {
            viewport.current.scrollTo({ top: viewport.current.scrollHeight, behavior: 'smooth' });
        }
    }, [chatDisplayHistory, isChatOpen, activeProposals]); // Added activeProposals to scroll if they appear

    const handleSendMessage = async () => {
        if (!currentMessage.trim() || isLoading || !currentFocus.scriptId) return;
        const userMessage: ChatMessage = { role: 'user', content: currentMessage.trim() };
        addMessageToHistory(userMessage);
        const messageForApi = currentMessage.trim();
        setCurrentMessage('');
        setLoading(true);
        setError(null);
        setActiveProposals([]); // Clear previous proposals when sending a new message
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
        if (currentAgentTaskID) {
            setLoading(true);
            pollingIntervalRef.current = setInterval(async () => {
                try {
                    const statusResponse = await api.getChatTaskStatus(currentAgentTaskID);
                    if (statusResponse.status === 'SUCCESS' && statusResponse.info) {
                        stopPolling();
                        setCurrentAgentTaskID(null); // setLoading(false) will be handled by setActiveProposals or if no proposals
                        const successInfo = statusResponse.info as ChatTaskResult;
                        const aiResponse: ChatMessage = {
                            role: 'assistant',
                            content: successInfo.ai_response_text || "(AI did not provide a text response)"
                        };
                        addMessageToHistory(aiResponse);
                        if (successInfo.proposed_modifications && successInfo.proposed_modifications.length > 0) {
                            setActiveProposals(successInfo.proposed_modifications);
                        } else {
                            setLoading(false); // No proposals, so stop loading
                        }
                        // TODO: Handle scratchpad_updates, updated_conversation_history
                    } else if (statusResponse.status === 'FAILURE') {
                        stopPolling(); setLoading(false); setCurrentAgentTaskID(null);
                        const errorInfo = statusResponse.info as { error?: string; message?: string; };
                        const errorMessage = errorInfo?.error || errorInfo?.message || 'Task failed.';
                        setError(errorMessage);
                        addMessageToHistory({role: 'assistant', content: `Sorry, I encountered an error: ${errorMessage}`});
                    } else if (statusResponse.status !== 'PENDING' && statusResponse.status !== 'STARTED') {
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

    const prevScriptIdRef = useRef<number | null>();
    useEffect(() => {
        if (isChatOpen && currentFocus.scriptId !== prevScriptIdRef.current) {
            if (prevScriptIdRef.current !== null && prevScriptIdRef.current !== undefined) { 
                 useChatStore.getState().clearChat(); 
                 useChatStore.getState().clearActiveProposals();
            }
        }
        prevScriptIdRef.current = currentFocus.scriptId;
    }, [isChatOpen, currentFocus.scriptId]);

    // --- Mutations for Proposal Actions ---
    const updateLineTextMutation = useMutation<
        VoScriptLineData, // Expected success response type from api.updateLineText
        Error,            // Error type
        { lineId: number; newText: string } // Variables type
    >({
        mutationFn: ({ lineId, newText }) => 
            api.updateLineText(currentFocus.scriptId!, lineId, newText),
        onSuccess: (updatedLine) => {
            queryClient.invalidateQueries({ queryKey: ['voScriptDetail', currentFocus.scriptId] });
            notifications.show({
                title: 'Line Updated (Test)',
                message: `Line ${updatedLine.id} text updated successfully via chat proposal.`,
                color: 'green',
                autoClose: 7000 // Keep it for 7 seconds
            });
            console.log("Notification for line update should have been shown."); // Add console log
        },
        onError: (error, variables) => {
            notifications.show({ title: 'Error Updating Line', message: error.message || `Could not update line ${variables.lineId}.`, color: 'red' });
        },
    });

    // TODO: Add mutation for api.addVoScriptLine for INSERT/NEW_LINE_IN_CATEGORY types later
    // const addLineMutation = useMutation<VoScriptLineData, Error, { payload: AddVoScriptLinePayload }>(...);

    const handleAcceptProposal = async (proposal: ProposedModificationDetail) => {
        if (!currentFocus.scriptId) return;

        switch (proposal.modification_type) {
            case ModificationType.REPLACE_LINE:
                if (proposal.new_text !== null && proposal.new_text !== undefined) {
                    try {
                        setLoading(true); // Indicate global loading for this action for now
                        await updateLineTextMutation.mutateAsync({ 
                            lineId: proposal.target_id, 
                            newText: proposal.new_text 
                        });
                        removeProposal(proposal.proposal_id);
                    } catch (e) {
                        // Error already handled by mutation's onError
                    } finally {
                        setLoading(false);
                    }
                } else {
                    notifications.show({ title: 'Accept Error', message: 'No new text provided for line replacement.', color: 'orange' });
                }
                break;
            // TODO: Handle INSERT_LINE_AFTER, INSERT_LINE_BEFORE, NEW_LINE_IN_CATEGORY
            // These will require using the addLineMutation and more complex logic for line_key, order_index.
            // For MVP, these might be deferred or trigger a simpler user prompt.
            default:
                notifications.show({ title: 'Action Not Implemented', message: `Accepting ${proposal.modification_type} is not yet supported.`, color: 'blue' });
                console.warn("Unsupported modification_type for accept:", proposal.modification_type);
        }
    };

    const handleEditProposal = (proposal: ProposedModificationDetail) => { // Changed to take full proposal
        console.log("Editing proposal:", proposal.proposal_id);
        notifications.show({ title: 'Edit Proposal (Not Implemented)', message: `Editing ${proposal.proposal_id}`, color: 'yellow' });
    };

    const handleDismissProposal = (proposalId: string) => {
        removeProposal(proposalId);
        notifications.show({ title: 'Proposal Dismissed', message: `Dismissed ${proposalId}`, color: 'gray' });
    };

    return (
        <AppModal opened={isChatOpen} onClose={toggleChatOpen} title="AI Script Collaborator Chat" size="70%" zIndex={1001}>
            <Stack h="70vh">
                <ScrollArea style={{ flexGrow: 1 }} viewportRef={viewport} p="xs">
                    {chatDisplayHistory.length === 0 && (
                        <Text c="dimmed" ta="center" mt="xl">No messages yet. Start the conversation!</Text>
                    )}
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

                {/* Display Active Proposals */} 
                {activeProposals.length > 0 && (
                    <Paper withBorder p="sm" radius="sm" mt="sm" shadow="md" style={{maxHeight: '35vh', overflowY: 'auto'}}>
                        <Text fw={500} mb="xs">AI Suggestions:</Text>
                        <Stack gap="xs">
                            {activeProposals.map((proposal: ProposedModificationDetail, index: number) => (
                                <Card key={proposal.proposal_id || index} withBorder p="xs" radius="sm">
                                    <Text size="sm" fw={500}><IconBulb size={16} style={{ marginRight: 4}} /> {proposal.modification_type.replace('_',' ')}</Text>
                                    {proposal.new_text && <Text size="xs" mt={2}>New Text: <Text span style={{fontFamily: 'monospace', backgroundColor: 'var(--mantine-color-gray-1)', padding: '2px 4px', borderRadius: '2px'}}>{proposal.new_text}</Text></Text>}
                                    {proposal.reasoning && <Text size="xs" c="dimmed" mt={2}>Reasoning: {proposal.reasoning}</Text>}
                                    <Group justify="flex-end" mt="xs" gap="xs">
                                        <Button size="xs" variant="light" color="red" onClick={() => handleDismissProposal(proposal.proposal_id)} leftSection={<IconX size={14}/>} disabled={updateLineTextMutation.isPending}>Dismiss</Button>
                                        <Button size="xs" variant="light" color="yellow" onClick={() => handleEditProposal(proposal)} leftSection={<IconEdit size={14}/>} disabled={updateLineTextMutation.isPending}>Edit</Button>
                                        <Button size="xs" variant="filled" color="green" onClick={() => handleAcceptProposal(proposal)} leftSection={<IconCheck size={14}/>} loading={updateLineTextMutation.isPending && updateLineTextMutation.variables?.lineId === proposal.target_id} disabled={updateLineTextMutation.isPending}>Accept</Button>
                                    </Group>
                                </Card>
                            ))}
                        </Stack>
                    </Paper>
                )}
                
                {error && (
                    <Alert variant="light" color="red" title="Chat Error" icon={<IconX />} withCloseButton onClose={() => setError(null)} mb="sm">
                        {error}
                    </Alert>
                )}
                <Group wrap="nowrap" gap="xs">
                    <Textarea placeholder="Type your message..." value={currentMessage} onChange={(event) => setCurrentMessage(event.currentTarget.value)}
                        style={{ flexGrow: 1 }} minRows={1} autosize disabled={isLoading}
                        onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSendMessage(); }}}
                    />
                    <Button onClick={handleSendMessage} disabled={!currentMessage.trim() || isLoading} loading={isLoading} variant="filled" size="md">
                        <IconSend size={18} />
                    </Button>
                </Group>
            </Stack>
        </AppModal>
    );
} 