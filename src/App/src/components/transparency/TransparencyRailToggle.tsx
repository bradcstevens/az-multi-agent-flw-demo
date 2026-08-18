import React from 'react';
import { Button } from '@fluentui/react-components';
import { PanelRightContract20Regular, PanelRightExpand20Regular } from '@fluentui/react-icons';

import { useDesktopDrawer } from '@/hooks/usePanelDrawer';
import { TRANSPARENCY_RAIL_ID } from '@/models/panelDrawer';
import { TRANSPARENCY_PANELS_LABEL } from '@/models/storeSurface';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
    selectTransparencyRailExpanded,
    selectTransparencyRailPinned,
    transparencyRailToggled,
} from '@/store/slices/transparencySlice';
import { TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION } from '@/models/storeSurface';

/**
 * The **Transparency rail**'s drawer control (issue #127, ADR-035).
 *
 * A **disclosure button**, in the content toolbar — the one element on both the
 * home surface and the chat surface, which is what lets a single control reach
 * a rail that is rendered bare on one and wrapped on the other.
 *
 * **One accessible name**, and it is a noun. A label that flipped between
 * *Show* and *Hide* would be a second control to anybody reading the surface
 * through a screen reader: the thing they just pressed is gone and something
 * else is in its place. The state is `aria-expanded`'s to report, and the
 * target `aria-controls`'.
 *
 * Absent below the **Stacking breakpoint** rather than disabled, because there
 * the rail is always open: a control for a state that cannot exist costs the
 * associate a tap to discover that it does nothing.
 */
const TransparencyRailToggle: React.FC = () => {
    const dispatch = useAppDispatch();
    const isDesktopDrawer = useDesktopDrawer();
    const expanded = useAppSelector(selectTransparencyRailExpanded);
    const pinned = useAppSelector(selectTransparencyRailPinned);

    if (!isDesktopDrawer) return null;

    return (
        <Button
            appearance="subtle"
            className="transparency-rail-toggle"
            /*
             * The one thing here that does change with the state, and it is the
             * glyph rather than the name: the surface is read from across a
             * room, where `aria-expanded` is invisible and a control offering
             * to *contract* an already-closed rail is the surface arguing with
             * itself in front of the audience.
             */
            icon={expanded ? <PanelRightContract20Regular /> : <PanelRightExpand20Regular />}
            aria-controls={TRANSPARENCY_RAIL_ID}
            aria-expanded={expanded}
            aria-description={
                pinned && !expanded ? TRANSPARENCY_RAIL_PINNED_CLOSED_DESCRIPTION : undefined
            }
            onClick={() => dispatch(transparencyRailToggled())}
        >
            {TRANSPARENCY_PANELS_LABEL}
        </Button>
    );
};

export default TransparencyRailToggle;
