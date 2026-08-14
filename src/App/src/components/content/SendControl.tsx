import React from "react";
import { Button } from "@fluentui/react-components";
import { Send } from "@/commonComponents/imports/bundleicons";

/**
 * The control that sends what has been typed — one component for both surfaces
 * (#56).
 *
 * It was two: an icon-only Fluent Button declared at each call site, unnamed,
 * asked for the `subtle` appearance and then repainted — once by a stylesheet
 * Fluent overrides and once by inline styles that override Fluent. Both are
 * the same control, so both are declared here, and neither carries a rule of
 * ours for Fluent to fight with.
 */

/** Said out loud, because the control is an icon and nothing else. */
export const SEND_QUESTION = "Send question";
export const SEND_MESSAGE = "Send message";

interface SendControlProps {
    /** What this control sends, as a screen reader will announce it. */
    label: typeof SEND_QUESTION | typeof SEND_MESSAGE;
    onSend: () => void;
    /** There is nothing to send, or a send is already in flight. */
    unavailable?: boolean;
}

const SendControl: React.FC<SendControlProps> = ({
    label,
    onSend,
    unavailable = false,
}) => (
    <Button
        aria-label={label}
        appearance="primary"
        icon={<Send />}
        /*
         * Focusable rather than disabled: a natively-disabled control leaves
         * the tab order, so the one affordance that submits a question
         * disappears for a keyboard or screen-reader user instead of saying
         * why it cannot be used. Fluent renders `aria-disabled` and refuses
         * the activation.
         */
        disabledFocusable={unavailable}
        onClick={onSend}
    />
);

export default SendControl;
