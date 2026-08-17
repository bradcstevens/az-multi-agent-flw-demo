import React from 'react';

import { useAppSelector } from '@/store/hooks';
import {
    selectGroundingSource,
    selectMeter,
    selectTransparencyRailExpanded,
} from '@/store/slices/transparencySlice';
import { modelsByExecutor } from '@/models/roster';
import { TeamConfig } from '@/models/Team';
import useDesktopDrawer from '@/hooks/useDesktopDrawer';
import '@/styles/transparency.css';

import GroundingPanel from './GroundingPanel';
import TokenMeterPanel from './TokenMeterPanel';

/**
 * The transparency rail (issue #24) — the Grounding panel and the Token meter,
 * side by side down one edge of the surface.
 *
 * One component because they are one argument: *where the answer came from* and
 * *what it cost*, watched live while the architecture works. It reads the slice
 * directly rather than taking the signals as props, so it can be dropped onto
 * any surface the walkthrough visits — and it has to be, because the demo's
 * refusal happens on the home surface and its answers happen on the plan
 * surface, while the meter's running total spans both.
 */
export interface TransparencyRailProps {
    /** The workflow roster, for the meter's per-agent model column. */
    team?: TeamConfig | null;
    children?: React.ReactNode;
}

const TransparencyRail: React.FC<TransparencyRailProps> = ({ team, children }) => {
    const source = useAppSelector(selectGroundingSource);
    const meter = useAppSelector(selectMeter);
    const isDesktopDrawer = useDesktopDrawer();
    const expanded = useAppSelector(selectTransparencyRailExpanded);
    const visible = !isDesktopDrawer || expanded;

    return (
        <aside
            id="transparency-rail"
            className={`transparency-rail${visible ? '' : ' transparency-rail--collapsed'}`}
            data-testid="transparency-rail"
        >
            {visible && (
                <>
                    {children}
                    <GroundingPanel source={source} />
                    <TokenMeterPanel meter={meter} models={modelsByExecutor(team)} />
                </>
            )}
        </aside>
    );
};

export default TransparencyRail;
