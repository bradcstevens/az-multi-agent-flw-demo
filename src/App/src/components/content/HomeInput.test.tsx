import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { Button } from '@fluentui/react-components';
import { Send } from '@/commonComponents/imports/bundleicons';
import { configureStore } from '@reduxjs/toolkit';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

vi.mock('../../store/TaskService', () => ({
    TaskService: { createPlan: vi.fn(), signInDevice: vi.fn() },
}));

import HomeInput from './HomeInput';
import { TaskService } from '../../store/TaskService';
import transparencyReducer from '@/store/slices/transparencySlice';
import progressReducer, { selectProgressNarration } from '@/store/slices/progressSlice';
import webSocketService from '@/store/WebSocketService';
import { WebsocketMessageType } from '@/models';
import { FakeSocket, frame } from '@/testing/fakeSocket';
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
        display_name: 'Clara Workman',
        role: 'Store associate, Store 223',
        facts: [{ label: 'PTO balance', value: '34.5 hours' }],
        note: 'Simulated associate record, authored for this walkthrough.',
    },
} as any;

const renderInput = (team: any = TEAM) => {
    const store = configureStore({
        reducer: { transparency: transparencyReducer, progress: progressReducer },
    });
    return {
        store,
        narration: () => selectProgressNarration(store.getState() as never),
        ...render(
            <Provider store={store}>
                <MemoryRouter>
                    <HomeInput selectedTeam={team} />
                </MemoryRouter>
            </Provider>,
        ),
    };
};

const ask = async (question: string) => {
    await userEvent.type(screen.getByRole('textbox'), question);
    await userEvent.click(screen.getByRole('button', { name: 'Send question' }));
};

beforeEach(() => {
    window.sessionStorage.clear();
    forgetSignedInDevice();
    FakeSocket.instances = [];
    webSocketService.disconnect();
    vi.stubGlobal('WebSocket', FakeSocket);
    window.appConfig = { API_URL: 'https://backend.example/api' } as never;
    createPlan.mockReset().mockResolvedValue({ plan_id: 'plan-1' } as any);
    signInDevice.mockReset().mockImplementation(async () => {
        rememberSignedInName('Clara Workman');
        return 'Clara Workman';
    });
});

describe('the door beside the refusal', () => {
    it('offers a way in alongside the refusal', async () => {
        // R5's boundary is meant to read as a door rather than a wall: the
        // refusal explains the policy, and the affordance beside it is the
        // licensing conversation the customer has been avoiding.
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');

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
        rememberSignedInName('Clara Workman');
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');

        await waitFor(() => expect(signedInName()).toBeNull());
    });

    it('answers the previously refused question on one tap', async () => {
        // The whole beat: refused, tap, answered — and never a keyboard, for
        // the reason the Rehearsed replies exist (#26). Re-typing the question
        // would put a typo between the presenter and the payoff.
        createPlan.mockRejectedValueOnce(REFUSAL).mockResolvedValueOnce(ANSWER);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        expect(await screen.findByTestId('personal-answer')).toHaveTextContent(
            '34.5 hours',
        );
        expect(createPlan.mock.calls[1][0]).toBe(
            'my name is Clara, how much PTO do I have?',
        );
    });

    it('signs in before re-asking, never the other way round', async () => {
        const order: string[] = [];
        signInDevice.mockImplementation(async () => {
            order.push('sign_in');
            rememberSignedInName('Clara Workman');
            return 'Clara Workman';
        });
        createPlan.mockImplementation(async () => {
            order.push('ask');
            throw REFUSAL;
        });
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        await waitFor(() => expect(order).toEqual(['ask', 'sign_in', 'ask']));
    });

    it('does not re-ask when the sign-in signed nobody in', async () => {
        // Fails closed. Re-asking anonymously would show the same refusal a
        // second time and read on stage as the tap having done nothing.
        signInDevice.mockResolvedValue(null);
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');
        await userEvent.click(await screen.findByTestId('sign-in-to-continue'));

        await waitFor(() => expect(createPlan).toHaveBeenCalledTimes(1));
    });

    it('takes the refusal off screen once the question is answered', async () => {
        createPlan.mockRejectedValueOnce(REFUSAL).mockResolvedValueOnce(ANSWER);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');
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
            'Clara Workman',
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

/**
 * The window between the response and the render (issue #63, ADR-021).
 *
 * `process_request` schedules `run_orchestration_task` as a detached task
 * *before* it returns the HTTP response, so everything the orchestration emits
 * from that moment is pushed at whatever socket exists — and
 * `send_status_update_async` drops it when there is none. Hanging the connect
 * off the chat page put the navigation, a mount and a second GET inside that
 * window, and the frames most likely to fall in it are the first agent's
 * `agent_message_streaming` header — the only signal in the system that names
 * *which* specialist took the question — and, on a short Fast lane answer,
 * `source_used` and `token_usage` too.
 *
 * There is deliberately no chat page anywhere in this tree. That is the claim:
 * the connect does not depend on one.
 */
describe('the socket the answer arrives on', () => {
    /**
     * What `send_status_update_async` does with a frame: push it to the socket
     * for this plan, or drop it in silence when there isn't one.
     */
    const backendPushes = (text: string): boolean => {
        const socket = FakeSocket.forPlan('plan-1')[0];
        if (!socket) return false;
        if (socket.readyState !== FakeSocket.OPEN) socket.open();
        socket.deliver(text);
        return true;
    };

    it('is open before any chat page has mounted', async () => {
        renderInput();

        await ask('how do I close the store?');

        await waitFor(() => expect(FakeSocket.forPlan('plan-1')).toHaveLength(1));
    });

    it('carries the frame that names the specialist rather than dropping it', async () => {
        // Raw wire text through the real service, per the #47 finding: a test
        // that hand-feeds the payload shape agrees with its own author and
        // cannot see this bug.
        const named: string[] = [];
        const unsub = webSocketService.on(
            WebsocketMessageType.AGENT_MESSAGE_STREAMING,
            (message: any) => named.push(message.data?.agent),
        );
        renderInput();

        await ask('how do I close the store?');
        const delivered = backendPushes(
            frame('agent_message_streaming', {
                agent_name: 'Troubleshooting Agent',
                content: 'Let me check the closing procedure.',
                is_final: false,
            }),
        );
        unsub();

        expect(delivered).toBe(true);
        expect(named).toEqual(['Troubleshooting Agent']);
    });

    it('is not opened for a question the gate refused', async () => {
        // A refusal costs no agent, no tokens and no plan, so there is no
        // orchestration to observe and nothing to connect to.
        createPlan.mockRejectedValue(REFUSAL);
        renderInput();

        await ask('my name is Clara, how much PTO do I have?');

        await screen.findByTestId('policy-block');
        expect(FakeSocket.instances).toHaveLength(0);
    });

    it('is not opened for an answer that never had a plan', async () => {
        createPlan.mockResolvedValue(ANSWER);
        renderInput();

        await ask('how much PTO do I have?');

        await screen.findByTestId('personal-answer');
        expect(FakeSocket.instances).toHaveLength(0);
    });
});

describe('the send control', () => {
    it('is named for what it does', () => {
        // WCAG 2.1 4.1.2. It is an icon and nothing else, so without a name a
        // screen reader announces the one control that asks the question as
        // "button".
        renderInput();

        expect(
            screen.getByRole('button', { name: 'Send question' }),
        ).toBeInTheDocument();
    });

    it('says it is unavailable while a question is in flight', async () => {
        // The only signal today is the input wrapper's `opacity: 0.3`, which a
        // screen reader cannot see, and a natively-disabled control leaves the
        // tab order entirely — so the one affordance that submits a question
        // vanishes rather than explaining itself.
        createPlan.mockReturnValue(new Promise(() => {}) as any);
        renderInput();

        await ask('how do I close the store?');

        const send = screen.getByRole('button', { name: 'Send question' });
        await waitFor(() => expect(send).toHaveAttribute('aria-disabled', 'true'));
        expect(send.tabIndex).not.toBe(-1);

        // Reachable, and inert when reached: `pointer-events: none` on the
        // wrapper stops a mouse, and nothing but the control itself stops a
        // keyboard.
        send.focus();
        await userEvent.keyboard('{Enter}');
        expect(createPlan).toHaveBeenCalledTimes(1);
    });

    it('is rendered as the primary action of the input', () => {
        // The stylesheet has always described a filled brand button that nobody
        // has seen: Fluent's `subtle` styling is injected after the imported
        // stylesheet and wins at equal specificity, so the surface's primary
        // action renders transparent with a grey glyph — wearing the disabled
        // state's clothes. Compared against Fluent's own buttons rather than
        // against a class name copied out of the implementation.
        renderInput();
        const rendered = new Set(
            screen.getByRole('button', { name: 'Send question' }).classList,
        );

        const fluentClasses = (appearance: 'primary' | 'subtle') => {
            const { container, unmount } = render(
                <Button appearance={appearance} icon={<Send />} aria-label="reference" />,
            );
            const classes = Array.from(
                container.querySelector('button')!.classList,
            );
            unmount();
            return classes;
        };

        expect(fluentClasses('primary').every((c) => rendered.has(c))).toBe(true);
        expect(fluentClasses('subtle').every((c) => rendered.has(c))).toBe(false);
    });

    it('is painted by Fluent alone, with no rule of ours for Fluent to override', () => {
        // The counterpart to the test above, and the half jsdom cannot see: a
        // declaration this project makes about the send control is a
        // declaration Fluent overrides, because griffel's styles are injected
        // after an imported stylesheet. A rule that silently does nothing is
        // the reason the next person will assume it works.
        renderInput();
        const send = screen.getByRole('button', { name: 'Send question' });

        for (const cls of Array.from(send.classList)) {
            for (const [file, declarations] of rulesNaming(cls)) {
                expect(
                    declarations,
                    `${file} paints .${cls}, which Fluent will override`,
                ).not.toMatch(/(^|[;{\s])(color|background-color|border)\s*:/);
            }
        }
    });
});

/** Every stylesheet rule in this project whose selector names `cls`, as [file, body]. */
const rulesNaming = (cls: string): [string, string][] => {
    const dir = join(__dirname, '..', '..', 'styles');
    const named = new RegExp(`\\.${cls}(?![\\w-])`);
    return readdirSync(dir)
        .filter((entry) => entry.endsWith('.css'))
        .flatMap((entry) => {
            // Comments first. These sheets carry long explanations of the rules
            // they deliberately *do not* declare, so a class named in prose was
            // read as part of the selector of whatever rule came next — and the
            // declarations of an unrelated rule were reported against it (#59).
            const css = readFileSync(join(dir, entry), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
            return Array.from(css.matchAll(/([^{}]+)\{([^{}]*)\}/g))
                .filter((rule) => named.test(rule[1]))
                .map((rule) => [entry, rule[2]] as [string, string]);
        });
};

/**
 * The **Progress narration** as the home surface arms it (issue #64, ADR-023).
 *
 * The two phases that happen before any chat page exists, which is exactly why
 * the phase is held in a slice: the story used to run backwards across this
 * navigation — *"Plan created — Fast lane"* here, then *"Loading plan data..."*
 * over *"Initializing AI agents..."* on the page that follows.
 */
describe('what the home surface says about a question it has just sent', () => {
    it('says nothing until a question has been asked', () => {
        const { narration } = renderInput();

        expect(narration()).toBeNull();
    });

    it('names the lane the router reported, in the Lane badge\'s own words', async () => {
        createPlan.mockResolvedValue({ plan_id: 'plan-1', lane: 'fast' } as never);
        const { narration } = renderInput();

        await ask('how do I close the store?');

        await waitFor(() => expect(narration()).toBe('Routed — Fast lane'));
    });

    it('holds the question being sent when the response reported no lane', async () => {
        // The router failing to say is not the router saying "fast". A lane
        // this surface invented would be the Lane badge's claim made by
        // something that never read the response.
        createPlan.mockResolvedValue({ plan_id: 'plan-1' } as never);
        const { narration } = renderInput();

        await ask('how do I close the store?');

        await waitFor(() => expect(narration()).toBe('Sending your question...'));
    });

    it('stops narrating a question the gate refused', async () => {
        // A refusal is an answer. Nothing is in flight behind it, and there is
        // no chat page to arrive at that could ever stop the narration.
        createPlan.mockRejectedValue(REFUSAL);
        const { narration } = renderInput();

        await ask('my name is Clara, how much PTO do I have?');

        await screen.findByTestId('policy-block');
        expect(narration()).toBeNull();
    });

    it('stops narrating a question answered without a plan', async () => {
        createPlan.mockResolvedValue(ANSWER);
        const { narration } = renderInput();

        await ask('how much PTO do I have?');

        await screen.findByTestId('personal-answer');
        expect(narration()).toBeNull();
    });

    it('stops narrating when no plan could be created at all', async () => {
        createPlan.mockResolvedValue({ plan_id: null } as never);
        const { narration } = renderInput();

        await ask('how do I close the store?');

        await waitFor(() => expect(narration()).toBeNull());
    });
});
