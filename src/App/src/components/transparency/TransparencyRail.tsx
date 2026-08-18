import React from 'react';

import { useAppSelector } from '@/store/hooks';
import { selectGroundingSource, selectMeter } from '@/store/slices/transparencySlice';
import { modelsByExecutor } from '@/models/roster';
import { TeamConfig } from '@/models/Team';
import {
    TRANSPARENCY_RAIL_COLLAPSED_CLASS,
    TRANSPARENCY_RAIL_ID,
} from '@/models/panelDrawer';
import { useTransparencyRailOpen } from '@/hooks/usePanelDrawer';
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
 *
 * It is also a **Panel drawer** (#127): closed, it is zero width and the
 * conversation takes the width back, because the rail is read *beside* the
 * answer it explains and an overlay would cover the thing it is explaining.
 * The panels **unmount** rather than hide — a section heading a non-visual user
 * skims to and finds nothing behind is #78's defect one step further on, and
 * `display: none` on a rail that still holds them would rebuild it exactly.
 *
 * Below the **Stacking breakpoint** the rail is always open, exactly as it
 * behaved before the drawer existed: the associate's phone has no width beside
 * the conversation to give back, and #60 fought to make this rail readable
 * there.
 */
export interface TransparencyRailProps {
    /** The workflow roster, for the meter's per-agent model column. */
    team?: TeamConfig | null;
    children?: React.ReactNode;
}

const TransparencyRail: React.FC<TransparencyRailProps> = ({ team, children }) => {
    const source = useAppSelector(selectGroundingSource);
    const meter = useAppSelector(selectMeter);
    const open = useTransparencyRailOpen();

    return (
        <aside
            id={TRANSPARENCY_RAIL_ID}
            className={open ? 'transparency-rail' : `transparency-rail ${TRANSPARENCY_RAIL_COLLAPSED_CLASS}`}
            data-testid="transparency-rail"
        >
            {open && (
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
