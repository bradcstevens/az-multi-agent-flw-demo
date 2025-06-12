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
import { Task, TaskListProps } from "@/models";





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
      className="task-skeleton-container"
    >
      <Skeleton aria-label="Loading task">
        <div
          className="task-skeleton-content"
        >
          <SkeletonItem
            shape="rectangle"
            animation="wave"
            className="task-skeleton-item"
          />
        </div>
      </Skeleton>
    </div>
  );

  return (
    <Accordion defaultOpenItems={["inprogress"]} collapsible>      <AccordionItem value="inprogress">
      <AccordionHeader
        expandIconPosition="end"
        className="task-accordion-header-in-progress"
      >
        <Body1>In progress</Body1>
      </AccordionHeader>

      <AccordionPanel className="task-accordion-panel">
        {loading && inProgressTasks.length === 0
          ? [...Array(3)].map((_, i) =>
            renderSkeleton(`inprogress-skel-${i}`)
          )
          : inProgressTasks.map(renderTaskItem)}
      </AccordionPanel>
    </AccordionItem>      <AccordionItem value="completed">
        <AccordionHeader
          expandIconPosition="end"
          className="task-accordion-header-completed"
        >
          <Body1>Completed</Body1>
        </AccordionHeader>

        <AccordionPanel className="task-accordion-panel">
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
