import { createSlice, PayloadAction } from '@reduxjs/toolkit';

import type { RootState } from '../store';
import { Verdict, parseVerdict } from '@/models/verdict';
import { conversationStarted } from './transparencySlice';

export interface VerdictState {
    verdicts: Verdict[];
}

const initialState: VerdictState = { verdicts: [] };

const verdictSlice = createSlice({
    name: 'verdict',
    initialState,
    reducers: {
        verdictLanded(state, action: PayloadAction<unknown>) {
            const verdict = parseVerdict(action.payload);
            if (!verdict) return;
            if (
                state.verdicts.some(
                    (landed) =>
                        landed.planId === verdict.planId && landed.stepId === verdict.stepId,
                )
            ) {
                return;
            }
            state.verdicts.push(verdict);
        },
    },
    extraReducers: (builder) => {
        builder.addCase(conversationStarted, () => initialState);
    },
});

export const { verdictLanded } = verdictSlice.actions;

export const selectVerdicts = (state: RootState): Verdict[] =>
    state.verdict?.verdicts ?? [];

export default verdictSlice.reducer;
