import React from "react";
import { Button } from "@fluentui/react-components";

import { TicketStatusReply as TicketStatusReplyModel } from "@/models/Team";
import "../../styles/rehearsedReplies.css";

export interface TicketStatusReplyProps {
  reply: TicketStatusReplyModel;
  onReply: (reply: TicketStatusReplyModel) => void;
  disabled: boolean;
}

const TicketStatusReply: React.FC<TicketStatusReplyProps> = ({
  reply,
  onReply,
  disabled,
}) => (
  <div className="rehearsed-replies" data-testid="ticket-status-reply">
    <Button
      appearance="outline"
      size="small"
      disabled={disabled}
      className="rehearsed-replies-chip"
      onClick={() => onReply(reply)}
    >
      {reply.prompt}
    </Button>
  </div>
);

export default TicketStatusReply;
