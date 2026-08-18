import React, {
  ReactNode,
  ReactElement,
  isValidElement,
} from "react";
import PanelToolbar from "./PanelLeftToolbar.js";
import PanelFooter from "./PanelFooter"; // 👈 new

interface PanelLeftProps {
  id?: string;
  children?: ReactNode;
}

const PanelLeft: React.FC<PanelLeftProps> = ({
  id,
  children,
}) => {
  const childrenArray = React.Children.toArray(children) as ReactElement[];
  const toolbar = childrenArray.find(
    (child) => isValidElement(child) && child.type === PanelToolbar
  );
  const footer = childrenArray.find(
    (child) => isValidElement(child) && child.type === PanelFooter
  );
  const content = childrenArray.filter(
    (child) =>
      !(
        isValidElement(child) &&
        (child.type === PanelToolbar || child.type === PanelFooter)
      )
  );
  const panelStyle: React.CSSProperties & { "--panel-width": string } = {
    "--panel-width": `${width}px`,
    backgroundColor: "var(--colorNeutralBackground4)",
    height: "100%",
    boxSizing: "border-box",
    position: "relative",
    borderRight: panelResize
      ? isHandleHovered
        ? "2px solid var(--colorNeutralStroke2)"
        : "2px solid transparent"
      : "none",
  };

  return (
    /*
     * `nav`, because it is: this panel is the chat history, and every row in it
     * opens a conversation. It was the second of the surface's three columns to
     * be an anonymous `div` — the rail was already an `aside` — which left a
     * screen-reader user no landmark to move between and no way past the chat
     * list except through it. The conversation is now a `main`, and the skip
     * link in `CoralShellColumn` jumps to it.
     */
    <nav
      id={id}
      className="panelLeft"
      aria-label="Chat history"
      style={panelStyle}
    >
      {toolbar && <div style={{ flexShrink: 0 }}>{toolbar}</div>}

      <div
        className="panelContent"
        style={{
          flex: 1,
          overflowY: "auto",
          overflowX: "hidden",
          boxSizing: "border-box",
        }}
      >
        {content}
      </div>

      {footer && <div style={{ position: 'relative', zIndex: 2 }}>{footer}</div>}
    </nav>
  );
};

export default PanelLeft;
