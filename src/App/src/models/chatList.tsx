import { PlanStatus } from './enums';

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
    /**
     * What state this chat is in — its **latest** plan's `overall_status`.
     *
     * The domain's own status, not a two-valued surface word (#74). The list
     * holds chats in every state, so a row has to be able to say which of
     * `failed`, `canceled` and `in_progress` it is; "not completed" cannot.
     * `chatStateLabel` in `models/chatState.ts` is the words it says.
     */
    status: PlanStatus;
    date?: string;
}

export interface ChatListProps {
    /** Every chat, in every state (#74) — the panel filters nothing out. */
    chats: Chat[];
    onChatSelect: (chatId: string) => void;
    loading?: boolean;
    selectedChatId?: string;
    isLoadingTeam?: boolean;
}
