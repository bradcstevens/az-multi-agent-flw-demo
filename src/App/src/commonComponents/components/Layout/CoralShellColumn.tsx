// coral.config/components/Layout/CoralShellColumn.tsx
// Structural wrapper for top-level app layout (vertical orientation)

import React from "react";

const CoralShellColumn: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        // `dvh`, not `vh`: on iOS Safari `100vh` counts the viewport as if the
        // browser chrome were not there, so the shell stood a toolbar taller
        // than the screen and shifted as that chrome collapsed on scroll. This
        // surface is a shared phone in a store before it is anything else.
        height: "100dvh",
        overflow: "hidden",
        backgroundColor: "var(--colorNeutralBackground3)",
      }}
    >
      {/*
        Both surfaces open with the task-history panel, so a keyboard user
        reached the question box only after tabbing through every task in it.
        The link is the first focusable thing in the shell and is visible only
        while it holds focus.
      */}
      <a className="skip-to-content" href="#conversation">
        Skip to the conversation
      </a>
      {children}
    </div>
  );
};

export default CoralShellColumn;



