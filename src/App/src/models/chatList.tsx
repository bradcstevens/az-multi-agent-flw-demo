/**
 * The left panel's rows.
 *
 * A row is a **Chat** — one Session and the plans it holds (ADR-025) — which
 * is why the row's own id is a `session_id` and the Plan it opens is a
 * separate field.
 */
export interface Chat {
    id: string;
    name: string;
    /**
     * The Plan this row opens — the chat's latest.
     *
     * A row is a Chat and a Chat is a Session (ADR-025), which can hold more
     * than one Plan. The row therefore carries the plan it opens rather than
     * leaving the caller to search the plans for one matching its session:
     * that search took the first match, so the escalation was unreachable
     * from the panel (#71).
     */
    planId: string;
    status: string;
    date?: string;
}

export interface ChatListProps {
    completedChats: Chat[];
    onChatSelect: (chatId: string) => void;
    loading?: boolean;
    selectedChatId?: string;
    isLoadingTeam?: boolean;
}
