import React, { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Button,
  Text,
  Card,
  CardHeader,
  useToastController,
  Badge,
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
import Octo from "../coral/imports/Octopus.png"; // 🐙 Your animated PNG
import { PanelRightContract, PanelRightExpand } from "@/coral/imports/bundleicons";
import PanelRightToggles from "@/coral/components/Header/PanelRightToggles";

const PlanPage: React.FC = () => {
  const { planId } = useParams<{ planId: string }>();
  const navigate = useNavigate();
  const { showToast } = useInlineToaster();

  const [input, setInput] = useState("");
  const [planData, setPlanData] = useState<ProcessedPlanData | any>(null);
  const [loading, setLoading] = useState<boolean>(true);
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

  useEffect(() => {
    if (!loading) return;
    let index = 0;
    const interval = setInterval(() => {
      index = (index + 1) % loadingMessages.length;
      setLoadingMessage(loadingMessages[index]);
    }, 2000);
    return () => clearInterval(interval);
  }, [loading]);

  const loadPlanData = useCallback(async () => {
    if (!planId) return;
    try {
      setPlanData(null);
      setLoading(true);
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
  }, [planId]);

  const loadPlanData2 = useCallback(async () => {
    if (!planId) return;
    try {
      setError(null);
      const data = await PlanDataService.fetchPlanData(planId);
      setPlanData(data);
    } catch (err) {
      setError(
        err instanceof Error ? err : new Error("Failed to load plan data")
      );
    }
  }, [planId]);

  const handleOnchatSubmit = useCallback(
    async (chatInput: string) => {
      if (!planData?.plan) return;
      showToast("Submitting clarification...", "progress", {
        dismissible: false,
      });
      try {
        await PlanDataService.submitClarification(
          planData.plan.id,
          planData.plan.session_id,
          chatInput
        );
        showToast("Clarification submitted successfully", "success");
        await loadPlanData2();
      } catch (error) {
        showToast("Failed to submit clarification", "error");
        console.error("Failed to submit clarification:", error);
      } finally {
        setInput("");
      }
    },
    [planData, loadPlanData2]
  );

  const handleApproveStep = useCallback(
    async (step: Step) => {
      setProcessingSubtaskId(step.id);
      showToast("Submitting approval...", "progress", { dismissible: false });
      try {
        await PlanDataService.approveStep(step);
        showToast("Step approved successfully", "success");
        await loadPlanData2();
      } catch (error) {
        showToast("Failed to approve step", "error");
        console.error("Failed to approve step:", error);
      } finally {
        setProcessingSubtaskId(null);
      }
    },
    [loadPlanData2]
  );

  const handleRejectStep = useCallback(
    async (step: Step) => {
      setProcessingSubtaskId(step.id);
      showToast("Submitting rejection...", "progress", { dismissible: false });
      try {
        await PlanDataService.rejectStep(step);
        showToast("Step rejected successfully", "success");
        await loadPlanData2();
      } catch (error) {
        showToast("Failed to reject step", "error");
        console.error("Failed to reject step:", error);
      } finally {
        setProcessingSubtaskId(null);
      }
    },
    [loadPlanData2]
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
          {/* 🐙 OCTO LOADING STATE BLOCK */}
          {loading && (
            <div
              style={{
                height: "100%",
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
                alignItems: "center",
                gap: "12px",
              }}
            >
              <img
                src={Octo}
                alt="Loading animation"
                style={{ width: 64, height: 64 }}
              />
              <Text>{loadingMessage}</Text>
            </div>
          )}

          {/* ✅ MAIN CONTENT RENDERING */}
          {!loading && (
            <>
<ContentToolbar
  panelTitle={planData?.plan?.initial_goal || 'Plan Details'}
  panelIcon={<Sparkle20Filled />}
>
  {/* Panel toggle with dynamic expand/contract icon */}
  <PanelRightToggles>
    <Button
      appearance="transparent"
      panelToggleIcon // 🧠 Typescript error. Leave in place
      title="Toggle Panel View"
    />
  </PanelRightToggles>
</ContentToolbar>


              <PlanChat
                planData={planData}
                OnChatSubmit={handleOnchatSubmit}
                loading={loading}
                input={input}
              />
            </>
          )}
        </Content>

        <PlanPanelRight
          planData={planData}
          OnApproveStep={handleApproveStep}
          OnRejectStep={handleRejectStep}
          processingSubtaskId={processingSubtaskId}
          loading={loading}
        />
      </CoralShellRow>
    </CoralShellColumn>
  );
};

export default PlanPage;
