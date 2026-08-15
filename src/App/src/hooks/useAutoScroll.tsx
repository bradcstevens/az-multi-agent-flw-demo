/**
 * useAutoScroll — smooth-scrolls a container to the bottom.
 * Extracted from PlanPage to be reusable.
 */
import { useCallback, useEffect, useRef } from 'react';

/**
 * Scroll `el` to `top`. `Element.scrollTo` is absent wherever there is no layout
 * engine — jsdom defines none of scrollTo/scroll/scrollBy/scrollIntoView — so
 * fall back to assigning scrollTop, which really scrolls, rather than letting
 * the call throw from inside a timer nobody is watching.
 */
function scrollElementTo(el: HTMLElement, top: number) {
    if (typeof el.scrollTo === 'function') {
        el.scrollTo({ top, behavior: 'smooth' });
    } else {
        el.scrollTop = top;
    }
}

export function useAutoScroll() {
    const messagesContainerRef = useRef<HTMLDivElement>(null);
    const finalResultRef = useRef<HTMLDivElement>(null);
    // Every pending scroll is owned here so unmount can cancel it; an orphaned
    // timer would otherwise run against a detached node after the page is gone.
    const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

    const schedule = useCallback((run: () => void, delay: number) => {
        const id = setTimeout(() => {
            timeoutsRef.current = timeoutsRef.current.filter((pending) => pending !== id);
            run();
        }, delay);
        timeoutsRef.current.push(id);
    }, []);

    useEffect(
        () => () => {
            timeoutsRef.current.forEach(clearTimeout);
            timeoutsRef.current = [];
        },
        [],
    );

    const scrollToBottom = useCallback(() => {
        schedule(() => {
            const container = messagesContainerRef.current;
            if (container) {
                scrollElementTo(container, container.scrollHeight);
            }
        }, 100);
    }, [schedule]);

    // Scroll to the final result message instead of the absolute bottom.
    // Falls back to scrollToBottom when the anchor is not yet mounted.
    const scrollToFinalResult = useCallback(() => {
        schedule(() => {
            const anchor = finalResultRef.current;
            if (!anchor) {
                scrollToBottom();
                return;
            }
            if (typeof anchor.scrollIntoView === 'function') {
                anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }
            const container = messagesContainerRef.current;
            if (container) {
                scrollElementTo(container, anchor.offsetTop - container.offsetTop);
            }
        }, 150);
    }, [schedule, scrollToBottom]);

    return { messagesContainerRef, finalResultRef, scrollToBottom, scrollToFinalResult };
}

export default useAutoScroll;
