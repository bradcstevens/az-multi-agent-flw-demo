/**
 * The auto-scroll timer is the one piece of this hook nothing else observes:
 * it runs 100ms after the render that scheduled it, outside any assertion, so
 * a throw inside it fails the run without failing a test. These cover the two
 * ways it can misbehave — scrolling by an API the environment does not define,
 * and running at all after the component that scheduled it has gone.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, renderHook } from '@testing-library/react';
import { useAutoScroll } from './useAutoScroll';

function attachContainer(
    ref: React.RefObject<HTMLDivElement | null>,
    scrollHeight: number,
): HTMLDivElement {
    const { container } = render(<div />);
    const el = container.firstChild as HTMLDivElement;
    (ref as { current: HTMLDivElement | null }).current = el;
    Object.defineProperty(el, 'scrollHeight', { value: scrollHeight, configurable: true });
    return el;
}

describe('the auto-scroll timer, fired while still mounted', () => {
    it('scrolls the container instead of throwing', async () => {
        const { result } = renderHook(() => useAutoScroll());
        const { messagesContainerRef, scrollToBottom } = result.current;
        const el = attachContainer(messagesContainerRef, 500);

        scrollToBottom();
        await new Promise((r) => setTimeout(r, 200));

        expect(el.scrollTop).toBe(500);
    });

    it('scrolls to the final result anchor instead of throwing', async () => {
        const { result } = renderHook(() => useAutoScroll());
        const { messagesContainerRef, finalResultRef, scrollToFinalResult } = result.current;
        const el = attachContainer(messagesContainerRef, 500);
        const anchor = render(<div />).container.firstChild as HTMLDivElement;
        Object.defineProperty(anchor, 'offsetTop', { value: 320, configurable: true });
        (finalResultRef as { current: HTMLDivElement | null }).current = anchor;

        scrollToFinalResult();
        await new Promise((r) => setTimeout(r, 250));

        expect(el.scrollTop).toBe(320);
    });
});

describe('the auto-scroll timer, after the component has gone', () => {
    it('does not run against the detached container', async () => {
        const { result, unmount } = renderHook(() => useAutoScroll());
        const { messagesContainerRef, scrollToBottom } = result.current;
        const el = attachContainer(messagesContainerRef, 500);
        const scrollTo = vi.fn();
        Object.defineProperty(el, 'scrollTo', { value: scrollTo, configurable: true });

        scrollToBottom();
        unmount();
        await new Promise((r) => setTimeout(r, 200));

        expect(scrollTo).not.toHaveBeenCalled();
        expect(el.scrollTop).toBe(0);
    });
});
