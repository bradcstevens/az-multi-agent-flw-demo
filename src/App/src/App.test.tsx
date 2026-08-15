import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router-dom';

/*
  The route table, and nothing else. The pages are stubbed because what is
  being asked here is which path reaches which screen — a question the real
  HomePage and ChatPage answer by fetching plans and opening sockets.
*/
vi.mock('./pages', () => ({
    HomePage: () => <span data-testid="home" />,
    ChatPage: () => <span data-testid="chat" />,
}));

vi.mock('./hooks/useWebSocket', () => ({ useWebSocket: () => undefined }));

vi.mock('./store/hooks', () => ({ useAppDispatch: () => vi.fn() }));

vi.mock('./api/config', () => ({ getUserInfoGlobal: () => null }));

vi.mock('./App.css', () => ({}));

import App from './App';

const Here = () => <span data-testid="here">{useLocation().pathname}</span>;

vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual<typeof import('react-router-dom')>(
        'react-router-dom',
    );
    return {
        ...actual,
        BrowserRouter: ({ children }: { children: React.ReactNode }) => (
            <actual.BrowserRouter>
                <Here />
                {children}
            </actual.BrowserRouter>
        ),
    };
});

const openAt = (path: string) => {
    window.history.pushState({}, '', path);
    return render(<App />);
};

describe('the conversation route', () => {
    it('is /chat/:id, because a Chat is the unit of the surface', async () => {
        openAt('/chat/plan-troubleshooting');

        expect(await screen.findByTestId('chat')).toBeInTheDocument();
    });

    it('still answers the path the presenter has open from before the rename', async () => {
        // ADR-025 renamed the surface, not the demonstration in progress. The
        // catch-all below the route table sends anything unmatched to the home
        // screen, so a `/plan/<id>` in a tab or in history would lose the
        // conversation being shown rather than 404 visibly.
        openAt('/plan/plan-troubleshooting');

        await waitFor(() =>
            expect(screen.getByTestId('here')).toHaveTextContent(
                '/chat/plan-troubleshooting',
            ),
        );
        expect(screen.getByTestId('chat')).toBeInTheDocument();
    });
});
