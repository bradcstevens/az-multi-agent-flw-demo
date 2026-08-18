import { useEffect, useState } from 'react';

import { DESKTOP_DRAWER_QUERY } from '@/models/panelDrawer';
import { useAppSelector } from '@/store/hooks';
import { selectTransparencyRailExpanded } from '@/store/slices/transparencySlice';

/**
 * The **Panel drawer**, as one rule (issue #127, ADR-035).
 *
 * Two questions, and both of them have to have exactly one answer.
 *
 * *Is there a drawer here at all* is the **Stacking breakpoint**: a drawer is a
 * side-column rule, and below 900px the columns stack, so there is no width
 * beside the conversation to give back and the rail is always open — exactly as
 * it behaved before the drawer existed. The number lives in `panelDrawer.ts`
 * and is proved against `storeSurface.css` by `TransparencyRail.test`, because
 * a stylesheet that released the drawer at one width while a component stopped
 * unmounting at another leaves a band that is a rail with room and no headings.
 *
 * *Is the drawer open* has to be answered once for the same reason the collapse
 * rule has to name two containers. The home surface renders a bare
 * `.transparency-rail`; the chat surface wraps it in `.plan-panel-right`, which
 * is where that column's width is declared. Each reading the slice and the
 * breakpoint for itself is two answers to one question, and the one that
 * disagrees is the one nobody happens to be looking at.
 */

const matchesDesktopDrawer = (): boolean =>
    typeof window === 'undefined' || !window.matchMedia
        ? true
        : window.matchMedia(DESKTOP_DRAWER_QUERY).matches;

/**
 * Whether the surface is wide enough to have a drawer.
 *
 * Defaults to open where `matchMedia` is missing: a surface that cannot tell
 * how wide it is should show the panels rather than hide them.
 */
export const useDesktopDrawer = (): boolean => {
    const [isDesktopDrawer, setIsDesktopDrawer] = useState(matchesDesktopDrawer);

    useEffect(() => {
        const query = window.matchMedia?.(DESKTOP_DRAWER_QUERY);
        if (!query) return undefined;

        const update = () => setIsDesktopDrawer(query.matches);
        update();
        query.addEventListener('change', update);
        return () => query.removeEventListener('change', update);
    }, []);

    return isDesktopDrawer;
};

/** Whether the **Transparency rail** is open — the rule every container obeys. */
export const useTransparencyRailOpen = (): boolean => {
    const isDesktopDrawer = useDesktopDrawer();
    const expanded = useAppSelector(selectTransparencyRailExpanded);

    return !isDesktopDrawer || expanded;
};
