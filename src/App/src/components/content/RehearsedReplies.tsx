import React from "react";
import { Button } from "@fluentui/react-components";

import { useAppSelector } from "@/store/hooks";
import { selectHasPendingClarification } from "@/store/slices/chatSlice";
import "../../styles/rehearsedReplies.css";

/**
 * The Rehearsed replies as one-tap chips (issue #26).
 *
 * The troubleshooting beat is the only one that asks the associate a question
 * back, and answering it was the last place in the scripted walkthrough the
 * presenter had to type. A typo or an autocorrect cannot derail a stakeholder
 * meeting if nobody types.
 *
 * **The pending-clarification gate lives here, not at the call site.** Outside
 * a clarification these are a second way to start a turn, competing with the
 * box — and a gate the caller owns is a gate a second caller forgets. That is
 * the same move the approval seam makes in #22.
 *
 * A tap submits the reply through the ordinary chat submit, so what the
 * clarification seam records as **Attempted steps** (#21) — and what the
 * **Simulated ticket** then carries (#22) — is exactly what a typed answer
 * would have recorded. The chips are a faster way to say the words, not a
 * second route around the seam.
 */
export interface RehearsedRepliesProps {
  /** The replies the Quick Task this plan was started from authored. */
  replies: string[];
  /** Submits one, the way a typed answer is submitted. */
  onReply: (reply: string) => void;
  /** True while an answer is already in flight. */
  disabled: boolean;
}

const RehearsedReplies: React.FC<RehearsedRepliesProps> = ({
  replies,
  onReply,
  disabled,
}) => {
  const clarificationPending = useAppSelector(selectHasPendingClarification);

  if (!clarificationPending || replies.length === 0) return null;

  return (
    <div className="rehearsed-replies" data-testid="rehearsed-replies">
      {replies.map((reply) => (
        <Button
          key={reply}
          appearance="outline"
          size="small"
          disabled={disabled}
          className="rehearsed-replies-chip"
          onClick={() => onReply(reply)}
        >
          {reply}
        </Button>
      ))}
    </div>
  );
};

export default RehearsedReplies;
