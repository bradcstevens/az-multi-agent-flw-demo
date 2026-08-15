import React from "react";
import PanelLeft from "@/commonComponents/components/Panels/PanelLeft";
import PanelLeftToolbar from "@/commonComponents/components/Panels/PanelLeftToolbar";
import PanelFooter from "@/commonComponents/components/Panels/PanelFooter";
import {
  Body1Strong,
  Toast,
  ToastBody,
  ToastTitle,
  Tooltip,
  useToastController,
} from "@fluentui/react-components";
import {
  ChatAdd20Regular,
  ErrorCircle20Regular,
} from "@fluentui/react-icons";
import ChatList from "./ChatList";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Chat, ChatPanelLeftProps, Plan } from "@/models";
import { apiService } from "@/api";
import { TaskService } from "@/store";
import "../../styles/ChatPanelLeft.css";
import { ASSISTANT_NAME } from "../../models/storeSurface";
import StoreAssistantLogo from "../branding/StoreAssistantLogo";

const ChatPanelLeft: React.FC<ChatPanelLeftProps> = ({
  reloadChats,
  onNewChatButton,
  restReload,
  onNavigationWithAlert,
  isLoadingTeam
}) => {
  const { dispatchToast } = useToastController("toast");
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

  const loadPlansData = useCallback(async (forceRefresh = false) => {
    try {
      setPlansLoading(true);
      setPlansError(null);
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
      const performNavigation = () => {
        /*
          The row carries the plan it opens (#71). Searching the plans for one
          matching the row's session took the *first* match, so on the
          walkthrough's centrepiece pair — a troubleshooting turn and the
          escalation that continues its session (ADR-024) — the escalation was
          unreachable from this panel.
        */
        const selectedChat = chats.find((chat) => chat.id === chatId);
        if (selectedChat) {
          navigate(`/chat/${selectedChat.planId}`);
        }
      };

      if (onNavigationWithAlert) {
        onNavigationWithAlert(performNavigation);
      } else {
        performNavigation();
      }
    },
    [chats, navigate, onNavigationWithAlert]
  );

  const handleLogoClick = useCallback(() => {
    const performNavigation = () => {
      navigate("/");
    };

    if (onNavigationWithAlert) {
      onNavigationWithAlert(performNavigation);
    } else {
      performNavigation();
    }
  }, [navigate, onNavigationWithAlert]);

  return (
    <div className="panel-left-container">
      <PanelLeft panelWidth={280} panelResize={true}>
        <PanelLeftToolbar
          linkTo={onNavigationWithAlert ? undefined : "/"}
          onTitleClick={onNavigationWithAlert ? handleLogoClick : undefined}
          panelTitle={ASSISTANT_NAME}
          panelIcon={<StoreAssistantLogo />}
        >
          <Tooltip content="New chat" relationship={"label"} />
        </PanelLeftToolbar>

        {/*
          No team picker (issue #25). Choosing between specialists is the lane
          router's job and the orchestrator's job; an associate mid-shift has no
          basis for the choice, and asking them to make it turns getting an
          answer into a routing decision. The upload dialog goes with it — a
          picker with one entry is still a picker, and it was also the last way
          a suppressed stock content pack could reach the surface.
        */}
        <div
          className="tab tab-new-task"
          onClick={onNewChatButton}
          tabIndex={0} // ✅ allows tab focus
          role="button" // ✅ announces as button
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onNewChatButton();
            }
          }}
        >
          <div className="tab tab-new-task-icon">
            <ChatAdd20Regular />
          </div>
          <Body1Strong>New chat</Body1Strong>
        </div>

        <br />
        <ChatList
          chats={chats}
          onChatSelect={handleChatSelect}
          loading={plansLoading}
          selectedChatId={selectedChatId ?? undefined}
          isLoadingTeam={isLoadingTeam}
        />

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
    </div>
  );
};

const MemoizedChatPanelLeft = React.memo(ChatPanelLeft);
MemoizedChatPanelLeft.displayName = 'ChatPanelLeft';
export default MemoizedChatPanelLeft;
