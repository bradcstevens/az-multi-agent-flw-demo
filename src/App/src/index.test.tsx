import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { TeamConfig } from './models/Team';

const TEAM = {
    id: 'team-1',
    team_id: 'circle-k-store-assistant',
    name: 'Circle K Frontline Store Assistant',
    description: 'Store operations support',
    status: 'visible',
    created: '2026-08-17T00:00:00Z',
    created_by: 'test',
    logo: '',
    plan: '',
    agents: [],
    starting_tasks: [
        {
            id: 'close-store',
            name: 'Close the store',
            prompt: 'How do I close the store?',
            created: '2026-08-17T00:00:00Z',
            creator: 'test',
            logo: '',
            lane: 'fast',
        },
    ],
} satisfies TeamConfig;

vi.mock('./hooks/useWebSocket', () => ({ useWebSocket: () => undefined }));

vi.mock('./store/TeamService', () => ({
    TeamService: {
        getUserTeams: vi.fn(),
        initializeTeam: vi.fn(),
        storageTeam: vi.fn(),
        clearStoredTeam: vi.fn(),
        getStoredTeam: vi.fn(() => null),
    },
}));

vi.mock('./api', () => {
    class APIService {
        getPlans = vi.fn(async () => []);
    }

    const apiService = new APIService() as APIService & {
        sendUserBrowserLanguage: ReturnType<typeof vi.fn>;
    };
    apiService.sendUserBrowserLanguage = vi.fn();

    return { APIService, apiService };
});

import { TeamService } from './store/TeamService';
import { apiService } from './api';

type Deferred<T> = {
    promise: Promise<T>;
    resolve: (value: T) => void;
};

const deferred = <T,>(): Deferred<T> => {
    let resolve: (value: T) => void = () => undefined;
    const promise = new Promise<T>((resolvePromise) => {
        resolve = resolvePromise;
    });
    return { promise, resolve };
};

describe('the bootstrap surface', () => {
    beforeEach(() => {
        document.body.innerHTML = '<div id="root"></div>';
        vi.stubGlobal(
            'matchMedia',
            vi.fn().mockReturnValue({
                matches: false,
                addEventListener: vi.fn(),
                removeEventListener: vi.fn(),
            }),
        );
        vi.mocked(TeamService.initializeTeam).mockReturnValue(new Promise(() => undefined) as never);
        vi.mocked(apiService.sendUserBrowserLanguage).mockReturnValue(new Promise(() => undefined));
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        vi.clearAllMocks();
        document.body.innerHTML = '';
    });

    it('opens the real home surface after its user-scoped roster resolves without waiting for the language report', async () => {
        const config = deferred<Response>();
        const user = deferred<Response>();
        const teams = deferred<typeof TEAM[]>();

        vi.mocked(TeamService.getUserTeams).mockReturnValue(teams.promise);
        vi.stubGlobal(
            'fetch',
            vi.fn((input: RequestInfo | URL) => {
                if (String(input) === '/config') {
                    return config.promise;
                }
                if (String(input) === '/.auth/me') {
                    return user.promise;
                }
                throw new Error(`Unexpected bootstrap request: ${input}`);
            }),
        );

        await act(async () => {
            await import('./index');
        });

        expect(
            await screen.findByRole('progressbar', { name: 'Starting the store assistant...' }),
        ).toBeInTheDocument();
        await waitFor(() =>
            expect(fetch).toHaveBeenCalledWith('/.auth/me'),
        );
        expect(apiService.getPlans).not.toHaveBeenCalled();

        await act(async () => {
            config.resolve(
                new Response(JSON.stringify({ API_URL: 'https://backend.example/api', ENABLE_AUTH: 'false' }), {
                    headers: { 'Content-Type': 'application/json' },
                }),
            );
        });

        expect(apiService.sendUserBrowserLanguage).not.toHaveBeenCalled();
        expect(
            screen.getAllByRole('progressbar', { name: 'Starting the store assistant...' }),
        ).toHaveLength(1);

        await act(async () => {
            teams.resolve([TEAM]);
        });
        expect(screen.queryByRole('button', { name: /close the store/i })).not.toBeInTheDocument();

        await act(async () => {
            user.resolve(
                new Response(JSON.stringify([{ user_claims: [] }]), {
                    headers: { 'Content-Type': 'application/json' },
                }),
            );
        });

        await waitFor(() =>
            expect(apiService.sendUserBrowserLanguage).toHaveBeenCalledOnce(),
        );

        const task = await screen.findByRole('button', { name: /close the store/i });
        expect(task).toBeEnabled();
        expect(
            screen.queryByRole('progressbar', { name: 'Starting the store assistant...' }),
        ).not.toBeInTheDocument();

        await userEvent.click(screen.getByRole('button', { name: 'New chat' }));
        expect(
            screen.queryByRole('progressbar', { name: 'Starting the store assistant...' }),
        ).not.toBeInTheDocument();
    });
});
