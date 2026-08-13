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
import TaskList from "./TaskList";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Plan, PlanPanelLefProps, Task } from "@/models";
import { apiService } from "@/api";
import { TaskService } from "@/store";
import "../../styles/PlanPanelLeft.css";
import { ASSISTANT_NAME } from "../../models/storeSurface";
import StoreAssistantLogo from "../branding/StoreAssistantLogo";

const PlanPanelLeft: React.FC<PlanPanelLefProps> = ({
  reloadTasks,
  onNewTaskButton,
  restReload,
  onNavigationWithAlert,
  isLoadingTeam
}) => {
  const { dispatchToast } = useToastController("toast");
  const navigate = useNavigate();
  const { planId } = useParams<{ planId: string }>();

  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
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
    if (reloadTasks) {
      loadPlansData(true); // Force refresh when reloadTasks is true
    }
  }, [loadPlansData, reloadTasks]);
  useEffect(() => {
    if (plans) {
      const { completed } =
        TaskService.transformPlansToTasks(plans);
      setCompletedTasks(completed);
    }
  }, [plans]);

  useEffect(() => {
    if (plansError) {
      dispatchToast(
        <Toast>
          <ToastTitle>
            <ErrorCircle20Regular />
            Failed to load tasks
          </ToastTitle>
          <ToastBody>{plansError.message}</ToastBody>
        </Toast>,
        { intent: "error" }
      );
    }
  }, [plansError, dispatchToast]);

  // Get the session_id that matches the current URL's planId
  const selectedTaskId =
    plans?.find((plan) => plan.id === planId)?.session_id ?? null;

  const handleTaskSelect = useCallback(
    (taskId: string) => {
      const performNavigation = () => {
        const selectedPlan = plans?.find(
          (plan: Plan) => plan.session_id === taskId
        );
        if (selectedPlan) {
          navigate(`/plan/${selectedPlan.id}`);
        }
      };

      if (onNavigationWithAlert) {
        onNavigationWithAlert(performNavigation);
      } else {
        performNavigation();
      }
    },
    [plans, navigate, onNavigationWithAlert]
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
          <Tooltip content="New task" relationship={"label"} />
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
          onClick={onNewTaskButton}
          tabIndex={0} // ✅ allows tab focus
          role="button" // ✅ announces as button
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onNewTaskButton();
            }
          }}
        >
          <div className="tab tab-new-task-icon">
            <ChatAdd20Regular />
          </div>
          <Body1Strong>New task</Body1Strong>
        </div>

        <br />
        <TaskList
          completedTasks={completedTasks}
          onTaskSelect={handleTaskSelect}
          loading={plansLoading}
          selectedTaskId={selectedTaskId ?? undefined}
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

const MemoizedPlanPanelLeft = React.memo(PlanPanelLeft);
MemoizedPlanPanelLeft.displayName = 'PlanPanelLeft';
export default MemoizedPlanPanelLeft;
