// PromptCard.tsx
import React from "react";
import { Body1, Body1Strong, Button } from "@fluentui/react-components";

type PromptCardProps = {
  title: string;
  description: string;
  icon?: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  /** Optional trailing element beside the title, e.g. a Lane badge. */
  badge?: React.ReactNode;
};

const PromptCard: React.FC<PromptCardProps> = ({
  title,
  description,
  icon,
  onClick,
  disabled = false,
  badge,
}) => {
  return (
    <Button
      type="button"
      disabled={disabled}
      onClick={onClick}
      style={{
        flex: "1",
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
        padding: "16px",
        margin: 0,
        backgroundColor: disabled
          ? "var(--colorNeutralBackgroundDisabled)"
          : "var(--colorNeutralBackground3)",
        border: "1px solid var(--colorNeutralStroke1)",
        borderRadius: "8px",
        cursor: disabled ? "not-allowed" : "pointer",
        boxShadow: "none",
        opacity: disabled ? 0.4 : 1, //
        transition: "background-color 0.2s ease-in-out",
      }}
      // 🧠 Only apply hover if not disabled
      onMouseOver={(e: React.MouseEvent<HTMLElement>) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor =
            "var(--colorNeutralBackground3Hover)";
            e.currentTarget.style.border = "1px solid var(--colorNeutralStroke1)"; // subtle shadow on hover
        }
      }}
      onMouseOut={(e: React.MouseEvent<HTMLElement>) => {
        if (!disabled) {
          e.currentTarget.style.backgroundColor =
            "var(--colorNeutralBackground3)";
            e.currentTarget.style.border = "1px solid var(--colorNeutralStroke1)";
        }
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          {/*
            The badge leads the card, on a row of its own.

            Beside the title it had neither room nor a fixed position: a grid
            column is ~237px wide at the surface's 728px, and a two-word pill
            took most of what was left after the padding, so the title wrapped
            a word at a time and the badge — vertically centred against a title
            of one line or two — sat at a different height on every card. Six
            badges at six heights cannot be scanned, and scanning them is the
            entire reason five cards say one thing and one says another.

            A row of its own fixes both: full width, so the label never wraps
            inside its own pill, and an identical position on all six cards.
          */}
          {badge && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                marginBottom: "2px",
              }}
            >
              {badge}
            </div>
          )}
          <div style={{ display: "flex", alignItems: "flex-start", gap: "8px" }}>
            {icon && (
              <div
                style={{
                  fontSize: "20px",
                  color: "var(--colorBrandForeground1)",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {icon}
              </div>
            )}
            <Body1Strong>{title}</Body1Strong>
          </div>
          <Body1 style={{ color: "var(--colorNeutralForeground3)" }}>
            {description}
          </Body1>
        </div>
      </div>
    </Button>
  );
};

export default PromptCard;
