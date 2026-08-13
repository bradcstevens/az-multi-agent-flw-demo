import React from "react";
import { Badge } from "@fluentui/react-components";
import { Flash16Regular, Checkmark16Regular } from "@fluentui/react-icons";

import { Lane, LANE_LABELS } from "../../models/lane";

/**
 * The Lane, made visible (issue #16, ADR-013).
 *
 * The two-lane split is the demo's answer to "why does your assistant make a
 * store associate approve a plan to look up a procedure", so the lane is
 * surfaced as a feature rather than hidden as an implementation detail. It
 * appears twice, and the two mean different things: on a Quick Task it is the
 * lane **declared**, before anything is submitted; on a plan it is the lane
 * **taken**, as the backend's lane router decided it.
 */
export interface LaneBadgeProps {
  lane: Lane;
  /** Distinguishes the declared lane from the lane actually taken. */
  variant?: "declared" | "taken";
}

const LaneBadge: React.FC<LaneBadgeProps> = ({ lane, variant = "declared" }) => (
  <Badge
    appearance={lane === "fast" ? "tint" : "outline"}
    color={lane === "fast" ? "brand" : "warning"}
    icon={lane === "fast" ? <Flash16Regular /> : <Checkmark16Regular />}
    data-testid="lane-badge"
    data-lane={lane}
    data-lane-variant={variant}
    title={
      lane === "fast"
        ? "Answered straight away — no approval step"
        : "You approve before anything is submitted"
    }
  >
    {LANE_LABELS[lane]}
  </Badge>
);

export default LaneBadge;
