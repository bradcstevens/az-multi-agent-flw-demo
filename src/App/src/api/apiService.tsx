import { apiClient } from './apiClient';
import {
    AgentMessage,
    HumanClarification,
    InputTask,
    InputTaskResponse,
    Plan,
    PlanApprovalRequest,
    PlanApprovalResponse,
    AgentMessageBE,
    MPlanBE,
    TeamConfigurationBE,
    PlanFromAPI,
    AgentMessageResponse
} from '../models';
import { SessionState } from '../models/sessionState';
import { ChatDeletionResponse, ChatsDeletionResponse } from '../models/chatDeletion';

export interface ChatTurnEndResponse {
    status: 'ended' | 'already_settled';
    session_id: string;
    cancelled: boolean;
}

// Constants for endpoints
const API_ENDPOINTS = {
    PROCESS_REQUEST: '/v4/process_request',
    PLANS: '/v4/plans',
    PLAN: '/v4/plan',
    // Chat deletion is session-scoped (ADR-026): the path carries a
    // `session_id`, never the plan id a row opens with.
    CHATS: '/v4/chats',
    PLAN_APPROVAL: '/v4/plan_approval',
    HUMAN_CLARIFICATION: '/v4/user_clarification',
    USER_BROWSER_LANGUAGE: '/user_browser_language',
    AGENT_MESSAGE: '/v4/agent_message',
    SESSION_STATE: '/v4/session_state',
};

// Simple cache implementation
interface CacheEntry<T> {
    data: T;
    timestamp: number;
    ttl: number; // Time to live in ms
}

class APICache {
    private cache: Map<string, CacheEntry<any>> = new Map();

    set<T>(key: string, data: T, ttl = 60000): void { // Default TTL: 1 minute
        this.cache.set(key, {
            data,
            timestamp: Date.now(),
            ttl
        });
    }

    get<T>(key: string): T | null {
        const entry = this.cache.get(key);
        if (!entry) return null;

        // Check if entry is expired
        if (Date.now() - entry.timestamp > entry.ttl) {
            this.cache.delete(key);
            return null;
        }

        return entry.data;
    }

    clear(): void {
        this.cache.clear();
    }

    invalidate(pattern: RegExp): void {
        for (const key of this.cache.keys()) {
            if (pattern.test(key)) {
                this.cache.delete(key);
            }
        }
    }
}

// Request tracking to prevent duplicate requests
class RequestTracker {
    private pendingRequests: Map<string, Promise<any>> = new Map();

    async trackRequest<T>(key: string, requestFn: () => Promise<T>): Promise<T> {
        // If request is already pending, return the existing promise
        if (this.pendingRequests.has(key)) {
            return this.pendingRequests.get(key)!;
        }

        // Create new request
        const requestPromise = requestFn();

        // Track the request
        this.pendingRequests.set(key, requestPromise);

        try {
            const result = await requestPromise;
            return result;
        } finally {
            // Remove from tracking when done (success or failure)
            this.pendingRequests.delete(key);
        }
    }
}



export class APIService {
    private _cache = new APICache();
    private _requestTracker = new RequestTracker();


    /**
     * Create a new plan with RAI validation
     * @param inputTask The task description and optional session ID
     * @returns Promise with the response containing plan ID and status
     */
    // async createPlan(inputTask: InputTask): Promise<{ plan_id: string; status: string; session_id: string }> {
    //     return apiClient.post(API_ENDPOINTS.PROCESS_REQUEST, inputTask);
    // }

    async createPlan(inputTask: InputTask): Promise<InputTaskResponse> {
        return apiClient.post(API_ENDPOINTS.PROCESS_REQUEST, inputTask);
    }

    /**
     * Get all plans, optionally filtered by session ID
     * @param sessionId Optional session ID to filter plans
     * @param useCache Whether to use cached data or force fresh fetch
     * @returns Promise with array of plans with their steps
     */
    async getPlans(sessionId?: string, useCache = true): Promise<Plan[]> {
        const cacheKey = `plans_${sessionId || 'all'}`;
        const params = sessionId ? { session_id: sessionId } : {};
        const fetcher = async () => {
            const data = await apiClient.get(API_ENDPOINTS.PLANS, { params });
            if (useCache) {
                this._cache.set(cacheKey, data, 30000); // Cache for 30 seconds
            }
            return data;
        };

        if (useCache) {
            return this._requestTracker.trackRequest(cacheKey, fetcher);
        }

        return fetcher();
    }

    /**
     * Get a single plan by plan ID
     * @param planId Plan ID to fetch
     * @param useCache Whether to use cached data or force fresh fetch
     * @returns Promise with the plan and its steps
     */
    async getPlanById(planId: string, useCache = true): Promise<PlanFromAPI> {
        const cacheKey = `plan_by_id_${planId}`;
        const params = { plan_id: planId };

        const fetcher = async () => {
            const data = await apiClient.get(API_ENDPOINTS.PLAN, { params });

            // The API returns an array, but with plan_id filter it should have only one item
            if (!data) {
                throw new Error(`Plan with ID ${planId} not found`);
            }
            const results = {
                plan: data.plan as Plan,
                messages: data.messages as AgentMessageBE[],
                m_plan: data.m_plan as MPlanBE | null,
                team: data.team as TeamConfigurationBE | null,
                streaming_message: data.streaming_message as string | null
            } as PlanFromAPI;
            if (useCache) {
                this._cache.set(cacheKey, results, 30000); // Cache for 30 seconds
            }
            return results;
        };

        if (useCache) {
            const cachedPlan = this._cache.get<PlanFromAPI>(cacheKey);
            if (cachedPlan) return cachedPlan;

            return this._requestTracker.trackRequest(cacheKey, fetcher);
        }

        return fetcher();
    }

    /**
     * **Chat deletion** — the whole Chat, by its session (#75, ADR-026).
     *
     * Deletes every document in that Chat's session partition: its plans,
     * their steps, the transcript, `m_plan`, the **Troubleshooting record**,
     * the **Simulated ticket** and the **Session state**. The route scopes it
     * to the associate's own `user_id` and refuses while the Chat is running,
     * so a rejection here means the conversation is still in Cosmos and the
     * surface must go on saying so.
     *
     * The plans cache is invalidated rather than trimmed: the panel re-reads
     * the history, and a cached list is the one way a deleted row comes back.
     *
     * @param sessionId The Chat's `session_id` — never the plan id a row opens.
     */
    async deleteChat(sessionId: string): Promise<ChatDeletionResponse> {
        const deleted = await apiClient.delete<ChatDeletionResponse>(
            `${API_ENDPOINTS.CHATS}/${encodeURIComponent(sessionId)}`
        );
        this._cache.invalidate(new RegExp(`^plans_`));
        return deleted;
    }

    /**
     * **Delete every Chat** of the associate's own (#76, ADR-026).
     *
     * Each chat is swept on the single delete's own terms — a running one is
     * kept rather than taken, and the whole operation is not refused because
     * of it. The route always answers 200 and puts what actually happened in
     * the body, so this method returns that shape rather than throwing on a
     * partial result: the panel is what decides whether "kept" or "failed"
     * changes what it shows.
     *
     * The plans cache is invalidated for the same reason the single delete
     * invalidates it: a cached list is the one way a deleted row comes back.
     */
    async deleteAllChats(): Promise<ChatsDeletionResponse> {
        const deleted = await apiClient.delete<ChatsDeletionResponse>(
            API_ENDPOINTS.CHATS
        );
        this._cache.invalidate(new RegExp(`^plans_`));
        return deleted;
    }

    /**
     * **Ending a turn** — settle this Chat's in-flight turn by session
     * (ADR-031). Leaving a Chat is not a plan verdict, so this is deliberately
     * separate from plan approval.
     */
    async endChatTurn(sessionId: string): Promise<ChatTurnEndResponse> {
        const ended = await apiClient.post<ChatTurnEndResponse>(
            `${API_ENDPOINTS.CHATS}/${encodeURIComponent(sessionId)}/end_turn`,
        );
        this._cache.invalidate(new RegExp(`^plans_`));
        return ended;
    }

    /**
     * Read a session's server-side state (issue #20).
     *
     * Deliberately uncached: this is what a page reloaded mid-conversation
     * reads to recover state the browser threw away, so a copy cached from
     * before the reload would defeat the point.
     *
     * @param sessionId Session ID
     * @returns Promise with the session's state
     */
    async getSessionState(sessionId: string): Promise<SessionState> {
        return apiClient.get(
            `${API_ENDPOINTS.SESSION_STATE}/${encodeURIComponent(sessionId)}`
        );
    }

    /** Read the submitted Simulated ticket for an already-open Chat, if it has one. */
    async getChatTicket(sessionId: string): Promise<unknown> {
        return apiClient.get(
            `${API_ENDPOINTS.CHATS}/${encodeURIComponent(sessionId)}/ticket`
        );
    }

    /**
     * The Mocked sign-in (issue #27) — the whole of the identity provider.
     *
     * **It sends no name.** The route takes none: the associate is authored in
     * the backend's `associate/records.py` and comes back on the response, so
     * the name the header shows and the name the **Associate record** is keyed
     * by cannot drift apart. A name supplied from here would be a header
     * confidently claiming somebody the Identity boundary gate will not answer
     * for.
     *
     * No real identity provider is involved anywhere in this flow — not here,
     * not behind the route. That is the point of the beat.
     *
     * @param sessionId The session to write the identity into.
     * @returns Promise with the session's state, identity included
     */
    async signIn(sessionId: string): Promise<SessionState> {
        return apiClient.post(
            `${API_ENDPOINTS.SESSION_STATE}/${encodeURIComponent(sessionId)}/sign_in`,
            {}
        );
    }


    /**
   * Approve a plan for execution 
   * @param planApprovalData Plan approval data
   * @returns Promise with approval response
   */
    async approvePlan(planApprovalData: PlanApprovalRequest): Promise<PlanApprovalResponse> {
        const requestKey = `approve-plan-${planApprovalData.m_plan_id}`;

        return this._requestTracker.trackRequest(requestKey, async () => {
            const response = await apiClient.post(API_ENDPOINTS.PLAN_APPROVAL, planApprovalData);

            // Invalidate cache since plan execution will start
            this._cache.invalidate(new RegExp(`^plans_`));
            if (planApprovalData.plan_id) {
                this._cache.invalidate(new RegExp(`^plan.*_${planApprovalData.plan_id}`));
            }

            return response;
        });
    }


    /**
     * Submit clarification for a plan
     * @param planId Plan ID
     * @param sessionId Session ID
     * @param clarification Clarification text
     * @returns Promise with response object
     */
    async submitClarification(
        request_id: string = "",
        answer: string = "",
        plan_id: string = "",
        m_plan_id: string = ""
    ): Promise<{ status: string; session_id: string }> {
        const clarificationData: HumanClarification = {
            request_id,
            answer,
            plan_id,
            m_plan_id
        };

        const response = await apiClient.post(
            API_ENDPOINTS.HUMAN_CLARIFICATION,
            clarificationData
        );

        // Invalidate cached data
        this._cache.invalidate(new RegExp(`^(plan|steps)_${plan_id}`));
        this._cache.invalidate(new RegExp(`^plans_`));

        return response;
    }


    /**
     * Clear all cached data
     */
    clearCache(): void {
        this._cache.clear();
    }



    /**
     * Send the user's browser language to the backend
     * @returns Promise with response object
     */
    async sendUserBrowserLanguage(): Promise<{ status: string }> {
        const language = navigator.language || navigator.languages[0] || 'en';
        const response = await apiClient.post(API_ENDPOINTS.USER_BROWSER_LANGUAGE, {
            language
        });
        return response;
    }
    async sendAgentMessage(data: AgentMessageResponse): Promise<AgentMessage> {
        const result = await apiClient.post(API_ENDPOINTS.AGENT_MESSAGE, data);
        return result;
    }
}

// Export a singleton instance
export const apiService = new APIService();
