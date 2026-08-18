import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import type { RootState } from '../store';

export interface PanelDrawerState {
    /** The chat-history Panel drawer is transient navigation, never a saved preference. */
    chatHistoryOpen: boolean;
}

const initialState: PanelDrawerState = {
    /*
      Open (#168, ADR-047). The panel is a column, and a surface that opens
      with a hole where its third column belongs makes the presenter find a
      control before the chat list exists at all. The overlay this replaced had
      to start closed — a modal panel covering its own content at first paint
      is incoherent — which was a reason to stop floating it, not a reason to
      hide navigation.
    */
    chatHistoryOpen: true,
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
