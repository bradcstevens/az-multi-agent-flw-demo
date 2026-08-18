import { beforeEach, describe, expect, it } from 'vitest';

import { getConfigData, setEnvData } from './config';

describe('the browser runtime configuration', () => {
    beforeEach(() => {
        window.appConfig = undefined;
        setEnvData({
            API_URL: 'http://localhost:8000/api',
            ENABLE_AUTH: false,
            COPILOT_STUDIO_CHAT_URL: '',
        });
    });

    it('copies an optional Copilot Studio chat URL from the frontend config document', () => {
        window.appConfig = {
            API_URL: 'https://backend.example/api',
            ENABLE_AUTH: false,
            COPILOT_STUDIO_CHAT_URL: 'https://example.invalid',
        };

        expect(getConfigData().COPILOT_STUDIO_CHAT_URL).toBe('https://example.invalid');
    });

    it('keeps the Copilot Studio chat URL absent when the frontend config document omits it', () => {
        window.appConfig = {
            API_URL: 'https://backend.example/api',
            ENABLE_AUTH: false,
        };

        expect(getConfigData().COPILOT_STUDIO_CHAT_URL).toBe('');
    });
});
