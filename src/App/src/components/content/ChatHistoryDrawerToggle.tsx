import React from 'react';
import { Button } from '@fluentui/react-components';

import { useDesktopDrawer } from '@/hooks/usePanelDrawer';
import {
    CHAT_HISTORY_DRAWER_ID,
    CHAT_HISTORY_DRAWER_TOGGLE_CLASS,
    CHAT_HISTORY_DRAWER_TOGGLE_ID,
} from '@/models/panelDrawer';
import { CHAT_HISTORY_LABEL } from '@/models/storeSurface';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    chatHistoryDrawerToggled,
    selectChatHistoryDrawerOpen,
} from '@/store/slices/panelDrawerSlice';

/**
 * The chat-history **Panel drawer** disclosure (issue #130, ADR-035).
 *
 * It is absent below the **Stacking breakpoint** because chat history stays
 * dropped there; a control for a drawer that cannot exist would only add a
 * dead tap to the phone surface.
 */
const ChatHistoryDrawerToggle: React.FC = () => {
    const dispatch = useAppDispatch();
    const isDesktopDrawer = useDesktopDrawer();
    const open = useAppSelector(selectChatHistoryDrawerOpen);

    if (!isDesktopDrawer) return null;

    return (
        <Button
            appearance="subtle"
            id={CHAT_HISTORY_DRAWER_TOGGLE_ID}
            className={CHAT_HISTORY_DRAWER_TOGGLE_CLASS}
            aria-controls={CHAT_HISTORY_DRAWER_ID}
            aria-expanded={open}
            onClick={() => dispatch(chatHistoryDrawerToggled())}
        >
            {CHAT_HISTORY_LABEL}
        </Button>
    );
};

export default ChatHistoryDrawerToggle;
