import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./apiClient', () => ({
    apiClient: {
        post: vi.fn(),
        delete: vi.fn(),
    },
}));

import { apiClient } from './apiClient';
import { APIService } from './apiService';

describe('ending a Chat turn', () => {
    beforeEach(() => {
        vi.mocked(apiClient.post).mockReset().mockResolvedValue({
            status: 'ended',
            session_id: 'session / 223',
            cancelled: true,
        });
    });

    it('posts the session-scoped end-turn request', async () => {
        const result = await new APIService().endChatTurn('session / 223');

        expect(result).toEqual({
            status: 'ended',
            session_id: 'session / 223',
            cancelled: true,
        });
        expect(apiClient.post).toHaveBeenCalledWith(
            '/v4/chats/session%20%2F%20223/end_turn',
        );
        expect(apiClient.post).toHaveBeenCalledTimes(1);
    });
});

describe('deleting a Chat', () => {
    beforeEach(() => {
        vi.mocked(apiClient.delete).mockReset().mockResolvedValue({
            status: 'deleted',
            session_id: 'session / 223',
            documents_deleted: 7,
        });
    });

    it('deletes by session, asking nothing of a turn', () => {
        // The plain delete is unchanged: it carries no ask, so the route's
        // fail-closed guard answers for a running Chat exactly as it always
        // has (ADR-026).
        return new APIService().deleteChat('session / 223').then(() => {
            expect(apiClient.delete).toHaveBeenCalledWith(
                '/v4/chats/session%20%2F%20223',
            );
        });
    });

    it('asks for the turn to be ended first when the associate did', async () => {
        // #122, ADR-031 §5. The way out of `in_progress` is to end the turn,
        // and the ask travels on the request because the associate made it.
        await new APIService().deleteChat('session / 223', true);

        expect(apiClient.delete).toHaveBeenCalledWith(
            '/v4/chats/session%20%2F%20223?end_turn=true',
        );
    });
});
