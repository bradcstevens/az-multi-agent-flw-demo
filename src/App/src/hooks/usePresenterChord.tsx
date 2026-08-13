import { useEffect } from 'react';

import { apiClient } from '@/api/apiClient';
import { isPresenterChord } from '@/models/presenterChord';

/** The hidden route (#23). Deliberately absent from the published schema. */
export const PRESENTER_ALERT_ENDPOINT = '/v4/presenter/alert';

/**
 * Bind the hidden chord to the Presenter alert route (issue #24, R8).
 *
 * A **global** listener, which is the one place this codebase departs from its
 * own convention of inline `onKeyDown` handlers — and it has to: the chord must
 * work while focus is anywhere, including nowhere, and an inline handler would
 * mean the presenter has to click the right box first, on stage, mid-sentence.
 *
 * The request carries an **empty body**. The words are the server's — the route
 * picks from a rehearsed roster and there is no parameter that accepts prose —
 * and the recipient is the server's too, resolved from the sole connected
 * client. There is nothing here for the browser to choose.
 *
 * A failure is swallowed on this side. The backend reports one honestly (404
 * with nobody connected, 502 when the socket refused it) because the presenter
 * pressed a key and deserves to know; but an unhandled rejection thrown into
 * the page during a demo is a worse answer than a beat that did not land, and
 * the console keeps the detail.
 */
export function usePresenterChord(): void {
    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            if (!isPresenterChord(event)) return;
            event.preventDefault();
            Promise.resolve(apiClient.post(PRESENTER_ALERT_ENDPOINT, {})).catch((error) => {
                console.warn('Presenter alert did not land:', error);
            });
        };

        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, []);
}

export default usePresenterChord;
