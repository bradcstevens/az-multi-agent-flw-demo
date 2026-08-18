import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./apiClient', () => ({
    apiClient: {
        post: vi.fn(),
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
