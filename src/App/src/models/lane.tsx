/**
 * The Lane a request takes (issue #16, ADR-013).
 *
 * Declared as metadata on a Quick Task and echoed back by the backend as the
 * lane actually taken, which is not always the lane declared — free-typed
 * input declares nothing and is routed by the backend's keyword fallback.
 *
 * The lane router lives on the backend and only there. Re-deriving a lane in
 * the browser would be a second source of truth for a decision that fails open
 * to the Deliberate lane, and two routers cannot both be the one that failed
 * open.
 */
export type Lane = 'fast' | 'deliberate';

/** How each Lane is named to the associate and the audience. */
export const LANE_LABELS: Record<Lane, string> = {
    fast: 'Fast lane',
    deliberate: 'Needs approval',
};

/** Whether a value coming off the wire is a Lane we can render. */
export const isLane = (value: unknown): value is Lane =>
    value === 'fast' || value === 'deliberate';
