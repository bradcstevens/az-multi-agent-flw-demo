import React from "react";

import { Button } from "@fluentui/react-components";
import { History20Filled, MoreHorizontalRegular, TaskListSquareLtr20Regular, TaskListSquareLtrFilled } from "@fluentui/react-icons";
import PanelRight from "@/coral/components/Panels/PanelRight";
import PanelRightToolbar from "@/coral/components/Panels/PanelRightToolbar";
import TaskDetails from "./TaskDetails";



interface PlanPanelRightProps {
    activeTask: any | null;
    onAddAgent: () => void;
    onAddHuman: () => void;
}

const PlanPanelRight: React.FC<PlanPanelRightProps> = ({
    activeTask,
    onAddAgent,
    onAddHuman,
}) => {
    if (!activeTask) return null;

    return (
        <PanelRight
            panelWidth={450}
            defaultClosed={false}
            panelResize={true}
            panelType="first"
        >
            <PanelRightToolbar panelTitle="Task Details" panelIcon={<TaskListSquareLtr20Regular />}>

            </PanelRightToolbar>

            <div >
                <TaskDetails
                    taskName={activeTask.name}
                    subTasks={activeTask.subTasks}
                    agents={activeTask.agents}
                    humans={activeTask.humans}
                />
            </div>
        </PanelRight>
    );
};

export default PlanPanelRight;
