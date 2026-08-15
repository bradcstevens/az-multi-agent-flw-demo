import {
  Button,
  Caption1,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Menu,
  MenuItem,
  MenuList,
  MenuPopover,
  MenuTrigger,
  Skeleton,
  SkeletonItem,
} from "@fluentui/react-components";
import { Delete20Regular, MoreHorizontal20Regular } from "@fluentui/react-icons";
import React from "react";
import "../../styles/ChatList.css";
import { Chat, ChatListProps } from "@/models";
import { NO_CHATS_MESSAGE, chatStateLabel } from "../../models/chatState";
import {
  CANCEL_DELETE_LABEL,
  CONFIRM_DELETE_LABEL,
  DELETE_CHAT_LABEL,
  DELETE_CHAT_TITLE,
  DELETE_CHAT_WARNING,
  DELETE_FAILED_TITLE,
  STILL_RUNNING_REASON,
  canDeleteChat,
  chatMenuLabel,
} from "../../models/chatDeletion";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
} from "@fluentui/react-components";

const ChatList: React.FC<ChatListProps> = ({
  chats,
  onChatSelect,
  onChatDelete,
  loading,
  selectedChatId,
  isLoadingTeam
}) => {
  const isLoading = Boolean(loading || isLoadingTeam);
  /*
    Which chat the confirmation is about, or none. One dialog for the whole
    list rather than one per row: the confirmation names the chat it holds, so
    a second one would be a second place for that name to come from.
  */
  const [confirming, setConfirming] = React.useState<Chat | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [failure, setFailure] = React.useState<string | null>(null);

  const confirmDelete = React.useCallback(async () => {
    if (!confirming) return;

    setDeleting(true);
    setFailure(null);
    try {
      await onChatDelete(confirming);
      setConfirming(null);
    } catch (error) {
      /*
        The chat is still there. Closing on a rejected delete would tell the
        associate it is gone and leave the row to reappear on the next load, so
        the dialog stays open and says so.

        Said *here*, in the dialog the associate is already looking at, rather
        than thrown to a toast: the panel holds a Fluent `useToastController`
        whose `Toaster` this application has never mounted, so a message sent
        that way is a message nobody receives. Found by review.
      */
      setFailure(error instanceof Error ? error.message : String(error));
    } finally {
      setDeleting(false);
    }
  }, [confirming, onChatDelete]);

  const renderChatRow = (chat: Chat) => {
    const isActive = chat.id === selectedChatId;
    const state = chatStateLabel(chat.status);
    const deletable = canDeleteChat(chat.status);
    const reasonId = `chat-delete-reason-${chat.id}`;

    return (
      <div
        key={chat.id}
        className={`task-tab${isActive ? " active" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => onChatSelect(chat.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onChatSelect(chat.id);
          }
        }}
      >
        <div className="sideNavTick" />
        <div className="left">
          <div className="task-name-truncated" title={chat.name}>
            {chat.name}
          </div>
          <div className="task-list-task-meta">
            {/*
              Each row states its own state (#74). With failed and canceled
              chats listed beside good ones, a row that says nothing about its
              state cannot be told from one that finished — the associate would
              have to open a broken chat to find out it is broken.
            */}
            {state && (
              <Caption1 className="task-list-task-state">{state}</Caption1>
            )}
            {chat.date && (
              <Caption1 className="task-list-task-date">{chat.date}</Caption1>
            )}
          </div>
        </div>
        {/*
          The row's menu, popover included (#75). ADR-022 removed a `Menu`
          carrying a `MenuTrigger` and no `MenuPopover` after measuring that on
          `@fluentui/react-components` 9.64 such a menu renders *nothing* — the
          trigger never reaches the DOM, so no test, no screen reader and no
          click could see it. Rebuilding the control means building the popover
          too, and `ChatList.test` asserts it through the DOM rather than by
          reading this file.

          The click is stopped here: this row is itself a button, and reaching
          for the menu must not open the chat underneath it.
        */}
        <div
          className="task-menu"
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
        >
          <Menu>
            <MenuTrigger disableButtonEnhancement>
              <Button
                appearance="subtle"
                size="small"
                icon={<MoreHorizontal20Regular />}
                className="task-menu-button"
                aria-label={chatMenuLabel(chat.name)}
              />
            </MenuTrigger>
            <MenuPopover>
              <MenuList>
                <MenuItem
                  icon={<Delete20Regular />}
                  /*
                    `disabledFocusable` beside `disabled`, not instead of it:
                    `disabled` is what puts `aria-disabled` on the item, and
                    `disabledFocusable` is what keeps it in the tab order — a
                    natively-disabled item leaves it, so a keyboard user would
                    find the reason below missing rather than read it.
                  */
                  disabled={!deletable}
                  disabledFocusable={!deletable}
                  aria-describedby={deletable ? undefined : reasonId}
                  onClick={() => deletable && setConfirming(chat)}
                >
                  {DELETE_CHAT_LABEL}
                </MenuItem>
                {!deletable && (
                  /*
                    ADR-026's own noted cost: a running Chat cannot be deleted,
                    so the surface has to explain when it keeps one rather than
                    leave a control that reads as broken.
                  */
                  <Caption1 id={reasonId} className="task-menu-reason">
                    {STILL_RUNNING_REASON}
                  </Caption1>
                )}
              </MenuList>
            </MenuPopover>
          </Menu>
        </div>
      </div>
    );
  };

  const renderSkeleton = (key: string) => (
    <div key={key} className="task-skeleton-container">
      <Skeleton aria-label="Loading chat">
        <div className="task-skeleton-wrapper">
          <SkeletonItem shape="rectangle" animation="wave" size={24} />
        </div>
      </Skeleton>
    </div>
  );

  return (
    <div className="task-list-container">
      <Accordion defaultOpenItems="1" collapsible>
        <AccordionItem value="1">
          {/*
            Not "Completed" any more: the list holds chats in every state
            (#74), and a heading naming one of them would be false above the
            other five.
          */}
          <AccordionHeader expandIconPosition="end">
            Chats
          </AccordionHeader>
          <AccordionPanel>
            {isLoading
              ? Array.from({ length: 5 }, (_, i) =>
                renderSkeleton(`chat-${i}`)
              )
              : chats.length
                ? chats.map(renderChatRow)
                : (
                  /*
                    Plainly (#75). ADR-022's hedged "to show" guarded a list
                    that could merely be hidden; ADR-026 deletes chats instead,
                    so there is no state left in which the hedge is what makes
                    the sentence true.
                  */
                  <Caption1 className="task-list-empty">
                    {NO_CHATS_MESSAGE}
                  </Caption1>
                )}
          </AccordionPanel>
        </AccordionItem>

      </Accordion>

      <Dialog
        open={confirming !== null}
        onOpenChange={(_, data) => {
          if (data.open || deleting) return;
          setConfirming(null);
          setFailure(null);
        }}
      >
        <DialogSurface>
          <DialogBody>
            <DialogTitle>{DELETE_CHAT_TITLE}</DialogTitle>
            <DialogContent>
              {/*
                The chat is named here. Every row shares one dialog, and a
                confirmation that does not say which conversation it is about
                is a confirmation nobody can check.
              */}
              <div className="task-delete-name">{confirming?.name}</div>
              <div>{DELETE_CHAT_WARNING}</div>
              {failure !== null && (
                /*
                  What went wrong, where the associate asked. `role="alert"`
                  because the dialog does not move and nothing else changes:
                  without it a refusal is a button that appeared to do nothing.
                */
                <div className="task-delete-failure" role="alert">
                  <strong>{DELETE_FAILED_TITLE}</strong>
                  <div>{failure}</div>
                </div>
              )}
            </DialogContent>
            <DialogActions>
              <Button
                appearance="secondary"
                disabled={deleting}
                onClick={() => {
                  setConfirming(null);
                  setFailure(null);
                }}
              >
                {CANCEL_DELETE_LABEL}
              </Button>
              <Button
                appearance="primary"
                disabled={deleting}
                onClick={confirmDelete}
              >
                {CONFIRM_DELETE_LABEL}
              </Button>
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
};

const MemoizedChatList = React.memo(ChatList);
MemoizedChatList.displayName = 'ChatList';
export default MemoizedChatList;
