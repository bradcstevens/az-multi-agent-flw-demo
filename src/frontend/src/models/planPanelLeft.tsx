import { TeamConfig } from './Team';

export interface PlanPanelLefProps {
    reloadTasks?: boolean;
    onNewTaskButton: () => void;
    restReload?: () => void;
    onTeamSelect?: (team: TeamConfig) => void;
    selectedTeam?: TeamConfig | null;
}