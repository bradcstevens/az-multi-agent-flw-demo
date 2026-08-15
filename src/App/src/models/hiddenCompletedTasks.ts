/**
 * The **Hidden completed tasks** (issue #66, ADR-022).
 *
 * A morning of rehearsals leaves a long list of completed tasks in the left
 * panel. The presenter wants a clean panel before the customer walks in, and
 * this is the browser's whole memory of that.
 *
 * **It hides; it never deletes.** `delete_plan_by_plan_id` is implemented in
 * `cosmosdb.py` and reachable from exactly one caller — the human-feedback
 * rejection path — with no REST route in front of it, and ADR-022 exists to
 * keep it that way. Nothing here reaches the server: every plan stays in
 * Cosmos, which is what the intermittency work behind #47 and #54 read.
 *
 * Three properties follow, and each is an acceptance criterion:
 *
 * * **A set of ids, not a flag.** A task that completes *after* a clear still
 *   appears. "Stay hidden until I unhide" is a different feature and is
 *   deliberately not this one.
 * * **`sessionStorage`**, following the **Signed-in device** precedent — *"so a
 *   fresh tab is a fresh device."* Within a run the clear survives a reload, so
 *   the reset actually holds; a fresh tab is a fresh demonstration with the
 *   whole history back.
 * * **The label says it hides.** A control saying *delete* over a record that
 *   survives is the identity form of the rule the transparency panels run on,
 *   so the words live here beside the behaviour rather than loose in a
 *   component.
 *
 * The id is the one the task list keys a task by — the chat's `session_id`. One chat is one row
 * (#71), so hiding a row hides exactly one conversation; the plan that row *opens* is a separate
 * thing the row carries, and is not what is hidden.
 */

/** Where the tab remembers what the presenter hid. Namespaced, as the key is shared. */
export const HIDDEN_COMPLETED_TASKS_KEY = 'store-assistant.hidden-completed-tasks';

/**
 * What the control is called.
 *
 * Named for what it does. "Delete" would be false, and ADR-022 makes that the
 * whole reason the hide is honest rather than a lie the audience cannot check.
 */
export const HIDE_COMPLETED_LABEL = 'Hide completed tasks';

/**
 * What the list says when there is nothing in it.
 *
 * *"to show"* is load-bearing: a bare "No completed tasks" becomes false the
 * moment a clear hides some, and the panel would be claiming the records are
 * gone when they are not.
 */
export const NO_COMPLETED_TASKS_MESSAGE = 'No completed tasks to show';

type Listener = () => void;

const listeners = new Set<Listener>();

const NOTHING_HIDDEN: ReadonlySet<string> = new Set<string>();

/**
 * The hidden ids in memory, so the module still works when storage does not.
 *
 * `undefined` means "not read from storage yet", which is what a reload leaves
 * behind. The set's identity is stable between changes, because the hook that
 * reads this is a `useSyncExternalStore` snapshot and a fresh set every read is
 * an infinite render.
 */
let remembered: ReadonlySet<string> | undefined;

const usable = (id: unknown): string | null =>
    typeof id === 'string' && id.trim() ? id.trim() : null;

/**
 * Storage, if this browser has any that works.
 *
 * Private browsing throws on both read and write, and a stored value can be
 * anything at all — this key is one `JSON.parse` away from a blank panel. A
 * clear that cannot outlive a reload is a small loss; a screen that throws is
 * the whole demonstration, so every access here is total.
 */
const readStored = (): ReadonlySet<string> => {
    try {
        const stored: unknown = JSON.parse(
            window.sessionStorage.getItem(HIDDEN_COMPLETED_TASKS_KEY) ?? 'null',
        );
        if (!Array.isArray(stored)) return NOTHING_HIDDEN;

        const ids = stored.map(usable).filter((id): id is string => id !== null);
        return ids.length ? new Set(ids) : NOTHING_HIDDEN;
    } catch {
        return NOTHING_HIDDEN;
    }
};

const announce = (): void => {
    listeners.forEach((listener) => listener());
};

/** The completed tasks the presenter has hidden on this device. */
export const hiddenCompletedTaskIds = (): ReadonlySet<string> => {
    if (remembered === undefined) {
        remembered = readStored();
    }
    return remembered;
};

/** Whether this task is one the presenter hid. */
export const isCompletedTaskHidden = (id: string): boolean =>
    hiddenCompletedTaskIds().has(id);

/**
 * Hide these tasks from view.
 *
 * Adds to what is already hidden rather than replacing it, and does nothing at
 * all when every id given is already hidden — a snapshot that changed identity
 * without changing content re-renders every reader for no reason.
 */
export const hideCompletedTasks = (ids: readonly string[]): void => {
    const current = hiddenCompletedTaskIds();
    const added = ids
        .map(usable)
        .filter((id): id is string => id !== null && !current.has(id));
    if (!added.length) return;

    const next = new Set([...current, ...added]);
    remembered = next;
    try {
        window.sessionStorage.setItem(
            HIDDEN_COMPLETED_TASKS_KEY,
            JSON.stringify([...next]),
        );
    } catch {
        /* Storage refused; the tab still knows until it is reloaded. */
    }
    announce();
};

/**
 * Show the whole history again — what a fresh tab does.
 *
 * Not an unhide control. There is no such affordance on the surface, because
 * the presenter's reset is a fresh tab and ADR-022 says so; this is the seam
 * that behaviour is written against.
 */
export const forgetHiddenCompletedTasks = (): void => {
    remembered = NOTHING_HIDDEN;
    try {
        window.sessionStorage.removeItem(HIDDEN_COMPLETED_TASKS_KEY);
    } catch {
        /* Nothing stored is nothing to remove. */
    }
    announce();
};

/** Subscribe to changes, for the panel that renders this. */
export const subscribeToHiddenCompletedTasks = (listener: Listener): (() => void) => {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
};
