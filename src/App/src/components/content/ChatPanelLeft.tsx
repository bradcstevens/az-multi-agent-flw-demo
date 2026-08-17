import React from "react";
import PanelLeft from "@/commonComponents/components/Panels/PanelLeft";
import PanelLeftToolbar from "@/commonComponents/components/Panels/PanelLeftToolbar";
import PanelFooter from "@/commonComponents/components/Panels/PanelFooter";
import {
  Button,
  Caption1,
  DrawerBody,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  OverlayDrawer,
  Toast,
  ToastBody,
  ToastTitle,
  useToastController,
} from "@fluentui/react-components";
import { Delete20Regular, ErrorCircle20Regular } from "@fluentui/react-icons";
import ChatList from "./ChatList";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Chat, ChatPanelLeftProps, Plan } from "@/models";
import { apiService } from "@/api";
import {
  isRuntimeBootstrapPending,
  waitForRuntimeBootstrap,
} from "../../api/config";
import { TaskService } from "@/store";
import "../../styles/ChatPanelLeft.css";
import { ASSISTANT_NAME, CHAT_HISTORY_LABEL } from "../../models/storeSurface";
import {
  CHAT_HISTORY_DRAWER_ID,
  CHAT_HISTORY_DRAWER_TOGGLE_ID,
} from "../../models/panelDrawer";
import { useDesktopDrawer } from "../../hooks/usePanelDrawer";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import {
  chatHistoryDrawerSetOpen,
  selectChatHistoryDrawerOpen,
} from "../../store/slices/panelDrawerSlice";
import StoreAssistantLogo from "../branding/StoreAssistantLogo";
import {
  CANCEL_DELETE_LABEL,
  CONFIRM_DELETE_ALL_LABEL,
  DELETE_ALL_CHATS_LABEL,
  DELETE_ALL_CHATS_TITLE,
  DELETE_ALL_FAILED_TITLE,
  canDeleteChat,
  deleteAllChatsWarning,
  keptRunningMessage,
  sweepFailureMessage,
} from "../../models/chatDeletion";

const ChatPanelLeft: React.FC<ChatPanelLeftProps> = ({
  reloadChats,
  restReload,
  onLeavingChat,
  isLoadingTeam
}) => {
  const { dispatchToast } = useToastController("toast");
  const dispatch = useAppDispatch();
  const isDesktopDrawer = useDesktopDrawer();
  const drawerOpen = useAppSelector(selectChatHistoryDrawerOpen);
  const navigate = useNavigate();
  /*
    The route is `/chat/:id` and the id in it is a **Plan**'s (ADR-025): a
    Chat is a Session and can hold more than one Plan, so the surface says
    chat while the identity in the URL stays the precise one.
  */
  const { id: planId } = useParams<{ id: string }>();

  /*
    Every chat, in every state (#74). This used to be the completed bucket
    alone — which meant a chat mid-escalation, whose latest plan is still
    running (#71), was not on screen at all, and that is the chat most worth
    resuming.
  */
  const [chats, setChats] = useState<Chat[]>([]);
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [plansLoading, setPlansLoading] = useState<boolean>(false);
  const [plansError, setPlansError] = useState<Error | null>(null);

  /*
    The list-level control (#76, ADR-026). One dialog for the whole panel,
    the same shape as the row's own: `confirming` is a boolean rather than a
    chat, because there is no single row this confirmation is about.
  */
  const [confirmingDeleteAll, setConfirmingDeleteAll] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);
  const [deleteAllFailure, setDeleteAllFailure] = useState<string | null>(null);
  const [keptRunningNotice, setKeptRunningNotice] = useState<string | null>(null);

  const closeDrawer = useCallback(() => {
    dispatch(chatHistoryDrawerSetOpen(false));
    window.setTimeout(() => {
      document.getElementById(CHAT_HISTORY_DRAWER_TOGGLE_ID)?.focus();
    }, 0);
  }, [dispatch]);

  const loadPlansData = useCallback(async (forceRefresh = false) => {
    try {
      setPlansLoading(true);
      setPlansError(null);
      if (isRuntimeBootstrapPending()) {
        await waitForRuntimeBootstrap();
      }
      const plansData = await apiService.getPlans(undefined, !forceRefresh); // Invert forceRefresh for useCache
      setPlans(plansData);
      
      // Reset the reload flag after successful load
      if (forceRefresh && restReload) {
        restReload();
      }
    } catch (error) {
      setPlansError(
        error instanceof Error ? error : new Error("Failed to load plans")
      );
      
      // Reset the reload flag even on error to prevent infinite loops
      if (forceRefresh && restReload) {
        restReload();
      }
    } finally {
      setPlansLoading(false);
    }
  }, [restReload]);


  // Fetch plans


  useEffect(() => {
    loadPlansData();
  }, [loadPlansData]);


  useEffect(() => {
    if (reloadChats) {
      loadPlansData(true); // Force refresh when reloadChats is true
    }
  }, [loadPlansData, reloadChats]);
  useEffect(() => {
    if (plans) {
      setChats(TaskService.transformPlansToChats(plans));
    }
  }, [plans]);

  useEffect(() => {
    if (plansError) {
      dispatchToast(
        <Toast>
          <ToastTitle>
            <ErrorCircle20Regular />
            Failed to load chats
          </ToastTitle>
          <ToastBody>{plansError.message}</ToastBody>
        </Toast>,
        { intent: "error" }
      );
    }
  }, [plansError, dispatchToast]);

  // Get the session_id that matches the current URL's planId
  const selectedChatId =
    plans?.find((plan) => plan.id === planId)?.session_id ?? null;

  const handleChatSelect = useCallback(
    (chatId: string) => {
      /*
        The row carries the plan it opens (#71). Searching the plans for one
        matching the row's session took the *first* match, so on the
        walkthrough's centrepiece pair — a troubleshooting turn and the
        escalation that continues its session (ADR-024) — the escalation was
        unreachable from this panel.
      */
      const selectedChat = chats.find((chat) => chat.id === chatId);
      if (!selectedChat) return;
      const performNavigation = () => {
        closeDrawer();
        navigate(`/chat/${selectedChat.planId}`);
      };

      // Re-opening this Chat at its latest Plan remains ordinary navigation:
      // it leaves no Chat, so it must not end this one's turn.
      if (chatId === selectedChatId) {
        performNavigation();
        return;
      }

      if (onLeavingChat) {
        onLeavingChat(performNavigation);
      } else {
        performNavigation();
      }
    },
    [chats, closeDrawer, navigate, onLeavingChat, selectedChatId]
  );

  const handleChatDelete = useCallback(
    async (chat: Chat) => {
      /*
        **Chat deletion** (#75, ADR-026). What goes is the chat's `session_id`
        — the whole conversation and everything in its partition — never the
        plan id the row carries to open with, which would take one turn and
        leave the rest of the chat in Cosmos.

        Rethrows on failure, and deliberately says nothing itself: a refused
        delete (a running chat, or a sweep that could not finish) means the
        conversation is still there, and `ChatList` keeps its confirmation
        standing and reports the reason in the dialog the associate is already
        looking at.
      */
      await apiService.deleteChat(chat.id);

      /*
        The row goes here rather than only on the next read. `loadPlansData`
        swallows its own failure into `plansError`, so a refresh that did not
        arrive would leave a deleted chat sitting in the panel with its
        confirmation already closed — the surface saying a conversation is
        gone and listing it anyway. Found by review.
      */
      setPlans((current) =>
        current ? current.filter((plan) => plan.session_id !== chat.id) : current
      );

      /*
        The page is rendering a plan that no longer exists. Leaving the
        presenter looking at the transcript of a conversation the surface has
        just said is gone is the panel contradicting itself.
      */
      if (chat.id === selectedChatId) {
        navigate("/");
      }

      await loadPlansData(true);
    },
    [loadPlansData, navigate, selectedChatId]
  );

  const handleLogoClick = useCallback(() => {
    const performNavigation = () => {
      closeDrawer();
      navigate("/");
    };

    if (onLeavingChat) {
      onLeavingChat(performNavigation);
    } else {
      performNavigation();
    }
  }, [closeDrawer, navigate, onLeavingChat]);

  // The count the confirmation states (#76) — only the chats the sweep can
  // actually take, so the number said before the fact matches what a running
  // chat's own row already claims.
  const deletableChatsCount = chats.filter((chat) => canDeleteChat(chat.status)).length;

  const handleDeleteAllChats = useCallback(async () => {
    setDeletingAll(true);
    setDeleteAllFailure(null);
    try {
      const result = await apiService.deleteAllChats();
      const deletedSessions = new Set(result.deleted_sessions);

      /*
        Same reasoning as the single delete: the rows go here rather than
        only on the next read, so a refresh that never arrives cannot leave a
        deleted chat sitting in the panel with its confirmation already
        closed.
      */
      setPlans((current) =>
        current
          ? current.filter((plan) => !deletedSessions.has(plan.session_id))
          : current
      );

      // The page may be rendering a plan whose chat just went.
      if (selectedChatId && deletedSessions.has(selectedChatId)) {
        navigate("/");
      }

      if (result.chats_kept_running > 0) {
        /*
          Named rather than only counted, when it is exactly one (#76). A
          kept chat omitted here would be the surface saying the list is
          clear when a row is still sitting in it — the same dishonesty
          ADR-026 refuses at the row level.
        */
        const keptChat =
          result.chats_kept_running === 1
            ? chats.find((chat) => !deletedSessions.has(chat.id) && !canDeleteChat(chat.status))
            : undefined;

        /*
          Rendered inline rather than through `dispatchToast`: this panel's
          `useToastController` has no mounted `Toaster` to reach (the same gap
          `ChatList` found by review at the row level), so a message sent that
          way is a message nobody sees.
        */
        setKeptRunningNotice(
          keptRunningMessage(result.chats_kept_running, keptChat?.name)
        );
      } else {
        setKeptRunningNotice(null);
      }

      /*
        A sweep that could not take every chat it tried is not a cleared
        list, and this is where the first version said it was — found by
        review. `DELETE /v4/chats` reports `incomplete` and counts what it
        left behind precisely so the panel can say so; reading only
        `deleted_sessions` and `chats_kept_running` closed the dialog on a
        half-destroyed history with nothing on screen about it.

        Reported the way a rejected sweep is, and for the same reason: the
        confirmation stays open, because the associate is looking at it and
        the list is not clear. The rows that did go are still pruned above —
        those chats really are gone — and a chat kept running is still named,
        because "could not take everything" and "would not take a live chat"
        are different sentences and the associate is owed both.
      */
      if (result.chats_failed > 0) {
        setDeleteAllFailure(sweepFailureMessage(result.chats_failed));
      } else {
        setConfirmingDeleteAll(false);
      }

      await loadPlansData(true);
    } catch (error) {
      /*
        The list is still there. Closing on a rejected sweep would tell the
        associate it is clear when it is not, so the dialog stays open and
        says why, same as the row's own confirmation.
      */
      setDeleteAllFailure(
        error instanceof Error ? error.message : String(error)
      );
    } finally {
      setDeletingAll(false);
    }
  }, [chats, loadPlansData, navigate, selectedChatId]);

  if (!isDesktopDrawer) return null;

  return (
    <OverlayDrawer
      position="start"
      aria-label={CHAT_HISTORY_LABEL}
      open={drawerOpen}
      onOpenChange={(_, data) => {
        if (data.open) {
          dispatch(chatHistoryDrawerSetOpen(true));
          return;
        }
        closeDrawer();
      }}
    >
      <DrawerBody>
      <PanelLeft id={CHAT_HISTORY_DRAWER_ID}>
        <PanelLeftToolbar
          linkTo={onLeavingChat ? undefined : "/"}
          onTitleClick={onLeavingChat ? handleLogoClick : undefined}
          panelTitle={ASSISTANT_NAME}
          panelIcon={<StoreAssistantLogo />}
        >
        </PanelLeftToolbar>

        {/*
          No team picker (issue #25). Choosing between specialists is the lane
          router's job and the orchestrator's job; an associate mid-shift has no
          basis for the choice, and asking them to make it turns getting an
          answer into a routing decision. The upload dialog goes with it — a
          picker with one entry is still a picker, and it was also the last way
          a suppressed stock content pack could reach the surface.
        */}
        {/*
          The list-level control (#76, ADR-026). Disabled with nothing to
          take, the same fail-closed reasoning the row's own menu item uses:
          a control offered over an empty or all-running list is one the
          route would answer with nothing deleted.
        */}
        <div className="tab tab-delete-all-chats">
          <Button
            appearance="subtle"
            size="small"
            icon={<Delete20Regular />}
            disabled={deletableChatsCount === 0}
            onClick={() => {
              setKeptRunningNotice(null);
              setConfirmingDeleteAll(true);
            }}
          >
            {DELETE_ALL_CHATS_LABEL}
          </Button>
        </div>

        {keptRunningNotice !== null && (
          /*
            Stays on screen until the next sweep, rather than a toast: it
            reports what the last one actually did, and the associate reading
            it is looking at this panel, not a corner nothing has mounted a
            Toaster in.
          */
          <Caption1 className="chat-panel-kept-running-notice" role="status">
            {keptRunningNotice}
          </Caption1>
        )}

        <br />
        <ChatList
          chats={chats}
          onChatSelect={handleChatSelect}
          onChatDelete={handleChatDelete}
          loading={plansLoading}
          selectedChatId={selectedChatId ?? undefined}
          isLoadingTeam={isLoadingTeam}
        />

        <Dialog
          open={confirmingDeleteAll}
          onOpenChange={(_, data) => {
            if (data.open || deletingAll) return;
            setConfirmingDeleteAll(false);
            setDeleteAllFailure(null);
          }}
        >
          <DialogSurface>
            <DialogBody>
              <DialogTitle>{DELETE_ALL_CHATS_TITLE}</DialogTitle>
              <DialogContent>
                {/*
                  The count is stated here (#76) — the whole point of a
                  list-level control is reached for once the list is long
                  enough that naming every row would not fit.
                */}
                <div>{deleteAllChatsWarning(deletableChatsCount)}</div>
                {deleteAllFailure !== null && (
                  <div className="task-delete-failure" role="alert">
                    <strong>{DELETE_ALL_FAILED_TITLE}</strong>
                    <div>{deleteAllFailure}</div>
                  </div>
                )}
              </DialogContent>
              <DialogActions>
                <Button
                  appearance="secondary"
                  disabled={deletingAll}
                  onClick={() => {
                    setConfirmingDeleteAll(false);
                    setDeleteAllFailure(null);
                  }}
                >
                  {CANCEL_DELETE_LABEL}
                </Button>
                <Button
                  appearance="primary"
                  disabled={deletingAll}
                  onClick={handleDeleteAllChats}
                >
                  {CONFIRM_DELETE_ALL_LABEL}
                </Button>
              </DialogActions>
            </DialogBody>
          </DialogSurface>
        </Dialog>

        <PanelFooter>
          {/*
            No identity here. It lives in the conversation's header instead
            (issue #25): this panel is hidden at the phone breakpoint, and the
            associate's screen is a phone — an identity claim the associate
            cannot see is not a claim. A second one here would also be a second
            place for #27's sign-in to have to stay in step with.
          */}
          <div className="panel-footer-content" />
        </PanelFooter>
      </PanelLeft>
        </DrawerBody>
    </OverlayDrawer>
  );
};

const MemoizedChatPanelLeft = React.memo(ChatPanelLeft);
MemoizedChatPanelLeft.displayName = 'ChatPanelLeft';
export default MemoizedChatPanelLeft;
