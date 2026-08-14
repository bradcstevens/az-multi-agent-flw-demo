import React, { ReactNode, ReactElement } from "react";
import PanelToolbar from "../Panels/PanelLeftToolbar.js"; // Import to identify toolbar
import "../../../styles/storeSurface.css";

interface ContentProps {
    children?: ReactNode;
}

const Content: React.FC<ContentProps> = ({ children }) => {
    const childrenArray = React.Children.toArray(children) as ReactElement[];
    const toolbar = childrenArray.find(
        (child) => React.isValidElement(child) && child.type === PanelToolbar
    );
    const content = childrenArray.filter(
        (child) => !(React.isValidElement(child) && child.type === PanelToolbar)
    );

    // The conversation column's layout lives in `storeSurface.css` and not in
    // an inline style, for the reason `CoralShellRow` moved its own there in
    // #25 and this one followed in #60: an inline `flex`, `height` or
    // `min-width` beats a media query, so the stacking breakpoint could say the
    // stacked columns do not shrink while this one — the column the shell
    // crushed first — shrank anyway.
    //
    // `main`, because it is: the rail beside it is already an `aside` and the
    // task history is a `nav`, so the conversation was the one landmark on the
    // surface that a screen reader could not jump to. It is also what the skip
    // link in `CoralShellColumn` targets.
    return (
        <main className="content" id="conversation" tabIndex={-1}>
            {toolbar && <div style={{ flexShrink: 0 }}>{toolbar}</div>}

            <div className="panelContent">
                {content}
            </div>
        </main>
    );
};

export default Content;
