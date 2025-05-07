import { ActionIcon, Tooltip } from '@mantine/core';
import { IconMessageCircle } from '@tabler/icons-react';
import { useChatStore } from '../../stores/chatStore';

interface ChatFabProps {
    scriptId: number | null; // To set the focus when opening
    // Potentially add categoryId, lineId if the FAB can be context-specific
}

export function ChatFab({ scriptId }: ChatFabProps) {
    const { openChatWithFocus, isChatOpen } = useChatStore((state) => ({
        openChatWithFocus: state.openChatWithFocus,
        isChatOpen: state.isChatOpen,
    }));

    const handleOpenChat = () => {
        if (scriptId) {
            openChatWithFocus({ scriptId });
        } else {
            // Handle case where scriptId is not available, maybe disable button or open generic chat?
            // For now, we assume scriptId will be available from VoScriptDetailView
            console.warn("ChatFab clicked without a scriptId");
        }
    };

    // Optionally, don't render if chat is already open, or style it differently
    // if (isChatOpen) return null; 

    return (
        <Tooltip label="Chat with AI Script Collaborator" position="left" withArrow>
            <ActionIcon
                variant="filled"
                color="blue"
                size="xl"
                radius="xl"
                style={{
                    position: 'fixed',
                    bottom: '2rem',
                    right: '2rem',
                    zIndex: 1000, // Ensure it's above other content
                }}
                onClick={handleOpenChat}
                disabled={!scriptId} // Disable if no scriptId
            >
                <IconMessageCircle size={28} />
            </ActionIcon>
        </Tooltip>
    );
} 