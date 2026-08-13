import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('../../store/TaskService', () => ({
    TaskService: { createPlan: vi.fn(), signInDevice: vi.fn() },
}));

import HomeInput from './HomeInput';
import { TaskService } from '../../store/TaskService';
import transparencyReducer from '@/store/slices/transparencySlice';
import { PolicyBlockError } from '../../api/policyBlock';
import { PERSONAL_ANSWER_KIND } from '../../models/personalAnswer';
import {
    forgetSignedInDevice,
    rememberSignedInName,
    signedInName,
} from '../../models/signedInDevice';

const createPlan = vi.mocked(TaskService.createPlan);
const signInDevice = vi.mocked(TaskService.signInDevice);

const TEAM = {
    team_id: 'x',
    name: 'Circle K Frontline Store Assistant',
    agents: [],
    starting_tasks: [],
} as any;

const REFUSAL = new PolicyBlockError({
    kind: 'policy_block',
    code: 'identity_boundary',
    message:
        'This assistant is set up for Store 223 rather than for individual associates.',
});

const ANSWER = {
    status: 'Answered from the associate\'s record',
    session_id: 'sid_1',
    plan_id: null,
    personal_answer: {
        kind: PERSONAL_ANSWER_KIND,
        display_name: 'Tanya Alvarez',
        role: 'Store associate, Store 223',
        facts: [{ label: 'PTO balance', value: '34.5 hours' }],
        note: 'Simulated associate record, authored for this walkthrough.',
    },
} as any;

const renderInput = (team: any = TEAM) =>
    render(
        <Provider store={configureStore({ reducer: { transparency: transparencyReducer } })}>
            <MemoryRouter>
                <HomeInput selectedTeam={team} />
            </MemoryRouter>
        </Provider>,
    );

const ask = async (question: string) => {
    await userEvent.type(screen.getByRole('textbox'), question);
    await userEvent.click(screen.getByRole('button', { name: '' }));
};

beforeEach(() => {
    window.sessionStorage.clear();
    forgetSignedInDevice();
    createPlan.mockReset().mockResolvedValue({ plan_id: 'plan-1' } as any);
    signInDevice.mockReset().mockImplementation(async () => {
        rememberSignedInName('Tanya Alvarez');
        return 'Tanya Alvarez';
    });
});

describe('the door beside the refusal', () => {
    it('offers a way in alongside the refusal', async () => {
        // R5's boundary is meant to read as a door rather than a wall: the
        // refusal explains the policy, and the affordance beside it is the
        // licensing conversation the customer has been avoiding.
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');

        expect(await screen.findByTestId('policy-block')).toBeInTheDocument();
        expect(screen.getByTestId('sign-in-to-continue')).toBeInTheDocument();
    });

    it('offers no way in when nothing has been refused', () => {
        renderInput();

        expect(screen.queryByTestId('sign-in-to-continue')).not.toBeInTheDocument();
    });

    it('forgets any signed-in associate when the gate refuses', async () => {
        // A refusal *is* the gate stating that nobody is signed in. A header
        // that went on naming an associate the gate has just declined to answer
        // for is the one thing no surface here may do.
        rememberSignedInName('Tanya Alvarez');
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');

        await waitFor(() => expect(signedInName()).toBeNull());
    });

    it('answers the previously refused question on one tap', async () => {
        // The whole beat: refused, tap, answered — and never a keyboard, for
        // the reason the Rehearsed replies exist (#26). Re-typing the question
        // would put a typo between the presenter and the payoff.
        createPlan.mockRejectedValueOnce(REFUSAL).mockResolvedValueOnce(ANSWER);
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        expect(await screen.findByTestId('personal-answer')).toHaveTextContent(
            '34.5 hours',
        );
        expect(createPlan.mock.calls[1][0]).toBe(
            'my name is Tanya, how much PTO do I have?',
        );
    });

    it('signs in before re-asking, never the other way round', async () => {
        const order: string[] = [];
        signInDevice.mockImplementation(async () => {
            order.push('sign_in');
            rememberSignedInName('Tanya Alvarez');
            return 'Tanya Alvarez';
        });
        createPlan.mockImplementation(async () => {
            order.push('ask');
            throw REFUSAL;
        });
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        await waitFor(() => expect(order).toEqual(['ask', 'sign_in', 'ask']));
    });

    it('does not re-ask when the sign-in signed nobody in', async () => {
        // Fails closed. Re-asking anonymously would show the same refusal a
        // second time and read on stage as the tap having done nothing.
        signInDevice.mockResolvedValue(null);
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        await waitFor(() => expect(createPlan).toHaveBeenCalledTimes(1));
    });

    it('takes the refusal off screen once the question is answered', async () => {
        createPlan.mockRejectedValueOnce(REFUSAL).mockResolvedValueOnce(ANSWER);
        renderInput();

        await ask('my name is Tanya, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        await waitFor(() =>
            expect(screen.queryByTestId('policy-block')).not.toBeInTheDocument(),
        );
        expect(screen.queryByTestId('sign-in-to-continue')).not.toBeInTheDocument();
    });
});

describe('the answered personal question', () => {
    it('renders the record where the refusal was', async () => {
        createPlan.mockResolvedValue(ANSWER);
        renderInput();

        await ask('how much PTO do I have?');

        expect(await screen.findByTestId('personal-answer')).toHaveTextContent(
            'Tanya Alvarez',
        );
    });

    it('never reads a plan-less answer as a failure to create a plan', async () => {
        // The answer costs no agent and no plan, exactly as the refusal did, so
        // it comes back with a null `plan_id`. Rendering that as "failed to
        // create plan" would turn the demo's payoff into an error toast.
        createPlan.mockResolvedValue(ANSWER);
        renderInput();

        await ask('how much PTO do I have?');

        await screen.findByTestId('personal-answer');
        expect(screen.queryByText(/failed to create plan/i)).not.toBeInTheDocument();
    });

    it('clears the answer when the next question is asked', async () => {
        // The record answers the question that was asked. Leaving it up beside
        // a store answer would claim it was part of that answer.
        createPlan.mockResolvedValueOnce(ANSWER).mockResolvedValueOnce({
            plan_id: 'plan-1',
        } as any);
        renderInput();

        await ask('how much PTO do I have?');
        await screen.findByTestId('personal-answer');
        await ask('how do I close the store?');

        await waitFor(() =>
            expect(screen.queryByTestId('personal-answer')).not.toBeInTheDocument(),
        );
    });
});

describe('the home surface', () => {
    it('never asks the associate to pick a team', () => {
        // The accelerator's empty state told the user to "select a team",
        // which is a routing decision presented as a precondition. With one
        // assistant there is nothing to select, so there is nothing to say.
        renderInput(null);

        expect(screen.queryByText(/select a team/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/for this team/i)).not.toBeInTheDocument();
    });

    it('says the assistant is not loaded rather than blaming the associate', () => {
        renderInput(null);

        expect(screen.getByTestId('assistant-unavailable')).toHaveTextContent(
            'Circle K Frontline Store Assistant',
        );
    });

    it('says nothing about availability once the assistant is loaded', () => {
        renderInput();

        expect(screen.queryByTestId('assistant-unavailable')).not.toBeInTheDocument();
    });
});
