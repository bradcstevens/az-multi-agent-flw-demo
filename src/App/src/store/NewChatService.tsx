
/**
 * Service for handling "New chat" button functionality across different pages
 * Provides reusable methods for navigating to homepage and resetting textarea
 */
export class NewChatService {
    /**
     * Event name for textarea reset functionality
     */
    private static readonly RESET_TEXTAREA_EVENT = 'resetTextarea';

    /**
     * Handle new chat action from ChatPage
     * Navigates to homepage and resets textarea
     * @param navigate - React Router navigate function
     */
    static handleNewChatFromChat(navigate: (to: string) => void): void {
        // Navigate to homepage
        navigate('/');

        // Emit event to reset textarea after navigation
        // Use setTimeout to ensure navigation completes first
        setTimeout(() => {
            NewChatService.resetTextarea();
        }, 100);
    }

    /**
     * Handle new chat action from HomePage
     * Resets textarea to empty state
     */
    static handleNewChatFromHome(): void {
        NewChatService.resetTextarea();
    }

    /**
     * Reset textarea to empty state
     * Emits a custom event that HomeInput component can listen to
     */
    static resetTextarea(): void {
        const event = new CustomEvent(NewChatService.RESET_TEXTAREA_EVENT);
        window.dispatchEvent(event);
    }

    /**
     * Add event listener for textarea reset
     * Should be called in HomeInput component
     * @param callback - Function to call when reset event is triggered
     * @returns Cleanup function to remove the event listener
     */
    static addResetListener(callback: () => void): () => void {
        const handleReset = () => {
            callback();
        };

        window.addEventListener(NewChatService.RESET_TEXTAREA_EVENT, handleReset);

        // Return cleanup function
        return () => {
            window.removeEventListener(NewChatService.RESET_TEXTAREA_EVENT, handleReset);
        };
    }
}
