export interface Agent {
    input_key: string;
    type: string;
    name: string;
    system_message?: string;
    description?: string;
    icon?: string;
    index_name?: string;
    index_endpoint?: string;  // New: For RAG agents with custom endpoints
    deployment_name?: string;
    id?: string;
    capabilities?: string[];
    role?: string;
    use_rag?: boolean;        // New: Flag for RAG capabilities
    use_mcp?: boolean;        // New: Flag for MCP (Model Context Protocol)
    coding_tools?: boolean;   // New: Flag for coding capabilities
}


export interface StartingTask {
    id: string;
    name: string;
    prompt: string;
    created: string;
    creator: string;
    logo: string;
    /**
     * The declared Lane (issue #16, ADR-013). Deliberately a plain string
     * rather than `Lane`: it arrives from an uploaded team definition, and an
     * unreadable value must fail open to the Deliberate lane in the backend's
     * lane router rather than be assumed valid here.
     */
    lane?: string;
    /**
     * The Rehearsed replies (issue #26) — one-tap answers to the Clarification
     * this task provokes. Only the troubleshooting beat asks a question back,
     * so this is absent on every other task, and its content is unvalidated
     * for the same reason `lane` is.
     */
    rehearsed_replies?: string[];
    /**
     * The Quick Task to offer inside this task's conversation (issue #61,
     * ADR-024). A follow-on is not offered from the home grid.
     */
    follow_on?: string;
}

export interface Team {
    id: string;
    name: string;
    description: string;
    agents: Agent[];
    teamType: 'default' | 'custom';
    logoUrl?: string;
    category?: string;
}

// Backend-compatible Team model that matches uploaded JSON structure
export interface TeamConfig {
    id: string;
    team_id: string;
    name: string;
    description: string;
    status: 'visible' | 'hidden';
    protected?: boolean;
    created: string;
    created_by: string;
    logo: string;
    plan: string;
    agents: Agent[];
    starting_tasks: StartingTask[];
}

export interface TeamUploadResponse {
    success: boolean;
    teamId?: string;
    message?: string;
    errors?: string[];
}
