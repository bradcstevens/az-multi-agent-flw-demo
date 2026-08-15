export interface Task {
    id: string;
    name: string;
    /**
     * The Plan this row opens — the chat's latest.
     *
     * A row is a Chat and a Chat is a Session (ADR-025), which can hold more
     * than one Plan. The row therefore carries the plan it opens rather than
     * leaving the caller to search the plans for one matching its session:
     * that search took the first match, so the escalation was unreachable
     * from the panel (#71).
     */
    planId: string;
    status: string;
    date?: string;
}

export interface TaskListProps {
    completedTasks: Task[];
    onTaskSelect: (taskId: string) => void;
    loading?: boolean;
    selectedTaskId?: string;
    isLoadingTeam?: boolean;
}