import React from 'react';
import { Button } from '@fluentui/react-components';

import { useDesktopDrawer } from '@/hooks/usePanelDrawer';
import {
    CHAT_HISTORY_DRAWER_ID,
    CHAT_HISTORY_DRAWER_TOGGLE_CLASS,
} from '@/models/panelDrawer';
import { CHAT_HISTORY_LABEL } from '@/models/storeSurface';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    chatHistoryDrawerToggled,
    selectChatHistoryDrawerOpen,
} from '@/store/slices/panelDrawerSlice';

/**
 * The chat-history **Panel drawer** disclosure (issue #130, ADR-035, ADR-047).
 *
 * A static label plus `aria-expanded`, never a name that flips between *Show*
 * and *Hide*. What it controls is a column the surface opens with, so at first
 * paint it reports itself expanded and the press closes it.
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
