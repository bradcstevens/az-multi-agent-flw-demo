/**
 * What a chat row says about the state it is in (#74).
 *
 * The chat list shows chats in **every** `PlanStatus`, not only finished ones
 * — the chat most worth resuming is the one that did not finish, and that was
 * exactly the chat the old `completed` filter hid. With `failed` and
 * `canceled` chats on screen beside good ones, a row that does not state its
 * state cannot be told apart from a row that does, so this is the words it
 * says.
 *
 * A Chat's state is its **latest** Plan's `overall_status` (#71): an escalation
 * still running makes the whole conversation in progress, and saying otherwise
 * would have the surface calling a running escalation complete.
 */
import { PlanStatus } from './enums';

/**
 * The states the surface names in its own words.
 *
 * Keyed by the value the backend persists, not by the enum member, because the
 * wire is what a row is built from.
 */
const CHAT_STATE_LABELS: Readonly<Record<string, string>> = {
    [PlanStatus.CREATED]: 'Created',
    [PlanStatus.APPROVED]: 'Approved',
    [PlanStatus.IN_PROGRESS]: 'In progress',
    [PlanStatus.COMPLETED]: 'Completed',
    [PlanStatus.FAILED]: 'Failed',
    [PlanStatus.CANCELED]: 'Canceled',
};

/**
 * What this row says its state is.
 *
 * **Total.** It is called while building every row, and the set of statuses
 * lives in the backend — a status added there must reach the panel as itself
 * rather than as a blank row or, as `formatPlanDate` once did, as a throw that
 * takes the whole history with it.
 *
 * A record reporting no state at all is given no label: a row saying "Unknown"
 * is a claim about the chat, and the surface has nothing to base it on.
 */
export const chatStateLabel = (status?: string): string => {
    const reported = status?.trim();
    if (!reported) return '';

    const known = CHAT_STATE_LABELS[reported];
    if (known) return known;

    const said = reported.replace(/[_-]+/g, ' ').trim();
    return said.charAt(0).toUpperCase() + said.slice(1);
};

/**
 * What the list says when there is nothing in it.
 *
 * Chats, not completed tasks: the list is no longer a completed-only list.
 * *"to show"* is kept from ADR-022 and load-bearing for the same reason — a
 * bare "No chats" becomes false the moment a hide takes some out of view, and
 * the panel would be claiming the records are gone when every plan is still in
 * Cosmos.
 */
export const NO_CHATS_MESSAGE = 'No chats to show';
