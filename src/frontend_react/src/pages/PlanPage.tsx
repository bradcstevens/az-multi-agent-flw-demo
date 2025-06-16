import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Button,
  Text,
  Card,
  CardHeader,
  useToastController,
  Spinner,
  Badge,
  ToggleButton,
} from "@fluentui/react-components";
import {
  Add20Regular,
  ArrowLeft24Regular,
  ErrorCircle24Regular,
  Person24Regular,
  CheckmarkCircle24Regular,
  AlertUrgent24Regular,
  Sparkle20Filled,
} from "@fluentui/react-icons";
import "../styles/PlanPage.css";
import CoralShellColumn from "../coral/components/Layout/CoralShellColumn";
import CoralShellRow from "../coral/components/Layout/CoralShellRow";
import Content from "../coral/components/Content/Content";
import { NewTaskService } from "../services/NewTaskService";
import { PlanDataService } from "../services/PlanDataService";
import { Step, ProcessedPlanData } from "@/models";
import PlanPanelLeft from "@/components/content/PlanPanelLeft";
import ContentToolbar from "@/coral/components/Content/ContentToolbar";
import PlanChat from "@/components/content/PlanChat";
import PlanPanelRight from "@/components/content/PlanPanelRight";
import InlineToaster, {
  useInlineToaster,
} from "../components/toast/InlineToaster";
import Octo from "../coral/imports/Octopus.png"; // 🐙 Animated PNG loader
import PanelRightToggles from "@/coral/components/Header/PanelRightToggles";
import { TaskListSquareLtr } from "@/coral/imports/bundleicons";

/**
 * Page component for displaying a specific plan
 * Accessible via the route /plan/{plan_id}
 */
const PlanPage: React.FC = () => {
  const { planId } = useParams<{ planId: string }>();
  const navigate = useNavigate();
  const { showToast } = useInlineToaster();

  const [input, setInput] = useState("");
  const [planData, setPlanData] = useState<ProcessedPlanData | any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [submittingChatDisableInput, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);
  const [processingSubtaskId, setProcessingSubtaskId] = useState<string | null>(
    null
  );

  const loadingMessages = [
    "Initializing AI agents...",
    "Generating plan scaffolds...",
    "Optimizing task steps...",
    "Applying finishing touches...",
  ];
  const [loadingMessage, setLoadingMessage] = useState(loadingMessages[0]);

  // 🌀 Cycle loading messages while loading
  useEffect(() => {
    if (!loading) return;
    let index = 0;
    const interval = setInterval(() => {
      index = (index + 1) % loadingMessages.length;
      setLoadingMessage(loadingMessages[index]);
    }, 2000);
    return () => clearInterval(interval);
  }, [loading]);

  const loadPlanData = useCallback(
    async (navigate: boolean = true) => {
      if (!planId) return;

      try {
        setInput(""); // Clear input on new load
        if (navigate) {
          setPlanData(null);
          setLoading(true);
        }

        setError(null);
        const data = await PlanDataService.fetchPlanData(planId);
        console.log("Fetched plan data:", data);
        setPlanData(data);
      } catch (err) {
        console.error("Failed to load plan data:", err);
        setError(
          err instanceof Error ? err : new Error("Failed to load plan data")
        );
      } finally {
        setLoading(false);
      }
    },
    [planId]
  );

  const handleOnchatSubmit = useCallback(
    async (chatInput: string) => {
      setInput("");
      console.log("handleOnchatSubmit called with input:", chatInput);
      if (!chatInput.trim()) {
        showToast("Please enter a clarification", "error");
        return;
      }
      if (!planData?.plan) return;
      setSubmitting(true);
      showToast("Submitting clarification...", "progress");
      try {
        await PlanDataService.submitClarification(
          planData.plan.id,
          planData.plan.session_id,
          chatInput
        );
        setInput("");
        showToast("Clarification submitted successfully", "success");
        await loadPlanData(false);
      } catch (error) {
        showToast("Failed to submit clarification", "error");
        console.error("Failed to submit clarification:", error);
      } finally {
        setInput("");
        setSubmitting(false);
      }
    },
    [planData, loadPlanData]
  );

  const handleApproveStep = useCallback(
    async (step: Step) => {
      setProcessingSubtaskId(step.id);
      showToast("Submitting approval...", "progress");
      setSubmitting(true);
      try {
        await PlanDataService.stepStatus(step, true);
        showToast("Step approved successfully", "success");
        await loadPlanData(false);
      } catch (error) {
        showToast("Failed to approve step", "error");
        console.error("Failed to reject step:", error);
      } finally {
        setProcessingSubtaskId(null);
        setSubmitting(false);
      }
    },
    [loadPlanData]
  );

  const handleRejectStep = useCallback(
    async (step: Step) => {
      setProcessingSubtaskId(step.id);
      showToast("Submitting rejection...", "progress");
      setSubmitting(true);
      try {
        await PlanDataService.stepStatus(step, false);
        showToast("Step rejected successfully", "success");
        await loadPlanData(false);
      } catch (error) {
        showToast("Failed to reject step", "error");
        console.error("Failed to reject step:", error);
      } finally {
        setProcessingSubtaskId(null);
        setSubmitting(false);
      }
    },
    [loadPlanData]
  );

  useEffect(() => {
    loadPlanData();
  }, [loadPlanData]);

  const handleNewTaskButton = () => {
    NewTaskService.handleNewTaskFromPlan(navigate);
  };

  if (!planId) {
    return (
      <div style={{ padding: "20px" }}>
        <Text>Error: No plan ID provided</Text>
      </div>
    );
  }

  return (
    <CoralShellColumn>
      <CoralShellRow>
        <PlanPanelLeft onNewTaskButton={handleNewTaskButton} />

        <Content>
          {/* 🐙 Only replaces content body, not page shell */}
          {loading ? (
            <div
            className="loadingWrapper"

            >
              <img
                src={Octo}
                alt="Loading animation"
                style={{ width: 64, height: 64 }}
              />
              <Text>{loadingMessage}</Text>
            </div>
          ) : (
            <>
              <ContentToolbar
                panelTitle={planData?.plan?.initial_goal || "Plan Details"}
                panelIcon={<Sparkle20Filled />}
              >
                <PanelRightToggles>
                  <ToggleButton
                    appearance="transparent"
                    icon={<TaskListSquareLtr />}
                  />
                </PanelRightToggles>
              </ContentToolbar>
              <PlanChat
                planData={planData}
                OnChatSubmit={handleOnchatSubmit}
                loading={loading}
                submittingChatDisableInput={submittingChatDisableInput}
                input={input}
              />
            </>
          )}
        </Content>

        <PlanPanelRight
          planData={planData}
          OnApproveStep={handleApproveStep}
          OnRejectStep={handleRejectStep}
          submittingChatDisableInput={submittingChatDisableInput}
          processingSubtaskId={processingSubtaskId}
          loading={loading}
        />
      </CoralShellRow>
    </CoralShellColumn>
  );
};

export default PlanPage;
