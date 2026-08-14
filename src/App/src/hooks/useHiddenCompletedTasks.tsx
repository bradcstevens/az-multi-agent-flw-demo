import React from 'react';

import {
    hiddenCompletedTaskIds,
    subscribeToHiddenCompletedTasks,
} from '../models/hiddenCompletedTasks';

const NOTHING_HIDDEN: ReadonlySet<string> = new Set<string>();

/**
 * The completed tasks the presenter has hidden, re-rendering when that changes
 * (#66).
 *
 * `useSyncExternalStore` rather than a Redux slice, on the **Signed-in
 * device**'s reasoning: this is one fact, persisted for the tab, that no
 * reducer owns and no request path reads. A copy in a store is a second answer
 * to "what is hidden?", and the panel would be free to disagree with the tab it
 * is rendered in.
 *
 * The snapshot's identity is stable between changes — a fresh set on every read
 * is an infinite render — which is why the set lives in the module rather than
 * being derived here.
 */
export const useHiddenCompletedTasks = (): ReadonlySet<string> =>
    React.useSyncExternalStore(
        subscribeToHiddenCompletedTasks,
        hiddenCompletedTaskIds,
        () => NOTHING_HIDDEN,
    );

export default useHiddenCompletedTasks;
