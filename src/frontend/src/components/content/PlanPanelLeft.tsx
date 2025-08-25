// DEV NOTE: Left plan panel. Change: the "Current team" tile is now the trigger
// that opens SettingsButton’s modal. Hover → bg to background3, chevron to fg1.

import PanelLeft from "@/coral/components/Panels/PanelLeft";
import PanelLeftToolbar from "@/coral/components/Panels/PanelLeftToolbar";
import {
  Body1Strong,
  Button,
  Caption1,
  Divider,
  Subtitle1,
  Subtitle2,
  Toast,
  ToastBody,
  ToastTitle,
  Tooltip,
  useToastController,
} from "@fluentui/react-components";
import {
  Add20Regular,
  ArrowSwap20Regular,
  ChatAdd20Regular,
  ChevronUpDown20Regular,
  ErrorCircle20Regular,
} from "@fluentui/react-icons";
import TaskList from "./TaskList";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PlanPanelLefProps, PlanWithSteps, Task, UserInfo } from "@/models";
import { apiService } from "@/api";
import { TaskService } from "@/services";
import MsftColor from "@/coral/imports/MsftColor";
import ContosoLogo from "../../coral/imports/ContosoLogo";
import "../../styles/PlanPanelLeft.css";
import PanelFooter from "@/coral/components/Panels/PanelFooter";
import PanelUserCard from "../../coral/components/Panels/UserCard";
import { getUserInfoGlobal } from "@/api/config";
import SettingsButton from "../common/SettingsButton";
import TeamSettingsButton from "../common/TeamSettingsButton";
import { TeamConfig } from "../../models/Team";

const PlanPanelLeft: React.FC<PlanPanelLefProps> = ({
  reloadTasks,
  restReload,
  onTeamSelect,
  onTeamUpload,
  selectedTeam: parentSelectedTeam,
}) => {
  const { dispatchToast } = useToastController("toast");
  const navigate = useNavigate();
  const { planId } = useParams<{ planId: string }>();

  const [inProgressTasks, setInProgressTasks] = useState<Task[]>([]);
  const [completedTasks, setCompletedTasks] = useState<Task[]>([]);
  const [plans, setPlans] = useState<PlanWithSteps[] | null>(null);
  const [plansLoading, setPlansLoading] = useState<boolean>(false);
  const [plansError, setPlansError] = useState<Error | null>(null);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(getUserInfoGlobal());

  // DEV NOTE: If parent gives a team, use that; otherwise manage local selection.
  const [localSelectedTeam, setLocalSelectedTeam] = useState<TeamConfig | null>(null);
  const selectedTeam = parentSelectedTeam || localSelectedTeam;

  // DEV NOTE: Load and transform plans → task lists.
  const loadPlansData = useCallback(async (forceRefresh = false) => {
    try {
      setPlansLoading(true);
      setPlansError(null);
      const plansData = await apiService.getPlans(undefined, !forceRefresh);
      setPlans(plansData);
    } catch (error) {
      console.log("Failed to load plans:", error);
      setPlansError(error instanceof Error ? error : new Error("Failed to load plans"));
    } finally {
      setPlansLoading(false);
    }
  }, []);

  useEffect(() => {
    if (reloadTasks) {
      loadPlansData();
      restReload?.();
    }
  }, [reloadTasks, loadPlansData, restReload]);

  useEffect(() => {
    loadPlansData();
  }, [loadPlansData]);

  useEffect(() => {
    if (plans) {
      const { inProgress, completed } = TaskService.transformPlansToTasks(plans);
      setInProgressTasks(inProgress);
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

  // DEV NOTE: Pick the session_id of the plan currently in the URL.
  const selectedTaskId = plans?.find((plan) => plan.id === planId)?.session_id ?? null;

  // DEV NOTE: Navigate when a task is chosen from the list.
  const handleTaskSelect = useCallback(
    (taskId: string) => {
      const selectedPlan = plans?.find((plan: PlanWithSteps) => plan.session_id === taskId);
      if (selectedPlan) {
        navigate(`/plan/${selectedPlan.id}`);
      }
    },
    [plans, navigate]
  );

  // DEV NOTE: Bubble selection up if parent wants it; otherwise update local state + toast.
  const handleTeamSelect = useCallback(
    (team: TeamConfig | null) => {
      if (onTeamSelect) {
        onTeamSelect(team);
      } else {
        if (team) {
          setLocalSelectedTeam(team);
          dispatchToast(
            <Toast>
              <ToastTitle>Team Selected</ToastTitle>
              <ToastBody>
                {team.name} team has been selected with {team.agents.length} agents
              </ToastBody>
            </Toast>,
            { intent: "success" }
          );
        } else {
          setLocalSelectedTeam(null);
          dispatchToast(
            <Toast>
              <ToastTitle>Team Deselected</ToastTitle>
              <ToastBody>No team is currently selected</ToastBody>
            </Toast>,
            { intent: "info" }
          );
        }
      }
    },
    [onTeamSelect, dispatchToast]
  );

  // DEV NOTE (UI): Hover state for the "Current team" tile to flip bg + chevron color.
  const [teamTileHovered, setTeamTileHovered] = useState(false);

  // DEV NOTE: Build the trigger tile that opens the modal.
const teamTrigger = (
  <div
    role="button"
    tabIndex={0}
    aria-label="Open team selector"
    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.preventDefault(); }}
    onMouseEnter={() => setTeamTileHovered(true)}
    onMouseLeave={() => setTeamTileHovered(false)}
    style={{
      margin: "16px 16px",
      backgroundColor: teamTileHovered
        ? "var(--colorNeutralBackground3)"
        : "var(--colorNeutralBackground2)",
      padding: "12px 16px",
      textAlign: "left",
      borderRadius: 8,
      cursor: "pointer",
      outline: "none",
      userSelect: "none",
    }}
  >
    <div style={{ display: "flex", alignItems: "center" }}>
      <div style={{ width: "100%" }}>
        <Caption1 style={{ color: "var(--colorNeutralForeground3)" }}>
          {selectedTeam ? "Current team" : "Choose a team"}
        </Caption1>
        <br />
        <Body1Strong>{selectedTeam ? selectedTeam.name : "No team selected"}</Body1Strong>
      </div>
      <ChevronUpDown20Regular
        style={{
          color: teamTileHovered
            ? "var(--colorNeutralForeground1)"
            : "var(--colorNeutralForeground3)",
          flexShrink: 0,
        }}
      />
    </div>
  </div>
);

  return (
    <div style={{ flexShrink: 0, display: "flex", overflow: "hidden" }}>
      <PanelLeft panelWidth={280} panelResize={true}>
        <PanelLeftToolbar linkTo="/" panelTitle="Zava" panelIcon={<ContosoLogo />}>
          <br />
          <Tooltip content="New task" relationship={"label"} />
        </PanelLeftToolbar>

        {/* DEV NOTE: SettingsButton rendered with a custom trigger (the tile above).
            Clicking the tile opens the modal. */}
<TeamSettingsButton selectedTeam={selectedTeam} onTeamSelect={handleTeamSelect}>
  {teamTrigger}
</TeamSettingsButton>

        <br />
        <div
          className="tab tab-new-task"
          onClick={() => navigate("/", { state: { focusInput: true } })}
          tabIndex={0}
          role="button"
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              navigate("/", { state: { focusInput: true } });
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
          inProgressTasks={inProgressTasks}
          completedTasks={completedTasks}
          onTaskSelect={handleTaskSelect}
          loading={plansLoading}
          selectedTaskId={selectedTaskId ?? undefined}
        />

        <PanelFooter>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              width: "100%",
            }}
          >
            <PanelUserCard
              name={userInfo ? userInfo.user_first_last_name : "Guest"}
              size={32}
            />
          </div>
        </PanelFooter>
      </PanelLeft>
    </div>
  );
};

export default PlanPanelLeft;
