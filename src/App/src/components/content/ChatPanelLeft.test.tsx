import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';

vi.mock('@/api', () => ({
    apiService: {
        getPlans: vi.fn().mockResolvedValue([]),
        deleteChat: vi.fn().mockResolvedValue({ status: 'deleted' }),
        deleteAllChats: vi.fn().mockResolvedValue({
            status: 'deleted',
            deleted_sessions: [],
            documents_deleted: 0,
            chats_kept_running: 0,
            chats_failed: 0,
        }),
    },
}));

import ChatPanelLeft from './ChatPanelLeft';
import ChatHistoryDrawerToggle from './ChatHistoryDrawerToggle';
import appReducer from '../../store/slices/appSlice';
import { ASSISTANT_NAME } from '../../models/storeSurface';
import panelDrawerReducer from '../../store/slices/panelDrawerSlice';
import {
    CHAT_HISTORY_DRAWER_TOGGLE_CLASS,
} from '../../models/panelDrawer';
import {
    allRulesIncludingMediaQueries,
    classesIn,
    stackingRules,
} from '../../testing/stylesheets';
import { apiService } from '@/api';
import { PlanStatus } from '../../models/enums';
import {
    CONFIRM_DELETE_ALL_LABEL,
    CONFIRM_DELETE_LABEL,
    DELETE_ALL_CHATS_LABEL,
    DELETE_ALL_CHATS_TITLE,
    DELETE_CHAT_LABEL,
    END_AND_DELETE_LABEL,
    chatMenuLabel,
} from '../../models/chatDeletion';
import type { Plan } from '../../models';

const renderPanel = (props: Record<string, unknown> = {}) =>
    render(
        <Provider
            store={configureStore({
                reducer: { app: appReducer, panelDrawer: panelDrawerReducer },
                preloadedState: { panelDrawer: { chatHistoryOpen: true } },
            })}
        >
            <MemoryRouter>
                <ChatPanelLeft
                    reloadChats={false}
                    {...props}
                />
            </MemoryRouter>
        </Provider>,
    );

const renderDrawer = () =>
    render(
        <Provider store={configureStore({ reducer: { app: appReducer, panelDrawer: panelDrawerReducer } })}>
            <MemoryRouter>
                <ChatHistoryDrawerToggle />
                <ChatPanelLeft
                    reloadChats={false}
                />
            </MemoryRouter>
        </Provider>,
    );

describe('the chat-history panel drawer', () => {
    afterEach(() => vi.unstubAllGlobals());

    it('opens over the conversation and Escape returns focus to its disclosure', async () => {
        renderDrawer();

        const toggle = screen.getByRole('button', { name: 'Chat history' });
        expect(toggle).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByRole('navigation', { name: 'Chat history' })).not.toBeInTheDocument();

        fireEvent.click(toggle);

        expect(await screen.findByRole('navigation', { name: 'Chat history' })).toBeInTheDocument();
        expect(toggle).toHaveAttribute('aria-expanded', 'true');

        fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });

        await waitFor(() =>
            expect(screen.queryByRole('navigation', { name: 'Chat history' })).not.toBeInTheDocument(),
        );
        await waitFor(() => expect(toggle).toHaveFocus());
    });

    it('releases every chat-history drawer rule at the stacking breakpoint', () => {
        const drawerRules = allRulesIncludingMediaQueries().filter((rule) =>
            classesIn(rule.selector).includes(CHAT_HISTORY_DRAWER_TOGGLE_CLASS),
        );

        expect(drawerRules.length, 'the drawer control has no stylesheet rule').toBeGreaterThan(0);
        expect(
            stackingRules().some(
                (rule) =>
                    classesIn(rule.selector).includes(CHAT_HISTORY_DRAWER_TOGGLE_CLASS) &&
                    /display:\s*none/.test(rule.body),
            ),
        ).toBe(true);
    });

    it('keeps chat history dropped below the stacking breakpoint', () => {
        vi.stubGlobal('matchMedia', () => ({
            matches: false,
            addEventListener: () => undefined,
            removeEventListener: () => undefined,
        }));

        render(
            <Provider
                store={configureStore({
                    reducer: { app: appReducer, panelDrawer: panelDrawerReducer },
                    preloadedState: { panelDrawer: { chatHistoryOpen: true } },
                })}
            >
                <MemoryRouter>
                    <ChatHistoryDrawerToggle />
                    <ChatPanelLeft reloadChats={false} />
                </MemoryRouter>
            </Provider>,
        );

        expect(screen.queryByRole('button', { name: 'Chat history' })).not.toBeInTheDocument();
        expect(screen.queryByRole('navigation', { name: 'Chat history' })).not.toBeInTheDocument();
    });
});

describe('the store surface has one assistant', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('is branded as the store assistant, not as the accelerator', async () => {
        renderPanel();

        expect(await screen.findByText(ASSISTANT_NAME)).toBeInTheDocument();
        expect(screen.queryByText(/contoso/i)).not.toBeInTheDocument();
    });

    it('offers no team picker, because the associate has no basis for the choice', async () => {
        // Routing between specialists is the orchestrator's job and the lane
        // router's job. Asking an associate mid-shift to pick a team makes a
        // decision they cannot make into a precondition of getting an answer.
        renderPanel();

        await waitFor(() => {
            expect(screen.queryByText(/current team/i)).not.toBeInTheDocument();
        });
        expect(screen.queryByRole('button', { name: /team/i })).not.toBeInTheDocument();
        expect(screen.queryByText(/select a team/i)).not.toBeInTheDocument();
    });

    it('offers no team upload either — a picker with one entry is still a picker', async () => {
        renderPanel();

        await screen.findByText(ASSISTANT_NAME);
        expect(screen.queryByText(/upload/i)).not.toBeInTheDocument();
    });
});


/*
  The walkthrough's centrepiece pair. ADR-024 has the escalation continue the
  troubleshooting turn's session, so these are two Plans and — per ADR-025 —
  one Chat.
*/
const TROUBLESHOOTING = {
    id: 'plan-troubleshooting',
    session_id: 'session-shared',
    timestamp: '2026-08-14T09:00:00Z',
    initial_goal: 'The coffee machine is showing an error',
    overall_status: PlanStatus.COMPLETED,
} as unknown as Plan;

const ESCALATION = {
    id: 'plan-escalation',
    session_id: 'session-shared',
    timestamp: '2026-08-14T09:20:00Z',
    initial_goal: "I can't fix it",
    overall_status: PlanStatus.COMPLETED,
} as unknown as Plan;

const HereIs = () => <span data-testid="here">{useLocation().pathname}</span>;

const renderPanelAt = (path: string) =>
    render(
        <Provider
            store={configureStore({
                reducer: { app: appReducer, panelDrawer: panelDrawerReducer },
                preloadedState: { panelDrawer: { chatHistoryOpen: true } },
            })}
        >
            <MemoryRouter initialEntries={[path]}>
                <HereIs />
                <Routes>
                    <Route
                        path="/chat/:id"
                        element={
                            <ChatPanelLeft
                                reloadChats={false}
                            />
                        }
                    />
                </Routes>
            </MemoryRouter>
        </Provider>,
    );

describe('one chat is one row', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            ESCALATION,
        ] as never);
    });

    it('renders the troubleshooting turn and its escalation as a single row', async () => {
        // Before #71 this rendered two rows carrying one `session_id` — and so
        // one React key — at the moment the demonstration makes its strongest
        // claim.
        const duplicateKeys = vi.spyOn(console, 'error').mockImplementation(() => undefined);

        renderPanelAt('/chat/plan-troubleshooting');

        expect(
            await screen.findByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /can't fix it/i })).not.toBeInTheDocument();
        expect(
            duplicateKeys.mock.calls.some((call) => String(call[0]).includes('same key')),
        ).toBe(false);

        duplicateKeys.mockRestore();
    });

    it('opens the chat where the conversation got to, so the escalation is reachable', async () => {
        renderPanelAt('/chat/plan-troubleshooting');

        fireEvent.click(await screen.findByRole('button', { name: /^The coffee machine/ }));

        await waitFor(() =>
            expect(screen.getByTestId('here')).toHaveTextContent('/chat/plan-escalation'),
        );
        expect(screen.queryByRole('navigation', { name: 'Chat history' })).not.toBeInTheDocument();
    });

    it('highlights the chat that is open, escalation included', async () => {
        renderPanelAt('/chat/plan-escalation');

        const row = await screen.findByRole('button', { name: /^The coffee machine/ });
        expect(row).toHaveClass('active');
    });

    it('highlights nothing when the open plan belongs to another chat', async () => {
        renderPanelAt('/chat/plan-somewhere-else');

        const row = await screen.findByRole('button', { name: /^The coffee machine/ });
        expect(row).not.toHaveClass('active');
    });
});

describe('the panel shows chats in every state', () => {
    /*
      #74. `GET /plans` filtered to `completed` and this panel rendered only the
      completed bucket, so a chat mid-escalation — a Chat whose latest plan is
      still running (#71) — was not on screen at all, and it is the chat most
      worth resuming.
    */
    const RUNNING_ESCALATION = {
        ...ESCALATION,
        overall_status: PlanStatus.IN_PROGRESS,
    } as unknown as Plan;

    const FAILED = {
        id: 'plan-failed',
        session_id: 'session-failed',
        timestamp: '2026-08-14T08:00:00Z',
        initial_goal: 'How do I swap a shift?',
        overall_status: PlanStatus.FAILED,
    } as unknown as Plan;

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            RUNNING_ESCALATION,
            FAILED,
        ] as never);
    });

    it('keeps a chat mid-escalation on screen', async () => {
        renderPanelAt('/chat/plan-troubleshooting');

        expect(
            await screen.findByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
    });

    it('shows a failed chat, so rehearsal debris is visible rather than lost', async () => {
        renderPanelAt('/chat/plan-troubleshooting');

        expect(
            await screen.findByRole('button', { name: /^How do I swap a shift/ }),
        ).toBeInTheDocument();
    });

    it('opens a chat that has not finished at the turn it got to', async () => {
        renderPanelAt('/chat/plan-troubleshooting');

        fireEvent.click(await screen.findByRole('button', { name: /^The coffee machine/ }));

        await waitFor(() =>
            expect(screen.getByTestId('here')).toHaveTextContent('/chat/plan-escalation'),
        );
    });
});

/*
  The delete-all confirmation is asked for by the text of its title, never by a
  role query.

  #130's chat-history drawer is an `OverlayDrawer`, and tabster makes it a
  trapped modalizer. These tests open the confirmation with `fireEvent`, which
  never moves focus, so the dialog's own modalizer never becomes the active one
  and tabster's sweep marks the dialog's portal `aria-hidden="true"`. That
  sweep lands after these assertions on a developer's machine and before them
  on the runner, which is the whole of the difference between this file passing
  locally and failing in CI.

  Once the sweep has landed no role query can reach it. `hidden: true` gets the
  element back — but `computeAccessibleName` returns `''` for anything inside
  an aria-hidden subtree, so a `name` filter matches nothing. Measured here
  rather than assumed, and the reason 933daa12's `hidden: true` fix did not
  work either: the confirmation was never absent from the DOM, it was nameless
  in the accessibility tree.

  A text query does not consult that tree. Fluent unmounts a closed Dialog's
  surface, so the title being in the document is exactly the confirmation being
  open — mutation-checked by letting a sweep succeed, which closes it and fails
  every assertion below.
*/
const deleteAllConfirmation = () => screen.queryByText(DELETE_ALL_CHATS_TITLE);

const findDeleteAllConfirmation = () => screen.findByText(DELETE_ALL_CHATS_TITLE);

describe('deleting a chat from the panel', () => {
    /*
      #75 / ADR-026. The panel owns the request, the reload and the navigation:
      the list can only say a row was confirmed. Chat deletion is
      session-scoped, so what goes is `session_id` — never the plan id the row
      carries to open with.
    */
    const FINISHED_ELSEWHERE = {
        id: 'plan-other',
        session_id: 'session-other',
        timestamp: '2026-08-14T07:00:00Z',
        initial_goal: 'How do I swap a shift?',
        overall_status: PlanStatus.COMPLETED,
    } as unknown as Plan;

    /*
      The row #122 exists for: a turn destroyed by a walk-away leaves the Plan
      record at `in_progress` for ever, and until the door there was no exposed
      route that could clear it.
    */
    const STILL_RUNNING = {
        id: 'plan-running',
        session_id: 'session-running',
        timestamp: '2026-08-14T10:00:00Z',
        initial_goal: 'How do I close the store?',
        overall_status: PlanStatus.IN_PROGRESS,
    } as unknown as Plan;

    const deleteChat = async (name: string) => {
        fireEvent.click(
            await screen.findByRole('button', { name: chatMenuLabel(name) }),
        );
        fireEvent.click(screen.getByRole('menuitem', { name: DELETE_CHAT_LABEL }));
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );
    };

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            ESCALATION,
            FINISHED_ELSEWHERE,
        ] as never);
        vi.mocked(apiService.deleteChat).mockResolvedValue({
            status: 'deleted',
            session_id: 'session-shared',
            documents_deleted: 7,
        } as never);
    });

    it('deletes the chat‘s session, not the plan the row opens', async () => {
        // The row carries its latest plan's id (#71) and that is what a delete
        // reading the wrong field would send — taking one turn of the
        // conversation and leaving the rest of it in Cosmos.
        renderPanelAt('/chat/plan-troubleshooting');

        await deleteChat('The coffee machine is showing an error');

        await waitFor(() =>
            expect(apiService.deleteChat).toHaveBeenCalledWith('session-shared', false),
        );
    });

    it('asks nothing of a turn a settled row never claimed to be running', async () => {
        // The ask is what the confirmation promised, and a settled chat's
        // confirmation promised nothing about a turn. Sent anyway it would end
        // a turn that started after this list was read.
        renderPanelAt('/chat/plan-troubleshooting');

        await deleteChat('How do I swap a shift?');

        await waitFor(() =>
            expect(apiService.deleteChat).toHaveBeenCalledWith('session-other', false),
        );
    });

    it('asks for the turn to be ended when the row it offered was running', async () => {
        /*
          #122, ADR-031 §5. The associate confirmed a dialog that said the turn
          ends first, and the request carries that ask — which is the whole of
          the trigger. No heuristic about abandonment lives at either end of
          it, and the route's fail-closed guard is untouched: what changes is
          that the record reaches a **Settled status** before the sweep reads
          it.
        */
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            STILL_RUNNING,
        ] as never);
        renderPanelAt('/chat/plan-troubleshooting');

        fireEvent.click(
            await screen.findByRole('button', {
                name: chatMenuLabel('How do I close the store?'),
            }),
        );
        fireEvent.click(screen.getByRole('menuitem', { name: DELETE_CHAT_LABEL }));
        fireEvent.click(
            await screen.findByRole('button', { name: END_AND_DELETE_LABEL }),
        );

        await waitFor(() =>
            expect(apiService.deleteChat).toHaveBeenCalledWith('session-running', true),
        );
    });

    it('reads the history again after a delete', async () => {
        renderPanelAt('/chat/plan-escalation');
        await screen.findByRole('button', { name: /^How do I swap a shift/ });

        await deleteChat('How do I swap a shift?');

        // Forced, not cached. `getPlans`'s second argument is `useCache`, and
        // the panel's own cached list is the one way a deleted row comes back.
        await waitFor(() =>
            expect(apiService.getPlans).toHaveBeenCalledWith(undefined, false),
        );
    });

    it('takes the row even when the history does not come back', async () => {
        /*
          Found by review. `loadPlansData` swallows its own failure into
          `plansError`, so a panel that waited for the re-read to remove the row
          would keep listing a conversation it has just reported gone — with the
          confirmation already closed, and nothing on screen to say why.

          Deletes a chat other than the open one deliberately: deleting the open
          one navigates away and unmounts the panel, which would make any
          assertion about its rows pass for the wrong reason.
        */
        renderPanelAt('/chat/plan-escalation');
        await screen.findByRole('button', { name: /^How do I swap a shift/ });
        vi.mocked(apiService.getPlans).mockRejectedValue(new Error('offline'));

        await deleteChat('How do I swap a shift?');

        /*
          Waited on the re-read rather than on the row: a modal confirmation
          hides the rest of the tree from `getByRole` while it is open, so a
          bare `waitFor` for the row's absence passes on the dialog and never
          observes the panel at all.
        */
        await waitFor(() => expect(apiService.getPlans).toHaveBeenCalledTimes(2));
        await waitFor(() =>
            expect(deleteAllConfirmation()).not.toBeInTheDocument(),
        );
        /*
          The re-read's rejection is swallowed a tick after the call count
          rises, so the row leaves on a later render than the one `getPlans`
          resolves on. Waited rather than read once: the dialog check above has
          already established the panel is what `queryByRole` can see.
        */
        await waitFor(() =>
            expect(
                screen.queryByRole('button', { name: /^How do I swap a shift/ }),
            ).not.toBeInTheDocument(),
        );
        expect(
            screen.getByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
    });

    it('leaves a conversation it has just destroyed', async () => {
        // The page is rendering a plan that no longer exists. Staying put
        // would leave the presenter looking at a transcript of something the
        // surface has just said is gone.
        renderPanelAt('/chat/plan-escalation');
        vi.mocked(apiService.getPlans).mockResolvedValue([
            FINISHED_ELSEWHERE,
        ] as never);

        await deleteChat('The coffee machine is showing an error');

        // Anchored: a plain '/' is a substring of the pathname we started on,
        // so it would be satisfied before the navigation had happened at all.
        await waitFor(() => expect(screen.getByTestId('here')).toHaveTextContent(/^\/$/));
        expect(screen.getByTestId('here')).not.toHaveTextContent('plan-escalation');
    });

    it('stays where it is when the chat deleted is a different one', async () => {
        renderPanelAt('/chat/plan-escalation');
        await screen.findByRole('button', { name: /^How do I swap a shift/ });

        await deleteChat('How do I swap a shift?');

        await waitFor(() => expect(apiService.deleteChat).toHaveBeenCalled());
        expect(screen.getByTestId('here')).toHaveTextContent('/chat/plan-escalation');
    });

    it('keeps the chat on screen when the delete was refused', async () => {
        // A 409 for a running chat, or a partial sweep. Either way the
        // conversation is still in Cosmos, and a row that vanished optimistically
        // would be the panel saying something that is not so.
        vi.mocked(apiService.deleteChat).mockRejectedValue(new Error('conflict'));
        renderPanelAt('/chat/plan-escalation');

        await deleteChat('The coffee machine is showing an error');

        await waitFor(() => expect(apiService.deleteChat).toHaveBeenCalled());
        expect(
            screen.getByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
        expect(screen.getByTestId('here')).toHaveTextContent('/chat/plan-escalation');
    });
});

describe('deleting every chat from the panel (#76)', () => {
    /*
      The list-level control, ADR-026 applied to the whole history rather
      than one row. A running chat is kept by the same fail-closed rule the
      single delete uses, and the panel has to say so rather than let the row
      just vanish from the count.
    */
    const RUNNING = {
        id: 'plan-running',
        session_id: 'session-running',
        timestamp: '2026-08-14T06:00:00Z',
        initial_goal: 'Ordering more coffee filters',
        overall_status: PlanStatus.IN_PROGRESS,
    } as unknown as Plan;

    const openDeleteAllDialog = async () => {
        fireEvent.click(
            await screen.findByRole('button', { name: DELETE_ALL_CHATS_LABEL }),
        );
    };

    const confirmDeleteAll = async () => {
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_ALL_LABEL }),
        );
    };

    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(apiService.getPlans).mockResolvedValue([
            TROUBLESHOOTING,
            ESCALATION,
            RUNNING,
        ] as never);
        vi.mocked(apiService.deleteAllChats).mockResolvedValue({
            status: 'deleted',
            deleted_sessions: ['session-shared'],
            documents_deleted: 7,
            chats_kept_running: 1,
            chats_failed: 0,
        } as never);
    });

    it('is disabled when nothing on screen can be deleted', async () => {
        vi.mocked(apiService.getPlans).mockResolvedValue([RUNNING] as never);
        renderPanelAt('/chat/plan-running');

        expect(
            await screen.findByRole('button', { name: DELETE_ALL_CHATS_LABEL }),
        ).toBeDisabled();
    });

    it("states how many chats the sweep will take, in the confirmation", async () => {
        renderPanelAt('/chat/plan-troubleshooting');
        await screen.findByRole('button', { name: /^The coffee machine/ });

        await openDeleteAllDialog();

        // Two settled chats share one session (`session-shared`); the running
        // one is not offered up as part of the count.
        expect(await screen.findByText(/deletes 1 chat\b/)).toBeInTheDocument();
    });

    it('reads the history again and clears the deleted rows after a sweep', async () => {
        renderPanelAt('/chat/plan-somewhere-else');
        await screen.findByRole('button', { name: /^The coffee machine/ });
        vi.mocked(apiService.getPlans).mockResolvedValue([RUNNING] as never);

        await openDeleteAllDialog();
        await confirmDeleteAll();

        await waitFor(() => expect(apiService.deleteAllChats).toHaveBeenCalledWith());
        await waitFor(() =>
            expect(
                screen.queryByRole('button', { name: /^The coffee machine/ }),
            ).not.toBeInTheDocument(),
        );
        expect(
            await screen.findByRole('button', { name: /^Ordering more coffee filters/ }),
        ).toBeInTheDocument();
    });

    it('leaves the open conversation once its chat has gone', async () => {
        renderPanelAt('/chat/plan-troubleshooting');
        await screen.findByRole('button', { name: /^The coffee machine/ });

        await openDeleteAllDialog();
        await confirmDeleteAll();

        await waitFor(() => expect(screen.getByTestId('here')).toHaveTextContent(/^\/$/));
    });

    it('names the one chat a sweep kept running, rather than only counting it', async () => {
        renderPanelAt('/chat/plan-somewhere-else');
        await screen.findByRole('button', { name: /^The coffee machine/ });
        vi.mocked(apiService.deleteAllChats).mockResolvedValue({
            status: 'deleted',
            deleted_sessions: ['session-shared'],
            documents_deleted: 7,
            chats_kept_running: 1,
            chats_failed: 0,
        } as never);

        await openDeleteAllDialog();
        await confirmDeleteAll();

        expect(
            await screen.findByText(/Ordering more coffee filters.*kept/i),
        ).toBeInTheDocument();
    });

    it('does not report a partly-finished sweep as a cleared list', async () => {
        /*
          Found by review. The route answers 200 with `status: "incomplete"`
          and a count of the chats it could not take — a chat left in Cosmos
          under a control that said it cleared the list. The panel read
          neither, closed the dialog, and said nothing.
        */
        renderPanelAt('/chat/plan-somewhere-else');
        await screen.findByRole('button', { name: /^The coffee machine/ });
        vi.mocked(apiService.deleteAllChats).mockResolvedValue({
            status: 'incomplete',
            deleted_sessions: [],
            documents_deleted: 2,
            chats_kept_running: 0,
            chats_failed: 1,
        } as never);

        await openDeleteAllDialog();
        await confirmDeleteAll();

        expect(
            await screen.findByText(/1 chat could not be deleted/i),
        ).toBeInTheDocument();
        expect(await findDeleteAllConfirmation()).toBeInTheDocument();
    });

    it('still names a chat it kept running when the same sweep also failed', async () => {
        // Two different sentences: one chat was refused because it is live,
        // another could not be taken at all. Reporting only the failure would
        // leave the running chat's row unexplained.
        renderPanelAt('/chat/plan-somewhere-else');
        await screen.findByRole('button', { name: /^The coffee machine/ });
        vi.mocked(apiService.deleteAllChats).mockResolvedValue({
            status: 'incomplete',
            deleted_sessions: [],
            documents_deleted: 0,
            chats_kept_running: 1,
            chats_failed: 1,
        } as never);

        await openDeleteAllDialog();
        await confirmDeleteAll();

        expect(
            await screen.findByText(/1 chat could not be deleted/i),
        ).toBeInTheDocument();
        expect(
            await screen.findByText(/Ordering more coffee filters.*kept/i),
        ).toBeInTheDocument();
    });

    it('keeps the confirmation open and says why when the sweep is refused', async () => {
        vi.mocked(apiService.deleteAllChats).mockRejectedValue(new Error('offline'));
        renderPanelAt('/chat/plan-troubleshooting');
        await screen.findByRole('button', { name: /^The coffee machine/ });

        await openDeleteAllDialog();
        await confirmDeleteAll();

        await waitFor(() => expect(apiService.deleteAllChats).toHaveBeenCalled());
        expect(deleteAllConfirmation()).toBeInTheDocument();
        expect(screen.getByText('offline')).toBeInTheDocument();
        expect(
            screen.getByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
    });
});

/**
 * How tall the chat list is allowed to be (#178).
 *
 * Asserted **here**, where the panel renders whole, rather than beside the list
 * component. `.panelLeft .fui-AccordionPanel { max-height: 280px }` is a rule
 * about this list written the way this repository writes rules — scoped under a
 * class of ours — and a render with no panel around the list cannot see it: the
 * selector matches nothing, so the rule is never loaded and never reported. The
 * production ancestors are the point, so the production component is what gets
 * rendered.
 *
 * jsdom has no layout engine, so a hidden row is not observable. What *is*
 * observable is what the engine computed, and that is what this asks. Three
 * earlier versions parsed the stylesheets by hand and each review found another
 * hole in the parser rather than in the surface — `:is()`'s commas split into
 * invalid fragments, `var()` read as a literal, an unparseable selector treated
 * as no match, an inline `maxBlockSize` unrecognised beside `maxHeight`. All of
 * that is the engine's job, so the engine does it.
 *
 * Media-query rules are flattened in deliberately: below the **Stacking
 * breakpoint** this panel is not rendered at all, so a rule capping the list
 * there is dead code claiming to be a layout.
 */
describe("the chat list's height", () => {
    const A_MORNING_OF_CHATS = Array.from({ length: 12 }, (_, i) => ({
        id: `plan-${i}`,
        session_id: `session-${i}`,
        timestamp: `2026-08-14T09:${String(i).padStart(2, '0')}:00Z`,
        initial_goal: `Rehearsal question ${i}`,
        overall_status: PlanStatus.COMPLETED,
    })) as unknown as Plan[];

    /** A rule worth loading: one that could bound a box or scroll it. */
    const SIZES_OR_SCROLLS =
        /(?:^|[;{\s])(?:(?:max-)?(?:height|block-size)|overflow(?:-y|-block)?)\s*:/i;

    /**
     * The elements between the panel's scroll region and a chat row, taken from
     * the DOM the panel actually produces.
     *
     * Read rather than listed because the containers are not all ours: Fluent's
     * `Accordion`, `AccordionItem` and `AccordionPanel` sit between our
     * container and our rows, and it was `.fui-AccordionPanel` — a class no
     * source file in this repository contains — that carried the cap.
     *
     * The walk stops **below** `.panelContent`, and that boundary is the whole
     * claim rather than a detail: `.panelContent` is the panel's own scroll
     * region, the thing this list is supposed to be bounded by and scroll
     * inside. Walking through it reported the panel scrolling as though the
     * list had opened a second scrollbar, which is the opposite of what this
     * ticket is about.
     */
    const SCROLL_REGION = 'panelContent';

    const listContainers = async (): Promise<HTMLElement[]> => {
        vi.mocked(apiService.getPlans).mockResolvedValue(A_MORNING_OF_CHATS as never);
        renderPanel();

        const row = await screen.findByRole('button', { name: /^Rehearsal question 0/ });
        const containers: HTMLElement[] = [];

        for (
            let node = row.parentElement;
            node !== null && !node.classList.contains(SCROLL_REGION);
            node = node.parentElement
        ) {
            containers.push(node);
        }

        return containers;
    };

    /** The panel's own scroll region, which is what the list is bounded by. */
    const scrollRegion = (): HTMLElement =>
        document.querySelector(`.${SCROLL_REGION}`) as HTMLElement;

    /**
     * The surface's own rules, in the document, for the containers they apply
     * to — so the engine resolves them and this suite only reads the answer.
     *
     * One rule at a time rather than one sheet: jsdom rejects a *stylesheet*
     * wholesale when any rule in it defeats its parser, and written as a single
     * `<style>` the entire surface silently failed to load behind a green
     * assertion. One at a time, a rule it cannot parse is one rule, and it is
     * returned rather than swallowed.
     */
    const loadRulesFor = (
        containers: HTMLElement[],
    ): { unload: () => void; unreadable: string[]; declarations: CSSStyleDeclaration[] } => {
        const applies = (selector: string): boolean => {
            try {
                // Selector lists are handed over whole: `matches` understands
                // `.a, .b`, and splitting on commas is what broke `:is(a, b)`.
                return containers.some((container) => container.matches(selector));
            } catch {
                // A selector this engine cannot parse cannot be ruled out.
                return true;
            }
        };

        const injected: HTMLStyleElement[] = [];
        const unreadable: string[] = [];
        const declarations: CSSStyleDeclaration[] = [];

        for (const rule of allRulesIncludingMediaQueries()) {
            if (!SIZES_OR_SCROLLS.test(rule.body)) continue;
            if (!applies(rule.selector)) continue;

            const style = document.createElement('style');
            style.textContent = `${rule.selector}{${rule.body}}`;
            document.head.appendChild(style);
            injected.push(style);

            const parsed = style.sheet?.cssRules[0] as CSSStyleRule | undefined;
            if (parsed === undefined) unreadable.push(`${rule.file}: ${rule.selector}`);
            else declarations.push(parsed.style);
        }

        return {
            unload: () => injected.forEach((style) => style.remove()),
            unreadable,
            declarations,
        };
    };

    /*
      What these containers may say about their own size, which is nothing.

      The rule is deliberately stricter than "no `max-height: 280px`", because
      two rounds of this ticket were spent discovering that the defect has more
      than one spelling. `height: 100%` with `overflow-y: hidden` sizes the list
      to the panel and then clips the rows that do not fit — every chat past the
      fifth gone, with no scrollbar even to hint at them, which is worse than the
      rule this ticket deleted. `max-height: 100%` is the same defect with a
      percentage. And `overflow-y: var(--x)` cannot be read at all here, because
      this engine does not resolve custom properties.

      Between the panel's scroll region and a row there is nothing to decide: the
      height belongs to the panel and the scrolling belongs to the panel. So any
      height and any overflow on these containers is reported, and the only free
      values are the ones that mean "I said nothing". A container that genuinely
      needs to size itself can have this conversation in a review, which is
      exactly where it belongs.

      Physical and logical spellings both, because an element can be given
      either and the engine reports what it was given.
    */
    const HEIGHTS = ['height', 'max-height', 'block-size', 'max-block-size'];
    const SCROLLERS = ['overflow', 'overflow-y', 'overflow-block'];

    const SAYS_NOTHING = ['', 'auto', 'none', 'initial', 'unset', 'revert'];
    const NOT_A_SCROLL_REGION = ['', 'visible', 'initial', 'unset', 'revert'];

    /*
      Read with `getPropertyValue` and the CSS spelling of the property, which
      is the one accessor that answers for both a rule's declarations and an
      element's computed style. The camel-case properties are `undefined` on a
      `CSSStyleRule`'s declarations for the logical spellings, and an
      `undefined` compared against a list of allowed values reads as a finding —
      seven of them, all invented.
    */
    const valueOf = (style: CSSStyleDeclaration, property: string): string =>
        style.getPropertyValue(property).trim();

    const boundsIn = (style: CSSStyleDeclaration): string[] =>
        HEIGHTS.filter((property) => !SAYS_NOTHING.includes(valueOf(style, property))).map(
            (property) => `${property}: ${valueOf(style, property)}`,
        );

    const scrollsIn = (style: CSSStyleDeclaration): string[] =>
        SCROLLERS.filter(
            (property) => !NOT_A_SCROLL_REGION.includes(valueOf(style, property)),
        ).map((property) => `${property}: ${valueOf(style, property)}`);

    const describeElement = (element: HTMLElement): string =>
        `${element.tagName.toLowerCase()}.${Array.from(element.classList).join('.')}`;

    it('is bounded by the panel it sits in, not by anything of its own', async () => {
        /*
          The defect: `max-height: 280px` with its own `overflow-y: auto` put
          five rows on screen and the rest behind a scrollbar *inside* a panel
          that is already the height of the surface and already scrolls — #60's
          "content hidden behind a second scrollbar", in the column on the other
          edge.
        */
        const containers = await listContainers();
        const { unload, unreadable } = loadRulesFor(containers);

        try {
            expect(
                unreadable,
                `${unreadable.join(', ')} applies to the chat list and could not be read`,
            ).toEqual([]);

            for (const container of containers) {
                expect(
                    boundsIn(getComputedStyle(container)),
                    `${describeElement(container)} bounds the chat list's height`,
                ).toEqual([]);
                expect(
                    scrollsIn(getComputedStyle(container)),
                    `${describeElement(container)} opens a scroll region inside the panel`,
                ).toEqual([]);
            }
        } finally {
            unload();
        }
    });

    it('declares no such bound either, whatever the cascade settles on', async () => {
        /*
          The criterion is that the list *declares* no height of its own, and a
          computed value is the winner of an argument rather than the argument.
          A cap declared and then reset — or one whose reset lives in a query
          that does not apply — leaves the forbidden declaration in the
          stylesheet and this panel one edit from showing five chats again.

          Read off the CSSOM rather than parsed here, so it is still the engine
          saying what the rule declares.
        */
        const containers = await listContainers();
        const { unload, declarations } = loadRulesFor(containers);

        try {
            const declared = declarations.flatMap((style) => [
                ...boundsIn(style),
                ...scrollsIn(style),
            ]);

            expect(
                declared,
                `${declared.join(', ')} is declared for a container of the chat list`,
            ).toEqual([]);
        } finally {
            unload();
        }
    });

    it('would say so if the rule came back, however it were scoped', async () => {
        /*
          The guard, proved rather than trusted. The assertions above are "no
          container is bounded", which is also what a guard that has stopped
          looking says — and it *had* stopped looking once: loaded as one sheet,
          jsdom rejected the surface's whole stylesheet over one nested rule in
          `Chat.css` and everything passed against no styles at all.

          Both shapes go back. The unscoped one is how the rule was actually
          written; the panel-scoped one is how it would be written by someone
          following this repository's own convention, and it is invisible to any
          suite that renders the list without its panel.
        */
        const containers = await listContainers();
        const { unload } = loadRulesFor(containers);

        const unscoped = document.createElement('style');
        unscoped.textContent =
            '.fui-AccordionPanel { max-height: 280px !important; overflow-y: auto !important; }';
        const scoped = document.createElement('style');
        scoped.textContent = '.panelLeft .fui-AccordionPanel { max-block-size: 240px; }';

        try {
            const panel = containers.find((element) =>
                element.classList.contains('fui-AccordionPanel'),
            ) as HTMLElement;

            expect(panel, 'the Fluent accordion panel no longer holds the rows').toBeDefined();

            document.head.appendChild(unscoped);
            expect(boundsIn(getComputedStyle(panel))).toContain('max-height: 280px');
            expect(scrollsIn(getComputedStyle(panel))).toContain('overflow-y: auto');
            unscoped.remove();

            document.head.appendChild(scoped);
            expect(boundsIn(getComputedStyle(panel))).toContain('max-block-size: 240px');
        } finally {
            unscoped.remove();
            scoped.remove();
            unload();
        }
    });

    it('reads the surface it thinks it is reading', async () => {
        /*
          That this loader really pulls rules out of the repository's own
          stylesheets and gets them applying, rather than quietly loading
          nothing and reporting a clean list. `.panelLeft` declares `height:
          100%` in `ChatPanelLeft.css` and is one of the containers walked, so
          the proof needs nothing invented.
        */
        const containers = await listContainers();
        const panel = document.querySelector('.panelLeft') as HTMLElement;
        const { unload } = loadRulesFor([...containers, panel]);

        try {
            const classes = containers.flatMap((element) => Array.from(element.classList));

            expect(classes).toContain('task-list-container');
            expect(
                classes.some((className) => /^fui-Accordion/.test(className)),
                'the Fluent accordion is no longer between the list and its rows',
            ).toBe(true);

            // The boundary the walk stops at exists, and is the panel's own.
            expect(scrollRegion(), 'the panel has no scroll region for the list to sit in').not.toBeNull();
            expect(classes).not.toContain(SCROLL_REGION);
            expect(scrollsIn(getComputedStyle(scrollRegion()))).toContain('overflow-y: auto');

            // And the repository's own CSS is what is being read: `.panelLeft`
            // takes its height from `ChatPanelLeft.css` and from nothing here.
            expect(
                valueOf(getComputedStyle(panel), 'height'),
                "the surface's own stylesheets are not reaching the rendered panel",
            ).toBe('100%');
        } finally {
            unload();
        }
    });
});
