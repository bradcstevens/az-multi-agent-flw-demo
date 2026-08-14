import React from "react";
import { Badge, makeStyles } from "@fluentui/react-components";
import { Flash16Filled, Checkmark16Filled } from "@fluentui/react-icons";

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
 *
 * A Lane decides exactly one thing — whether the plan-review gate is built —
 * and that is the only thing this badge claims. It deliberately promises
 * neither a latency (Fast-lane latency is still unmeasured, and ADR-013 makes
 * that measurement the sole trigger for reopening the bypass question) nor an
 * answer: the one-tap boundary probe (#26) declares the Fast lane and is
 * refused by the Identity boundary gate above the router, so it is never
 * answered at all.
 */
export interface LaneBadgeProps {
  lane: Lane;
  /** Distinguishes the declared lane from the lane actually taken. */
  variant?: "declared" | "taken";
}

const useStyles = makeStyles({
  /*
   * Geometry only — never colour.
   *
   * Fluent's Badge is a `height: 20px` inline-flex box with no `white-space`
   * rule of its own, so a label allowed to wrap is a label rendered outside
   * its own pill: the border is drawn by an `::after` pinned to that fixed
   * height, and it runs straight through the second line. Both lane labels are
   * two words and a Quick Task card is a grid cell that narrows with the
   * window until the badge is the thing that gives — so the wrap is this
   * badge's default state rather than an edge case. "Fast lane" broke across
   * two lines on a 1440px screen.
   *
   * Colour is deliberately absent. It is the theme's to state, in both themes
   * (#56), and it is stated below by asking Fluent for an appearance rather
   * than by naming two colours here that would meet the ratio in one theme and
   * nobody's guarantee in the other.
   */
  badge: {
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
});

/**
 * How loud the lane is, by what it is read against.
 *
 * A **declared** lane is scanned down a grid of six cards, often from the back
 * of a room, and the whole point of that grid is that five cards say one thing
 * and one says another — it is read at a glance or it is not read at all. A
 * **taken** lane sits in the plan toolbar beside the store and the associate,
 * where it is read up close and must not shout over them.
 */
const LANE_BADGE_SIZE = {
  declared: "large",
  taken: "medium",
} as const;

const LaneBadge: React.FC<LaneBadgeProps> = ({ lane, variant = "declared" }) => {
  const styles = useStyles();

  return (
    <Badge
      className={styles.badge}
      /*
       * Filled, not tint-and-outline. The pair the accelerator's badge used is
       * Fluent's quietest, and the Deliberate lane drew as a hairline outline
       * around low-contrast text — so the one card on the grid whose lane the
       * audience actually has to read was the hardest one to read. `filled` is
       * Fluent's highest-contrast pairing and is an accessible pair in both
       * themes, which is the reason to ask for it by name.
       */
      appearance="filled"
      color={lane === "fast" ? "brand" : "warning"}
      size={LANE_BADGE_SIZE[variant]}
      /*
       * Filled glyphs. A hairline outline icon inside a filled pill is the
       * first thing to disappear at projector distance, and the icon is half
       * of what keeps the two lanes apart for anyone reading them without
       * colour.
       */
      icon={lane === "fast" ? <Flash16Filled /> : <Checkmark16Filled />}
      data-testid="lane-badge"
      data-lane={lane}
      data-lane-variant={variant}
      title={
        lane === "fast"
          ? "No approval step — nothing is submitted for you to confirm"
          : "You approve before anything is submitted"
      }
    >
      {LANE_LABELS[lane]}
    </Badge>
  );
};

export default LaneBadge;
