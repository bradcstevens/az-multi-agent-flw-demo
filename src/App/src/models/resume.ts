/**
 * What a turn typed into the chat surface's message box is (#77, ADR-027).
 *
 * The box was the **Clarification** seam's other half and nothing else: with
 * no question pending it had nowhere to send what was typed, and #68 closed it
 * rather than go on posting a clarification against an empty `request_id`.
 * ADR-027 gives it the other thing it can be — a new turn in **this Chat's
 * Session** — which is the recovery path for a presenter who left a
 * conversation and came back to it. The **Follow-on task** card remains the
 * rehearsed path, authored and keyboard-free.
 *
 * **Be precise about what resume carries.** Only what was explicitly
 * persisted against the session: the **Attempted steps**, the identity, the
 * **Lane** and the **Simulated ticket**. The **Workflow cache** is
 * process-local and keyed by *user*, so there is no per-Chat agent thread to
 * restore, and the transcript on screen is display-only — it is never replayed
 * into an agent's context, and nothing here should be read as claiming it is.
 *
 * The rule lives here rather than at either of its two call sites because both
 * need the same answer: `PlanChatBody` decides whether the box may be used and
 * what it invites, `ChatPage` decides where what was typed goes. A box open
 * over a submit path with nowhere to send is #68 read from the other side.
 */

/** What a turn typed into this chat's box will be. */
export type TurnMode =
    /** An answer to the **Clarification** the backend is waiting on. */
    | 'clarification'
    /** A new turn in this **Chat**'s **Session** (ADR-027). */
    | 'resume'
    /** Neither, so the box may not be used. */
    | 'none';

/**
 * Which of the three this chat's box is in.
 *
 * **Total and fail-closed**, for the reason the deletion rule is: a chat whose
 * session this build cannot name is one it cannot continue, and minting a
 * fresh session here would start a *new* conversation under the heading of an
 * old one — losing the very records resume exists to carry, silently.
 *
 * A pending clarification wins over a resumable session, and does not need
 * one: a clarification is posted against a `request_id` and a `plan_id`, never
 * against a session.
 */
export const turnModeFor = (
    pendingClarificationRequestId: string | null | undefined,
    sessionId: string | null | undefined,
): TurnMode => {
    if (pendingClarificationRequestId?.trim()) return 'clarification';
    if (sessionId?.trim()) return 'resume';
    return 'none';
};

/** What the box invites while it is answering a **Clarification**. */
export const ANSWER_THE_QUESTION = 'Type your message here...';

/**
 * What the box invites while a turn typed into it continues this chat.
 *
 * Different words from the answer's, because they are different acts: one
 * replies to a question the assistant asked, the other asks a new one. The
 * placeholder is the only place the surface says which is about to happen.
 */
export const CONTINUE_THIS_CHAT = 'Ask another question in this chat...';

/** What the box invites when it can carry nothing: nothing. */
const INVITES_NOTHING = '';

const PLACEHOLDERS: Readonly<Record<TurnMode, string>> = {
    clarification: ANSWER_THE_QUESTION,
    resume: CONTINUE_THIS_CHAT,
    none: INVITES_NOTHING,
};

/** What the box invites in this mode. */
export const placeholderFor = (mode: TurnMode): string => PLACEHOLDERS[mode];

/**
 * Why the box is closed, said out loud.
 *
 * Being unavailable without a reason is the quieter half of #68's fault, and
 * `NOTHING_TO_ANSWER` — the sentence this replaces — is no longer true: the
 * box opens outside a clarification now. What closes it is a chat the surface
 * cannot name a session for, which is a state, not a failure.
 */
export const NOTHING_TO_CONTINUE =
    'This conversation cannot be continued. Start a new chat to ask something else.';

/**
 * Why a turn that was submitted could not be sent.
 *
 * A different event from the closed box above — this one is a thing the
 * associate did that did not happen — so it is a different sentence.
 */
export const CANNOT_CONTINUE = 'Could not continue this conversation';

/**
 * Why the box is closed while this chat's last turn is still working.
 *
 * A **Resume** turn is a new request, and `process_request` cancels whatever
 * orchestration that user already had running before it schedules the next
 * one — so a turn typed over a working one does not queue behind it, it takes
 * its place. The box refuses rather than lets that happen silently, and says
 * so in its own sentence: this is a *wait*, not the unreachable chat
 * `NOTHING_TO_CONTINUE` describes.
 *
 * A pending **Clarification** is exempt and must stay exempt: there the
 * orchestration is waiting on the associate, and a spinner is up over a turn
 * that cannot progress until the box is used.
 */
export const TURN_STILL_WORKING =
    'This chat is still working on the last turn. It will accept another when it is done.';
