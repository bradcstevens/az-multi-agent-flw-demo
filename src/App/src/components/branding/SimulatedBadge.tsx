import React from 'react';
import { Badge } from '@fluentui/react-components';

import { SIMULATED_LABEL } from '../../models/storeSurface';

/**
 * The **Simulated** label (issue #25, R11's surviving fragment).
 *
 * A stakeholder is being asked to believe a cross-platform architecture claim,
 * and the fastest way to lose that is for them to discover afterwards that
 * something they took for connected was invented. So anything whose content was
 * authored for the walkthrough rather than produced by a system carries this.
 *
 * The converse matters as much: a badge on something that *is* connected —
 * a real Foundry answer, a real Copilot Studio hop, a measured token count —
 * gives away the demo's strongest evidence. Label the invented things, and only
 * those.
 */
export interface SimulatedBadgeProps {
    /** What is simulated, for the tooltip. */
    what?: string;
}

const SimulatedBadge: React.FC<SimulatedBadgeProps> = ({ what }) => (
    <Badge
        appearance="outline"
        color="informative"
        data-testid="simulated-badge"
        title={what ? `${what} is simulated for this demonstration.` : undefined}
    >
        {SIMULATED_LABEL}
    </Badge>
);

export default SimulatedBadge;
