// TaskDetails.tsx - Merged TSX + Styles

import { TaskDetailsProps } from "@/models";
import {
  Subtitle1,
  Text,
  Divider,
  Avatar,
  Checkbox,
  Body1,
  Body1Strong,
} from "@fluentui/react-components";
import {
  Add20Regular,
  CheckmarkCircle20Regular,
  Dismiss20Regular,
  CircleHalfFill20Regular,
  CheckboxChecked20Regular,
  DismissSquare20Regular,
} from "@fluentui/react-icons";
import React from "react";
import { TaskService } from "@/services";
import PanelLeftToolbar from "@/coral/components/Panels/PanelLeftToolbar";
import PanelRightToolbar from "@/coral/components/Panels/PanelRightToolbar";

const TaskDetails: React.FC<TaskDetailsProps> = ({
  planData,
  OnApproveStep,
  OnRejectStep,
}) => {
  const completedCount = planData.plan.completed || 0;
  const total = planData.plan.total_steps || 1;
  const subTasks = planData.steps || [];
  const progress = completedCount / total;
  const agents = planData.agents || [];

  const renderStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <CheckmarkCircle20Regular
            style={{ color: "var(--colorPaletteGreenForeground1)" }}
          />
        );
      case "planned":
        return (
          <CircleHalfFill20Regular
            style={{ color: "var(--colorBrandForeground1)" }}
          />
        );
      case "removed":
        return (
          <Dismiss20Regular
            style={{ color: "var(--colorPaletteRedForeground1)" }}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "auto",
      }}
    >
      <PanelRightToolbar panelTitle="Progress"></PanelRightToolbar>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          borderBottom: "1px solid var(--colorNeutralStroke2)",
          padding: "0px 16px 24px 16px",
          gap: "24px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              padding: "12px",
            //   border: "1px solid var(--colorNeutralStroke1)",
              backgroundColor:'var(--colorNeutralBackground4)',
              borderRadius: "var(--borderRadiusXLarge)",
              width:'100%'
            }}
          >
            <div
              style={{
                position: "relative",
                width: 56,
                height: 56,
                marginRight: 16,
              }}
            >
              <svg width="56" height="56" viewBox="0 0 56 56">
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  fill="none"
                  stroke="var(--colorNeutralBackground1)"
                  strokeWidth="8"
                />
                <circle
                  cx="28"
                  cy="28"
                  r="24"
                  fill="none"
                  stroke="var(--colorPaletteSeafoamBorderActive)"
                  strokeWidth="8"
                  strokeDasharray={`${progress * 150.8} 150.8`}
                  strokeDashoffset="0"
                  strokeLinecap="round"
                  transform="rotate(-90 28 28)"
                />
              </svg>
              <Body1Strong
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  transform: "translate(-50%, -50%)",
                  paddingBottom:'2px'
                }}
              >
                {/* {completedCount}/{total} */}
              </Body1Strong>
            </div>
            <div>
              <Body1Strong style={{}}>{planData.plan.initial_goal}</Body1Strong>
              <br />
              <Text size={200}>
                {planData.plan.completed} of {total} completed
              </Text>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {subTasks.map((subtask) => {
            const { description } = TaskService.splitSubtaskAction(
              subtask.action
            );
            const canInteract = planData.hasHumanClarificationRequest;

            return (
              <div
                key={subtask.id}
                style={{ display: "flex", alignItems: "center", gap: 8 }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    width: 24,
                    height: 24,
                  }}
                >
                  {renderStatusIcon(subtask.status)}
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flex: 1,
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--fontSizeBase300)",
                      fontWeight: "var(--fontWeightSemibold)",
                      flex: 1,
                    }}
                  >
                    {description}
                  </span>
                  <div
                    style={{ display: "flex", alignItems: "center", gap: 8 }}
                  >
                    <CheckboxChecked20Regular
                      onClick={
                        canInteract ? () => OnApproveStep(subtask) : undefined
                      }
                      style={{
                        cursor: canInteract ? "pointer" : "not-allowed",
                        padding: 4,
                        borderRadius: "var(--borderRadiusSmall)",
                      }}
                    />
                    <DismissSquare20Regular
                      onClick={
                        canInteract ? () => OnRejectStep(subtask) : undefined
                      }
                      style={{
                        cursor: canInteract ? "pointer" : "not-allowed",
                        padding: 4,
                        borderRadius: "var(--borderRadiusSmall)",
                      }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div
        style={{
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div
          style={{
            padding: "18px 16px",
            maxHeight: "56px",
          }}
        >
          <Body1Strong>Agents</Body1Strong>
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 16,
            padding: "0 16px 16px 16px",
          }}
        >
          {agents.map((agent) => (
            <div
              key={agent}
              style={{ display: "flex", alignItems: "center", gap: 12 }}
            >
              <Avatar name={agent} size={32} badge={{ status: "available" }} />
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span
                  style={{
                    fontSize: "var(--fontSizeBase300)",
                    fontWeight: "var(--fontWeightSemibold)",
                  }}
                >
                  {TaskService.cleanTextToSpaces(agent)}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default TaskDetails;
