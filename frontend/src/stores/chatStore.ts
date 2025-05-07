import { create } from 'zustand';
import { ProposedModificationDetail } from '../types'; // Import the new type

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

    toggleChatOpen: () => void;
    openChatWithFocus: (focus: ChatFocus) => void;
    addMessageToHistory: (message: ChatMessage) => void;
    setCurrentMessage: (message: string) => void;
    setLoading: (loading: boolean) => void;
    setCurrentFocus: (focus: ChatFocus) => void;
    setCurrentAgentTaskID: (taskId: string | null) => void;
    setError: (error: string | null) => void;
    clearChat: () => void; // Action to clear history and focus
    setActiveProposals: (proposals: ProposedModificationDetail[]) => void;
    removeProposal: (proposalId: string) => void; // To remove one after action
    clearActiveProposals: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
    isChatOpen: false,
    chatDisplayHistory: [],
    currentMessage: '',
    isLoading: false,
    currentFocus: { scriptId: null, categoryId: null, lineId: null },
    currentAgentTaskID: null,
    error: null,
    activeProposals: [],

    toggleChatOpen: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
    
    openChatWithFocus: (focus) => set({
        isChatOpen: true,
        currentFocus: focus, 
        // chatDisplayHistory: [], // Optionally clear history when focus changes, or manage this separately
        // currentMessage: '', 
        error: null, 
        isLoading: false, 
        currentAgentTaskID: null 
    }),

    addMessageToHistory: (message) => 
        set((state) => ({ chatDisplayHistory: [...state.chatDisplayHistory, message] })),
    
    setCurrentMessage: (message) => set({ currentMessage: message }),
    
    setLoading: (loading) => set({ isLoading: loading }),
    
    setCurrentFocus: (focus) => set({ currentFocus: focus }),
    
    setCurrentAgentTaskID: (taskId) => set({ currentAgentTaskID: taskId }),

    setError: (error) => set({ error: error }),

    clearChat: () => set({
        chatDisplayHistory: [],
        currentMessage: '',
        isLoading: false,
        // currentFocus: { scriptId: null, categoryId: null, lineId: null }, // Keep focus or clear?
        currentAgentTaskID: null,
        error: null
    }),

    setActiveProposals: (proposals) => set({ activeProposals: proposals, isLoading: false }), // Also turn off loading when proposals are set
    removeProposal: (proposalId) => 
        set((state) => ({ 
            activeProposals: state.activeProposals.filter(p => p.proposal_id !== proposalId) 
        })),
    clearActiveProposals: () => set({ activeProposals: [] }),
}));

// Example of how to get part of the history for context (e.g., last N messages)
// This can be a selector or a helper function used by components.
export const getChatHistoryForContext = (history: ChatMessage[], count: number = 6): ChatMessage[] => {
    return history.slice(Math.max(history.length - count, 0));
}; 