import { useEffect } from 'react';

import webSocketService from '@/store/WebSocketService';
import { useAppDispatch } from '@/store/hooks';
import {
    presenterAlertReceived,
    sourceUsedReceived,
    tokenUsageReceived,
} from '@/store/slices/transparencySlice';
import { ticketRaised } from '@/store/slices/ticketSlice';
import { StreamMessage, WebsocketMessageType } from '@/models';

/**
 * Subscribe the transparency panels to the socket (issue #24).
 *
 * All three signals in one hook because they share one subscription surface and
 * one slice — and because they are one feature: the audience watching the
 * architecture work. `WebSocketService` passes unrecognised message types
 * straight through its default branch, so nothing there needs to change for
 * these; the handlers take the raw `data` off the wire and hand it to the
 * slice, which does the parsing and drops anything it cannot read.
 *
 * The Simulated ticket (#22) rides the same hook although it is not a
 * transparency signal and lives in a slice of its own. It is subscribed here
 * because a second `useEffect` in a second hook is a second thing to mount on
 * every surface the first is mounted on — and the surface this arrives on,
 * the plan page, is the one where a missing subscription looks exactly like a
 * ticket that was never raised.
 */
export function useTransparencySignals(): void {
    const dispatch = useAppDispatch();

    useEffect(() => {
        const unsubs = [
            webSocketService.on(WebsocketMessageType.SOURCE_USED, (message: StreamMessage) =>
                dispatch(sourceUsedReceived(message?.data)),
            ),
            webSocketService.on(WebsocketMessageType.TOKEN_USAGE, (message: StreamMessage) =>
                dispatch(tokenUsageReceived(message?.data)),
            ),
            webSocketService.on(WebsocketMessageType.PRESENTER_ALERT, (message: StreamMessage) =>
                dispatch(presenterAlertReceived(message?.data)),
            ),
            webSocketService.on(WebsocketMessageType.TICKET_RAISED, (message: StreamMessage) =>
                dispatch(ticketRaised(message?.data)),
            ),
        ];
        return () => unsubs.forEach((unsub) => unsub());
    }, [dispatch]);
}

export default useTransparencySignals;
