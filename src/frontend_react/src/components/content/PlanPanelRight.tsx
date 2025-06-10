import React from "react";

import { Button } from "@fluentui/react-components";
import { History20Filled, MoreHorizontalRegular, TaskListSquareLtr20Regular, TaskListSquareLtrFilled } from "@fluentui/react-icons";
import PanelRight from "@/coral/components/Panels/PanelRight";
import PanelRightToolbar from "@/coral/components/Panels/PanelRightToolbar";
import TaskDetails from "./TaskDetails";
import { TaskDetailsProps } from "@/models";


const PlanPanelRight: React.FC<TaskDetailsProps> = ({
    planData,
    OnApproveStep,
    OnRejectStep,
}) => {
    if (!planData) return null;

    return (
        <PanelRight
            panelWidth={450}
            defaultClosed={false}
            panelResize={true}
            panelType="first"
        >

            <div >
                <TaskDetails
                    planData={planData}
                    OnApproveStep={OnApproveStep}
                    OnRejectStep={OnRejectStep}
                />
            </div>
        </PanelRight>
    );
};

export default PlanPanelRight;
