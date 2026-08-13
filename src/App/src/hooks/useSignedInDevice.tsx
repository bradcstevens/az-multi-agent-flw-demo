import React from 'react';

import {
    signedInName,
    subscribeToSignedInDevice,
} from '../models/signedInDevice';

/**
 * The associate signed in on this device, re-rendering when that changes (#27).
 *
 * `useSyncExternalStore` rather than a Redux slice, because the **Signed-in
 * device** is not application state that a reducer owns: it is one fact,
 * persisted for the tab, read by the header *and* by the request path, and
 * written by whichever of them learns first that the gate has refused. A copy
 * in a store is a second answer to "who is signed in?", and the failure mode of
 * two answers is a header naming somebody the Identity boundary gate will not
 * answer for.
 */
export const useSignedInName = (): string | null =>
    React.useSyncExternalStore(subscribeToSignedInDevice, signedInName, () => null);

export default useSignedInName;
