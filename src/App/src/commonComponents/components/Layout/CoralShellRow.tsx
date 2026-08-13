// coral.config/components/Layout/CoralShellRow.tsx
// Structural wrapper for main workspace layout (horizontal split)

import React from "react";
import "../../../styles/storeSurface.css";

/**
 * The shell's columns.
 *
 * The layout moved out of an inline style and into `storeSurface.css` for
 * issue #25: the associate's screen is a phone, and an inline
 * `flex-direction: row` cannot be overridden by a media query, so the phone
 * breakpoint would have been present, correct and completely inert.
 */
const CoralShellRow: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <div className="coral-shell-row" data-testid="coral-shell-row">
      {children}
    </div>
  );
};

export default CoralShellRow;
