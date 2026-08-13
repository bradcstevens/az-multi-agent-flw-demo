import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';

import { usePresenterChord } from './usePresenterChord';

const post = vi.fn();
vi.mock('@/api/apiClient', () => ({
    apiClient: { post: (...args: unknown[]) => post(...args) },
}));

const Harness = () => {
    usePresenterChord();
    return <div>on stage</div>;
};

const press = (over: Partial<KeyboardEventInit> = {}) =>
    window.dispatchEvent(
        new KeyboardEvent('keydown', {
            code: 'KeyA',
            ctrlKey: true,
            altKey: true,
            shiftKey: true,
            ...over,
        }),
    );

describe('the presenter chord, wired', () => {
    beforeEach(() => {
        post.mockReset();
        post.mockResolvedValue({});
    });

    afterEach(() => vi.restoreAllMocks());

    it('POSTs the hidden route when the chord is pressed', () => {
        render(<Harness />);

        press();

        expect(post).toHaveBeenCalledTimes(1);
        expect(post.mock.calls[0][0]).toBe('/v4/presenter/alert');
    });

    it('sends no words of its own — the alert is the server\u2019s to compose', () => {
        render(<Harness />);

        press();

        expect(post.mock.calls[0][1]).toEqual({});
    });

    it('does nothing at all on any other key', () => {
        render(<Harness />);

        press({ code: 'KeyB' });
        press({ ctrlKey: false });

        expect(post).not.toHaveBeenCalled();
    });

    it('renders no affordance — the control is invisible to the audience', () => {
        const { container } = render(<Harness />);

        expect(container.querySelectorAll('button')).toHaveLength(0);
    });

    it('stops listening when the surface goes away', () => {
        const { unmount } = render(<Harness />);
        unmount();

        press();

        expect(post).not.toHaveBeenCalled();
    });

    it('swallows a failed alert rather than throwing on stage', async () => {
        post.mockRejectedValue(new Error('no connected client to alert'));
        render(<Harness />);

        expect(() => press()).not.toThrow();
        await Promise.resolve();
    });
});
