import { useEffect, useState } from 'react';

const DESKTOP_DRAWER_QUERY = '(min-width: 901px)';

const matchesDesktopDrawer = (): boolean =>
    typeof window === 'undefined' || !window.matchMedia
        ? true
        : window.matchMedia(DESKTOP_DRAWER_QUERY).matches;

const useDesktopDrawer = (): boolean => {
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

export default useDesktopDrawer;
