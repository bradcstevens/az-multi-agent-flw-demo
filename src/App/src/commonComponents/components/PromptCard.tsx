// PromptCard.tsx
import React from "react";
import { Body1, Body1Strong, Button, makeStyles, shorthands, tokens } from "@fluentui/react-components";

type PromptCardProps = {
  title: string;
  description: string;
  icon?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  /** Optional element on the card's eyebrow row, e.g. a Lane badge. */
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
    ...shorthands.padding(tokens.spacingVerticalL, tokens.spacingHorizontalL),
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

    /*
     * The keyboard's indicator, declared where the hover and press states are.
     *
     * It used to live in `HomeInput.css` as `.home-input-quick-tasks
     * .fui-Button:focus-visible`, with `!important` twice to win against
     * Fluent's later-injected styles — a page reaching past a component's
     * interface to name a class the component's library generates, which stops
     * matching the day that library renames it. Silently, and on the one
     * affordance nobody notices missing until they need it.
     *
     * Here it is an ordinary declaration among the card's other states, and
     * Griffel's `:focus-visible` bucket is emitted after Fluent's own, so it
     * wins on order rather than on `!important`.
     */
    ":focus-visible": {
      ...shorthands.outline("2px", "solid", "var(--colorStrokeFocus2)"),
      outlineOffset: "2px",
    },

    /*
     * Motion is opt-out (#59).
     *
     * `index.css` shortens every transition on the surface to 0.01ms under this
     * preference, which turns the lift and the press into *instant* jumps
     * rather than removing them — six cards that snap under a cursor is the
     * complaint, not the fix. The states themselves stay: the card still tints,
     * still changes its border and still draws its focus ring, so nothing that
     * carried meaning is lost. Only the movement goes.
     */
    "@media (prefers-reduced-motion: reduce)": {
      transitionProperty: "box-shadow, border-color, background-color",

      ":hover": {
        transform: "none",
      },

      ":active": {
        transform: "none",
      },
    },
  },

  /*
   * One column, not two.
   *
   * There were two nested flex columns here, an outer with a 12px row gap and
   * an inner with a 4px one — and the outer had a single child, so its gap
   * separated nothing at all. A dead declaration that looks like the card's
   * main measurement is worse than no declaration: it is the first number
   * anybody reaches for when the spacing is wrong.
   */
  body: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXS,
  },

  /*
   * The eyebrow: the icon and the lane, on a row of their own ahead of the
   * title.
   *
   * Beside the title the badge had neither room nor a fixed position: a grid
   * column is ~237px wide at the surface's 728px, and a two-word pill took most
   * of what was left after the padding, so the title wrapped a word at a time
   * and the badge — vertically centred against a title of one line or two — sat
   * at a different height on every card. Six badges at six heights cannot be
   * scanned, and scanning them is the entire reason five cards say one thing
   * and one says another.
   *
   * The icon followed the badge up here for the other half of the same problem
   * (#59). It and its gap took 28px of the 205px the padding left, which is
   * what asked "The coffee brewer is down" to fit in 177px — so every one of
   * the six titles wrapped and none of them needed to. It is decoration for the
   * card rather than for the words, and up here it lands in the same place on
   * all six cards for the reason the badge does.
   */
  eyebrow: {
    display: "flex",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    marginBottom: tokens.spacingVerticalXXS,
  },

  icon: {
    display: "flex",
    alignItems: "center",
    fontSize: tokens.fontSizeBase500,
    color: "var(--colorBrandForeground1)",
    flexShrink: 0,
  },

  /*
   * The title has the column to itself, and `minWidth: 0` is what stops a flex
   * ancestor refusing to let it shrink below its longest word.
   */
  title: {
    display: "block",
    minWidth: 0,
  },

  /*
   * Exactly two lines, always (#59).
   *
   * The descriptions are the walkthrough's own prompts and run from 25 to 71
   * characters, which at a ~237px column is one line on one card and three on
   * another — so six cards varied by three lines of text and the two rows of
   * the grid did not line up with each other. Shortening the prompts is not on
   * offer: they are what the tap actually asks, and the SOP corpus and the
   * rehearsal marker are held to their exact wording.
   *
   * So the card shows two lines of them and `min-height` reserves the second
   * one whether or not it is used, which is what makes six cards the same
   * height rather than merely capped at one. The full prompt is unaffected —
   * `fullDescription` is what the tap submits.
   */
  description: {
    color: "var(--colorNeutralForeground3)",
    textWrap: "pretty",
    display: "-webkit-box",
    WebkitBoxOrient: "vertical",
    WebkitLineClamp: 2,
    overflowX: "hidden",
    overflowY: "hidden",
    minHeight: `calc(2 * ${tokens.lineHeightBase300})`,
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
        {(icon || badge) && (
          <span className={styles.eyebrow}>
            {icon && (
              <span className={styles.icon} data-testid="quick-task-icon">
                {icon}
              </span>
            )}
            {badge}
          </span>
        )}
        <Body1Strong className={styles.title}>{title}</Body1Strong>
        <Body1 className={styles.description}>{description}</Body1>
      </span>
    </Button>
  );
};

export default PromptCard;
