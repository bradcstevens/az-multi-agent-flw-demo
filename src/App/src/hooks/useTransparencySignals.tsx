import { useEffect } from 'react';

import webSocketService from '@/store/WebSocketService';
import { useAppDispatch } from '@/store/hooks';
import {
    presenterAlertReceived,
    sourceUsedReceived,
    tokenUsageReceived,
} from '@/store/slices/transparencySlice';
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
        ];
        return () => unsubs.forEach((unsub) => unsub());
    }, [dispatch]);
}

export default useTransparencySignals;
