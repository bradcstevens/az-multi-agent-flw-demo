import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
  Button,
  Menu,
  MenuTrigger,
  Caption1,
  Body1,
  Skeleton,
  SkeletonItem,
} from "@fluentui/react-components";
import { MoreHorizontal20Regular } from "@fluentui/react-icons";
import React from "react";
import "../../styles/TaskList.css";

interface Task {
  id: string;
  name: string;
  status: "inprogress" | "completed";
  date?: string;
}

interface TaskListProps {
  inProgressTasks: Task[];
  completedTasks: Task[];
  onTaskSelect: (taskId: string) => void;
  loading?: boolean;
  selectedTaskId?: string;
}

const TaskList: React.FC<TaskListProps> = ({
  inProgressTasks,
  completedTasks,
  onTaskSelect,
  loading,
  selectedTaskId,
}) => {
  const renderTaskItem = (task: Task) => {
    const isActive = task.id === selectedTaskId;

    return (
      <div
        key={task.id}
        className={`task-tab${isActive ? " active" : ""}`}
        onClick={() => onTaskSelect(task.id)}
      >
        <div className="sideNavTick" />
        <div className="left">
          <div>{task.name}</div>
          {task.date && (
            <Caption1 className="task-list-task-date">{task.date}</Caption1>
          )}
        </div>
        <Menu>
          <MenuTrigger>
            <Button
              appearance="subtle"
              icon={<MoreHorizontal20Regular />}
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
              className="task-menu-button"
            />
          </MenuTrigger>
        </Menu>
      </div>
    );
  };

  const renderSkeleton = (key: string) => (
    <div
      key={key}
      style={{
        padding: "8px",
        borderRadius: 6,
        pointerEvents: "none",
        cursor: "default",
        backgroundColor: "transparent",
      }}
    >
      <Skeleton aria-label="Loading task">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <SkeletonItem
            shape="rectangle"
            animation="wave"
            style={{ width: "100%", height: 24, borderRadius: 4 }}
          />
        </div>
      </Skeleton>
    </div>
  );

  return (
    <Accordion defaultOpenItems={["inprogress"]} collapsible>
      <AccordionItem value="inprogress">
        <AccordionHeader
          expandIconPosition="end"
          style={{
            color: "var(--colorNeutralForeground3)",
            padding: "0px 16px 0px 0",
            backgroundColor: "transparent",
            cursor: "pointer",
            justifyContent: "space-between",
            height: "40px",
          }}
        >
          <Body1>In progress</Body1>
        </AccordionHeader>

        <AccordionPanel style={{ margin: "8px" }}>
          {loading && inProgressTasks.length === 0
            ? [...Array(3)].map((_, i) =>
                renderSkeleton(`inprogress-skel-${i}`)
              )
            : inProgressTasks.map(renderTaskItem)}
        </AccordionPanel>
      </AccordionItem>

      <AccordionItem value="completed">
        <AccordionHeader
          expandIconPosition="end"
          style={{
            color: "var(--colorNeutralForeground3)",
            padding: "0px 16px 0px 0",
            backgroundColor: "transparent",
            cursor: "pointer",
            justifyContent: "space-between",
            height: "32px",
          }}
        >
          <Body1>Completed</Body1>
        </AccordionHeader>

        <AccordionPanel style={{ margin: "8px" }}>
          {loading && completedTasks.length === 0
            ? [...Array(2)].map((_, i) =>
                renderSkeleton(`completed-skel-${i}`)
              )
            : completedTasks.map(renderTaskItem)}
        </AccordionPanel>
      </AccordionItem>
    </Accordion>
  );
};

export default TaskList;
