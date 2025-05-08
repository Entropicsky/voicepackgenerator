import { create, StateCreator } from 'zustand';
import { ProposedModificationDetail, StagedCharacterDescriptionData, ScriptNoteData } from '../types'; // Import the new type

export interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
    // We might add more fields later, like proposals or timestamps
}

export interface ChatFocus {
    scriptId: number | null;
    categoryId?: number | null; // Assuming category ID from template
    lineId?: number | null;
}

export interface ChatState {
    isChatOpen: boolean;
    chatDisplayHistory: ChatMessage[];
    currentMessage: string;
    isLoading: boolean;
    currentFocus: ChatFocus;
    currentAgentTaskID: string | null;
    error: string | null;
    activeProposals: ProposedModificationDetail[];
    stagedDescriptionUpdate: StagedCharacterDescriptionData | null;
    scratchpadNotes: ScriptNoteData[];

    toggleChatOpen: () => void;
    openChatWithFocus: (focus: ChatFocus) => void;
    addMessageToHistory: (message: ChatMessage) => void;
    setChatDisplayHistory: (history: ChatMessage[]) => void;
    setCurrentMessage: (message: string) => void;
    setLoading: (loading: boolean) => void;
    setCurrentFocus: (focus: ChatFocus) => void;
    setCurrentAgentTaskID: (taskId: string | null) => void;
    setError: (error: string | null) => void;
    clearChat: () => void; // Action to clear history and focus
    setActiveProposals: (proposals: ProposedModificationDetail[]) => void;
    removeProposal: (proposalId: string) => void; // To remove one after action
    clearActiveProposals: () => void;
    setStagedDescriptionUpdate: (update: StagedCharacterDescriptionData | null) => void;
    clearStagedDescriptionUpdate: () => void;
    setScratchpadNotes: (notes: ScriptNoteData[]) => void;
}

// Explicitly type the creator function for better type safety
const chatStoreCreator: StateCreator<ChatState> = (set, get) => ({
    isChatOpen: false,
    chatDisplayHistory: [],
    currentMessage: '',
    isLoading: false,
    currentFocus: { scriptId: null, categoryId: null, lineId: null },
    currentAgentTaskID: null,
    error: null,
    activeProposals: [],
    stagedDescriptionUpdate: null,
    scratchpadNotes: [],

    toggleChatOpen: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
    
    openChatWithFocus: (focus) => set({
        isChatOpen: true,
        currentFocus: focus, 
        error: null, 
        isLoading: false, 
        currentAgentTaskID: null 
    }),

    addMessageToHistory: (message) => 
        set((state) => ({ chatDisplayHistory: [...state.chatDisplayHistory, message] })),
    
    setChatDisplayHistory: (history: ChatMessage[]) => set({ 
        chatDisplayHistory: history 
        // Consider if isLoading or error should be reset here too, if related to history load
    }),
    
    setCurrentMessage: (message) => set({ currentMessage: message }),
    
    setLoading: (loading) => set({ isLoading: loading }),
    
    setCurrentFocus: (focus) => set({ currentFocus: focus }),
    
    setCurrentAgentTaskID: (taskId) => set({ currentAgentTaskID: taskId }),

    setError: (error) => set({ error: error }),

    clearChat: () => set({
        chatDisplayHistory: [],
        currentMessage: '',
        isLoading: false,
        currentAgentTaskID: null,
        error: null
    }),

    setActiveProposals: (proposals) => set({ activeProposals: proposals, isLoading: false }),
    removeProposal: (proposalId) => 
        set((state) => ({ 
            activeProposals: state.activeProposals.filter(p => p.proposal_id !== proposalId) 
        })),
    clearActiveProposals: () => set({ activeProposals: [] }),

    setStagedDescriptionUpdate: (update) => set({ stagedDescriptionUpdate: update }),
    clearStagedDescriptionUpdate: () => set({ stagedDescriptionUpdate: null }),

    setScratchpadNotes: (notes) => set({ scratchpadNotes: notes }),
});

export const useChatStore = create<ChatState>(chatStoreCreator);

// Example of how to get part of the history for context (e.g., last N messages)
// This can be a selector or a helper function used by components.
export const getChatHistoryForContext = (history: ChatMessage[], count: number = 6): ChatMessage[] => {
    return history.slice(Math.max(history.length - count, 0));
}; 