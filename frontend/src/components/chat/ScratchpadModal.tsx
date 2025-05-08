import React, { useEffect, useState } from 'react';
import { Modal, ScrollArea, Text, Loader, Alert, Paper, Stack, Button, Group, ActionIcon, Tooltip, Box } from '@mantine/core'; // Import ActionIcon, Tooltip, Box
import { IconAlertCircle, IconTrash } from '@tabler/icons-react'; // Import IconTrash
import { api } from '../../api';
import { ScriptNoteData } from '../../types';
import AppModal from '../common/AppModal'; // Import the AppModal wrapper
import { notifications } from '@mantine/notifications'; // For feedback

interface ScratchpadModalProps {
    opened: boolean;
    onClose: () => void;
    scriptId: number | null;
}

export function ScratchpadModal({ opened, onClose, scriptId }: ScratchpadModalProps) {
    const [notes, setNotes] = useState<ScriptNoteData[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        // Fetch notes only when the modal is opened and scriptId is valid
        if (opened && scriptId) {
            console.log(`[ScratchpadModal] Modal opened for script ${scriptId}, fetching notes...`);
            setIsLoading(true);
            setError(null);
            api.getScratchpadNotes(scriptId)
                .then(data => {
                    setNotes(data);
                })
                .catch(err => {
                    console.error("[ScratchpadModal] Failed to fetch notes:", err);
                    setError(err.message || "Failed to load scratchpad notes.");
                    setNotes([]); // Clear notes on error
                })
                .finally(() => {
                    setIsLoading(false);
                });
        } else if (!opened) {
             // Clear state when modal closes
            setNotes([]);
            setError(null);
            setIsLoading(false);
        }
    }, [opened, scriptId]); // Rerun when modal opens or scriptId changes

    const handleDeleteNote = async (noteToDelete: ScriptNoteData) => {
        if (!scriptId) return;

        // Use window.confirm for simplicity
        const confirmationText = `Are you sure you want to delete this scratchpad note? ${noteToDelete.title ? `(${noteToDelete.title})` : ''}`;
        if (!window.confirm(confirmationText)) {
            return; // User cancelled
        }

        const noteIdToDelete = noteToDelete.id;
        // Optional: Add specific loading state for delete?

        try {
            await api.deleteScratchpadNote(scriptId, noteIdToDelete);
            // Remove note from local state for immediate UI update
            setNotes(currentNotes => currentNotes.filter(note => note.id !== noteIdToDelete));
            notifications.show({ title: 'Note Deleted', message: 'Scratchpad note deleted successfully.', color: 'green' });
        } catch (err: any) {
            console.error("[ScratchpadModal] Failed to delete note:", err);
            notifications.show({ title: 'Delete Failed', message: err.message || 'Could not delete note.', color: 'red' });
        }
    };

    return (
        // Use AppModal instead of Modal
        <AppModal
            opened={opened}
            onClose={onClose}
            title="Scratchpad Notes"
            size="lg"
            // Remove centered and scrollAreaComponent, AppModal likely handles defaults or has its own way
            // centered 
            // scrollAreaComponent={ScrollArea.Autosize} 
        >
            {isLoading && (
                <Group justify="center" p="md">
                    <Loader size="sm" />
                    <Text>Loading notes...</Text>
                </Group>
            )}
            {error && (
                <Alert color="red" title="Error Loading Notes" icon={<IconAlertCircle />} m="md">
                    {error}
                </Alert>
            )}
            {!isLoading && !error && notes.length === 0 && (
                <Text c="dimmed" ta="center" p="md">No notes saved for this script yet.</Text>
            )}
            {!isLoading && !error && notes.length > 0 && (
                // Use Mantine ScrollArea directly inside AppModal content if needed for the list
                <ScrollArea style={{ maxHeight: '60vh' }}> {/* Add max height for scroll */}
                    <Stack gap="xs" p="xs">
                        {notes.map(note => (
                            <Paper key={note.id} withBorder p="sm" radius="sm" shadow="xs">
                                <Group justify="space-between" align="flex-start" wrap="nowrap">
                                    <Box style={{ flexGrow: 1 }}>
                                        {note.title && <Text fw={500} size="sm" mb={2}>{note.title}</Text>}
                                        <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{note.text_content}</Text>
                                        <Text size="xs" c="dimmed" ta="right" mt={3}>
                                            Updated: {new Date(note.updated_at).toLocaleString()}
                                            {/* Optionally show relation */} 
                                            {/* {note.category_id && ` (Category: ${note.category_id})`} */} 
                                            {/* {note.line_id && ` (Line: ${note.line_id})`} */} 
                                        </Text>
                                    </Box>
                                    <Tooltip label="Delete Note">
                                        <ActionIcon 
                                            variant="subtle" 
                                            color="red" 
                                            onClick={() => handleDeleteNote(note)} 
                                            size="sm"
                                        >
                                            <IconTrash size={16} />
                                        </ActionIcon>
                                    </Tooltip>
                                </Group>
                            </Paper>
                        ))}
                    </Stack>
                </ScrollArea>
            )}
            <Group justify="flex-end" mt="md" p="xs" style={{ borderTop: '1px solid var(--mantine-color-gray-3)' }}>
                <Button variant="default" onClick={onClose}>Close</Button>
            </Group>
        </AppModal>
    );
} 