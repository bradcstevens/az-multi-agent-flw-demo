import {
  Button,
  Caption1,
  Skeleton,
  SkeletonItem,
} from "@fluentui/react-components";
import { EyeOff20Regular } from "@fluentui/react-icons";
import React from "react";
import "../../styles/TaskList.css";
import { Task, TaskListProps } from "@/models";
import {
  Accordion,
  AccordionHeader,
  AccordionItem,
  AccordionPanel,
} from "@fluentui/react-components";
import {
  HIDE_COMPLETED_LABEL,
  NO_COMPLETED_TASKS_MESSAGE,
  hideCompletedTasks,
} from "../../models/hiddenCompletedTasks";
import useHiddenCompletedTasks from "../../hooks/useHiddenCompletedTasks";

const TaskList: React.FC<TaskListProps> = ({
  completedTasks,
  onTaskSelect,
  loading,
  selectedTaskId,
  isLoadingTeam
}) => {
  const hidden = useHiddenCompletedTasks();
  const isLoading = Boolean(loading || isLoadingTeam);
  const visibleTasks = React.useMemo(
    () => completedTasks.filter((task) => !hidden.has(task.id)),
    [completedTasks, hidden]
  );

  const renderTaskItem = (task: Task) => {
    const isActive = task.id === selectedTaskId;

    return (
      <div
        key={task.id}
        className={`task-tab${isActive ? " active" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => onTaskSelect(task.id)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onTaskSelect(task.id);
          }
        }}
      >
        <div className="sideNavTick" />
        <div className="left">
          <div className="task-name-truncated" title={task.name}>
            {task.name}
          </div>
          {task.date && task.status == "completed" && (
            <Caption1 className="task-list-task-date">{task.date}</Caption1>
          )}
        </div>
        {/*
          No row menu. This row used to carry a Fluent `Menu` with a
          `MenuTrigger` and no `MenuPopover` at all, whose `onClick` called
          `stopPropagation` and nothing else (#66). Measured while removing it:
          on `@fluentui/react-components` 9.64 a `Menu` with one child renders
          *nothing* — the trigger never reaches the DOM — so the row has been
          carrying an icon button that no test and no screen reader could see,
          and no browser could click. Dead twice over, which is why
          `TaskList.test` guards it by reading this file rather than the DOM.
          Clearing is list-level because the need is list-level, so nothing
          belongs here.
        */}
      </div>
    );
  };

  const renderSkeleton = (key: string) => (
    <div key={key} className="task-skeleton-container">
      <Skeleton aria-label="Loading task">
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
            The hide control is a sibling of the accordion's own toggle rather
            than a child of it: `AccordionHeader` renders its children *inside*
            a button, and a button inside a button is not markup a screen
            reader can offer as two things to do.
          */}
          <div className="task-list-completed-header">
            <AccordionHeader expandIconPosition="end">
              Completed
            </AccordionHeader>
            {!isLoading && (
              <Button
                appearance="subtle"
                size="small"
                icon={<EyeOff20Regular />}
                className="task-list-hide-completed"
                /*
                  It hides; it never deletes (ADR-022). Every plan stays in
                  Cosmos — which is what the intermittency work behind #47 and
                  #54 read — so a label saying *delete* would be the surface
                  saying something that is not so.
                */
                aria-label={HIDE_COMPLETED_LABEL}
                title={
                  visibleTasks.length
                    ? HIDE_COMPLETED_LABEL
                    : "Nothing left to hide"
                }
                /*
                  `disabledFocusable`, not `disabled`: a natively-disabled
                  control leaves the tab order, so the panel's only affordance
                  would disappear for a keyboard user rather than say why it
                  cannot be used.
                */
                disabledFocusable={!visibleTasks.length}
                onClick={() =>
                  hideCompletedTasks(completedTasks.map((task) => task.id))
                }
              />
            )}
          </div>
          <AccordionPanel>
            {isLoading
              ? Array.from({ length: 5 }, (_, i) =>
                renderSkeleton(`completed-${i}`)
              )
              : visibleTasks.length
                ? visibleTasks.map(renderTaskItem)
                : (
                  /*
                    True whether the list is empty or merely hidden. A bare
                    "No completed tasks" stops being true the moment a clear
                    hides some, and would have the panel claiming the records
                    are gone when they are not.
                  */
                  <Caption1 className="task-list-empty">
                    {NO_COMPLETED_TASKS_MESSAGE}
                  </Caption1>
                )}
          </AccordionPanel>
        </AccordionItem>

      </Accordion>
    </div>
  );
};

const MemoizedTaskList = React.memo(TaskList);
MemoizedTaskList.displayName = 'TaskList';
export default MemoizedTaskList;
