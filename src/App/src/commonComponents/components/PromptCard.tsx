// PromptCard.tsx
import React from "react";
import { Body1, Body1Strong, Button, makeStyles, shorthands } from "@fluentui/react-components";

type PromptCardProps = {
  title: string;
  description: string;
  icon?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  /** Optional trailing element beside the title, e.g. a Lane badge. */
  badge?: React.ReactNode;
};

/**
 * A Quick Task card.
 *
 * Styled through Griffel rather than through inline styles or a stylesheet, and
 * both alternatives were tried here. A rule in `styles/` loses: this is a Fluent
 * Button, and Fluent injects its own styles after the imported sheets, so
 * anything declared there about the control is overridden in every state it can
 * be in (the same trap `HomeInput.css` records for the send control). Inline
 * styles win that fight but cannot express `:hover` or `:active` at all, which
 * is why the card previously carried `onMouseOver` / `onMouseOut` handlers that
 * repainted the background by hand — and, having no `onMouseDown`, gave no
 * press feedback whatsoever.
 *
 * Griffel is the seam that composes correctly with Fluent's own styles *and*
 * has pseudo-classes. Geometry and elevation are declared here; colour is
 * declared through theme tokens, never in hex, per #56.
 */
const useStyles = makeStyles({
  card: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
    // Fluent's Button centres its children on the cross axis, which in a
    // column is horizontal — so a card's content block is only as wide as
    // its own longest line, and short cards centre while long ones fill.
    // `justify-content` is the same problem on the other axis: grid cells
    // in a row stretch to the tallest card, and a card with a one-line
    // description floated its content to the middle. The lane badge is the
    // first thing that made either visible — an eyebrow that starts in a
    // different place on every card is not a column anyone can scan.
    alignItems: "stretch",
    justifyContent: "flex-start",
    textAlign: "left",
    ...shorthands.padding("16px"),
    ...shorthands.margin(0),
    ...shorthands.border("1px", "solid", "var(--colorNeutralStroke2)"),
    ...shorthands.borderRadius("var(--borderRadiusLarge)"),
    backgroundColor: "var(--colorNeutralBackground1)",
    boxShadow: "var(--shadow2)",
    // Transform and shadow only, so the lift is composited rather than
    // relaid out on every frame.
    transitionProperty: "transform, box-shadow, border-color, background-color",
    transitionDuration: "180ms",
    transitionTimingFunction: "cubic-bezier(0.33, 1, 0.68, 1)",

    ":hover": {
      backgroundColor: "var(--colorNeutralBackground1Hover)",
      ...shorthands.borderColor("var(--colorBrandStroke2)"),
      boxShadow: "var(--shadow8)",
      // A lift, not a colour change. Six cards in a grid are distinguished
      // from one another by position, so the one under the cursor should
      // move rather than merely tint.
      transform: "translateY(-2px)",
    },

    // The press the card never had. A card that only reacts on hover reads
    // as inert on the touchscreen this demo is actually operated from,
    // where there is no hover at all.
    ":active": {
      transform: "translateY(0) scale(0.995)",
      boxShadow: "var(--shadow2)",
      transitionDuration: "80ms",
    },

    ":disabled": {
      backgroundColor: "var(--colorNeutralBackgroundDisabled)",
      boxShadow: "none",
      transform: "none",
      opacity: 0.5,
      cursor: "not-allowed",
    },
  },

  body: {
    display: "flex",
    flexDirection: "column",
    rowGap: "12px",
  },

  stack: {
    display: "flex",
    flexDirection: "column",
    rowGap: "4px",
  },

  /*
   * The badge leads the card, on a row of its own.
   *
   * Beside the title it had neither room nor a fixed position: a grid column is
   * ~237px wide at the surface's 728px, and a two-word pill took most of what
   * was left after the padding, so the title wrapped a word at a time and the
   * badge — vertically centred against a title of one line or two — sat at a
   * different height on every card. Six badges at six heights cannot be
   * scanned, and scanning them is the entire reason five cards say one thing
   * and one says another.
   *
   * A row of its own fixes both: full width, so the label never wraps inside
   * its own pill, and an identical position on all six cards.
   */
  badgeRow: {
    display: "flex",
    alignItems: "center",
    marginBottom: "2px",
  },

  titleRow: {
    display: "flex",
    alignItems: "flex-start",
    columnGap: "8px",
  },

  icon: {
    display: "flex",
    alignItems: "center",
    fontSize: "20px",
    color: "var(--colorBrandForeground1)",
    flexShrink: 0,
  },

  description: {
    color: "var(--colorNeutralForeground3)",
    textWrap: "pretty",
  },
});

const PromptCard: React.FC<PromptCardProps> = ({
  title,
  description,
  icon,
  onClick,
  disabled = false,
  badge,
}) => {
  const styles = useStyles();

  return (
    <Button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={styles.card}
    >
      <span className={styles.body}>
        <span className={styles.stack}>
          {badge && <span className={styles.badgeRow}>{badge}</span>}
          <span className={styles.titleRow}>
            {icon && <span className={styles.icon}>{icon}</span>}
            <Body1Strong>{title}</Body1Strong>
          </span>
          <Body1 className={styles.description}>{description}</Body1>
        </span>
      </span>
    </Button>
  );
};

export default PromptCard;
