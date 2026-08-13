/**
 * The left panel's props.
 *
 * `onTeamSelect` / `onTeamUpload` / `selectedTeam` / `isHomePage` were removed
 * with the team picker (issue #25). One assistant, one surface: the panel shows
 * the store assistant's name and the task history, and has nothing left to
 * choose between.
 */
export interface PlanPanelLefProps {
    reloadTasks: boolean;
    onNewTaskButton: () => void;
    restReload?: () => void;
    onNavigationWithAlert?: (navigationFn: () => void) => void;
    isLoadingTeam?: boolean;
}
