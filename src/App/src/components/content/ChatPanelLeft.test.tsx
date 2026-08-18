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
            expect(apiService.deleteChat).toHaveBeenCalledWith('session-shared'),
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
        /*
          `hidden: true` throughout this file's delete-all assertions. The
          chat-history drawer is opened modal here, and Fluent's modalizer
          marks every other root `isOthersAccessible: false` once it settles —
          which is after the awaits below on a slow runner and before them on a
          fast one. Without it "the dialog is gone" is also satisfied by a
          dialog that is merely trapped, so the assertion would pass for the
          wrong reason exactly when it matters.
        */
        await waitFor(() =>
            expect(
                screen.queryByRole('dialog', {
                    name: DELETE_ALL_CHATS_TITLE,
                    hidden: true,
                }),
            ).not.toBeInTheDocument(),
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
        // Found rather than read, and `hidden: true`: the chat-history drawer's
        // modalizer traps this dialog out of the accessibility tree once it
        // settles, which on a slow runner is before this line.
        expect(
            await screen.findByRole('dialog', {
                name: DELETE_ALL_CHATS_TITLE,
                hidden: true,
            }),
        ).toBeInTheDocument();
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
        expect(
            screen.getByRole('dialog', {
                name: DELETE_ALL_CHATS_TITLE,
                hidden: true,
            }),
        ).toBeInTheDocument();
        expect(screen.getByText('offline')).toBeInTheDocument();
        expect(
            screen.getByRole('button', { name: /^The coffee machine/ }),
        ).toBeInTheDocument();
    });
});
