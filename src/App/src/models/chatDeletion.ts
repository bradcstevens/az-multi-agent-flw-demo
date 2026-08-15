/**
 * **Chat deletion** — what the control is allowed to take, and what it says
 * (#75, ADR-026).
 *
 * This module replaces `hiddenCompletedTasks.ts` rather than joining it.
 * ADR-022 chose hiding because the panel was a stage-clearing convenience, so
 * a control labelled *delete* would have claimed an action it did not perform;
 * ADR-025 reframed the panel as Chat management, under which hiding is the
 * weaker choice. The record really goes now, so the label that would have been
 * a lie is the only true one.
 *
 * What goes with it: every document in the Chat's session partition — its
 * plans, their steps, the transcript, `m_plan`, the **Troubleshooting
 * record**, the **Simulated ticket** and the **Session state** — scoped to the
 * associate's own `user_id`, which the backend enforces and this module cannot.
 *
 * Two rules live here, and the second is the one worth reading twice.
 */
import { PlanStatus } from './enums';

/**
 * The three states a conversation stops in.
 *
 * Mirrors `SETTLED_STATUSES` in `src/backend/chat/deletion.py`. Two copies is
 * inherent — the row has to know whether to offer the control *before* any
 * request is made, and the route has to refuse whatever the row offered — so
 * the CI-tooling loop asserts the two agree
 * (`src/tests/ci/test_chat_deletion_contract.py`) rather than trusting them to.
 */
const SETTLED_STATUSES: ReadonlySet<string> = new Set<string>([
    PlanStatus.COMPLETED,
    PlanStatus.FAILED,
    PlanStatus.CANCELED,
]);

/**
 * Whether this chat may be deleted.
 *
 * **Total, and fail-closed with it.** A state this module does not recognise —
 * one the backend adds later, or a record reporting none at all — is a chat
 * something may still be happening to. Offering a delete the route will refuse
 * is the surface claiming an action it does not have, and the cheap side of
 * that mistake is a control that says why it is unavailable.
 */
export const canDeleteChat = (status?: string): boolean => {
    const reported = status?.trim();
    return Boolean(reported && SETTLED_STATUSES.has(reported));
};

/** What the control is called. It deletes, so it says so. */
export const DELETE_CHAT_LABEL = 'Delete chat';

/**
 * The name of the menu a row's delete lives in.
 *
 * Carries the chat's own name: the panel renders one of these per row, and a
 * screen reader offered several identically-named buttons cannot say which
 * conversation it is about to destroy.
 */
export const chatMenuLabel = (name: string): string => `More options for ${name}`;

/** The confirmation's heading. */
export const DELETE_CHAT_TITLE = 'Delete this chat?';

/**
 * What the confirmation says before anything is destroyed.
 *
 * ADR-022 rejected deletion partly because an irreversible action three feet
 * from a live audience destroys the diagnosis trail that #47, #54, #61 and #62
 * read. ADR-026 accepts that cost rather than dismissing it, and this sentence
 * is where the presenter is told what they are about to spend.
 */
export const DELETE_CHAT_WARNING =
    'The conversation, its troubleshooting record and its ticket are removed for ' +
    'good. This cannot be undone.';

/** The button that actually does it — named for the act, not "Yes". */
export const CONFIRM_DELETE_LABEL = 'Delete chat';

/** The button that does not. */
export const CANCEL_DELETE_LABEL = 'Keep chat';

/**
 * Why a running chat is kept.
 *
 * ADR-026's own noted cost: the surface has to explain when it refuses, or the
 * control reads as broken. The same sentence the route answers a 409 with — see
 * `STILL_RUNNING_DETAIL` in `src/backend/chat/deletion.py`.
 */
export const STILL_RUNNING_REASON =
    'This chat is still running, so it cannot be deleted yet.';

/** What a failed delete tells the associate. */
export const DELETE_FAILED_TITLE = 'Could not delete this chat';

/**
 * What the delete route reports back.
 *
 * It reports what actually happened rather than success unconditionally
 * (ADR-026) — a sweep that could not take every document comes back as a
 * failure, not as this shape with a smaller number in it. Everything here is
 * therefore true of a chat that really is gone.
 */
export interface ChatDeletionResponse {
    status: string;
    session_id: string;
    documents_deleted: number;
}
