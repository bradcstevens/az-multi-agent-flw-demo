import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

import PlanPanelRight from './PlanPanelRight';
import transparencyReducer, {
    sourceUsedReceived,
    tokenUsageReceived,
} from '@/store/slices/transparencySlice';

const makeStore = () => configureStore({ reducer: { transparency: transparencyReducer } });

const planData = {
    plan: { id: 'plan-1' },
    team: {
        agents: [
            { input_key: '', type: '', name: 'ShiftTasksAgent', deployment_name: 'gpt-4.1-mini' },
        ],
    },
    messages: [],
    mplan: null,
    streaming_message: null,
} as any;

const renderPanel = (store = makeStore(), approvalRequest: any = null) =>
    render(
        <Provider store={store}>
            <PlanPanelRight
                planData={planData}
                loading={false}
                planApprovalRequest={approvalRequest}
            />
        </Provider>,
    );

describe('the plan surface with Plan review off', () => {
    it('shows the agent roster even though there is no plan to review', () => {
        // The Fast lane produces no plan object at all (ADR-013). The panel
        // used to bail out entirely on that, so the Agent Team was empty for
        // most of the walkthrough.
        renderPanel();

        expect(screen.getByTestId('agent-team-member-ShiftTasksAgent')).toBeInTheDocument();
    });

    it('says there is no plan rather than promising one that is not coming', () => {
        renderPanel();

        expect(screen.getByText(/No plan to review/i)).toBeInTheDocument();
    });

    it('shows the transparency rail, so the panels are reachable in the fast lane', () => {
        renderPanel();

        expect(screen.getByTestId('transparency-rail')).toBeInTheDocument();
        expect(screen.getByTestId('grounding-panel')).toBeInTheDocument();
        expect(screen.getByTestId('token-meter-panel')).toBeInTheDocument();
    });

    it('carries a token_usage signal all the way to the meter, model column included', () => {
        const store = makeStore();
        store.dispatch(
            tokenUsageReceived({
                agent_name: 'Shift Tasks Agent',
                executor_id: 'ShiftTasksAgent',
                input_tokens: 900,
                output_tokens: 100,
                total_tokens: 1000,
            }),
        );

        renderPanel(store);

        const row = screen.getByTestId('meter-row-ShiftTasksAgent');
        expect(row).toHaveTextContent('1,000');
        expect(row).toHaveTextContent('gpt-4.1-mini');
    });

    it('carries a source_used signal all the way to the Grounding panel', () => {
        const store = makeStore();
        store.dispatch(
            sourceUsedReceived({
                platform: 'Copilot Studio',
                source: 'Dataverse',
                agent_name: 'Store SOP Assistant',
                citations: [
                    {
                        position: 1,
                        name: 'SOP-102 Store Closing Procedure.docx',
                        snippet: 'Cash up the tills…',
                        url: null,
                    },
                ],
            }),
        );

        renderPanel(store);

        expect(screen.getByTestId('grounding-platform')).toHaveTextContent('Copilot Studio');
        expect(screen.getByText('SOP-102 Store Closing Procedure.docx')).toBeInTheDocument();
    });
});
