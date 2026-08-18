import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import type { RootState } from '../store';

export interface PanelDrawerState {
    /** The chat-history Panel drawer is transient navigation, never a saved preference. */
    chatHistoryOpen: boolean;
}

const initialState: PanelDrawerState = {
    chatHistoryOpen: false,
};

const panelDrawerSlice = createSlice({
    name: 'panelDrawer',
    initialState,
    reducers: {
        chatHistoryDrawerSetOpen(state, action: PayloadAction<boolean>) {
            state.chatHistoryOpen = action.payload;
        },
        chatHistoryDrawerToggled(state) {
            state.chatHistoryOpen = !state.chatHistoryOpen;
        },
    },
});

export const {
    chatHistoryDrawerSetOpen,
    chatHistoryDrawerToggled,
} = panelDrawerSlice.actions;

export const selectChatHistoryDrawerOpen = (state: RootState): boolean =>
    state.panelDrawer?.chatHistoryOpen ?? false;

export default panelDrawerSlice.reducer;
