import React, { ReactNode } from "react";
import { Body1Strong } from "@fluentui/react-components";

import { SURFACE_HEADING } from "@/models/headingOutline";

interface ContentToolbarProps {
  panelIcon?: ReactNode;
  panelTitle?: string | null;
  children?: ReactNode;
}

const ContentToolbar: React.FC<ContentToolbarProps> = ({
  panelIcon,
  panelTitle,
  children,
}) => {
  return (
    <div
      className="panelToolbar"
      style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "16px",
        boxSizing: "border-box",
        height: "56px",
        // A header needs an edge. Without one the assistant's name and the
        // store identity floated on the same plane as the conversation
        // beneath them, so nothing said where the chrome stopped and the
        // answer began.
        borderBottom: "1px solid var(--colorNeutralStroke2)",
        flexShrink: 0,
      }}
    >
      {(panelIcon || panelTitle) && (
        <div
          className="panelTitle"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            flex: "1 1 auto",
            overflow: "hidden", // Ensure title section is contained
          }}
        >
          {panelIcon && (
            <div
              style={{
                flexShrink: 0, // Prevent the icon from shrinking
                display: "flex",
                alignItems: "center",
              }}
            >
              {panelIcon}
            </div>
          )}
          {/*
            The surface's one top-level heading (issue #57). The conversation's
            header names the assistant, and it is the only place that does so
            which survives the Stacking breakpoint — the left panel's toolbar
            says the same name and is dropped below 900px, so a heading there
            is one the associate's phone never renders.

            `margin: 0` because a heading is a flex item here, and a flex item
            is blockified: without it the user-agent's `margin: .83em 0` would
            suddenly apply and the toolbar would grow. The `as` override keeps
            Fluent's typography classes, so nothing else about it changes.
          */}
          {panelTitle && (
            <Body1Strong
              as={SURFACE_HEADING}
              style={{
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                margin: 0,
              }}
            >
              {panelTitle}
            </Body1Strong>
          )}
        </div>
      )}
      <div
        className="panelTools"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0",
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default ContentToolbar;
