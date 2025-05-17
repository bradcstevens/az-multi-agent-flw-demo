import { Plan, PlanWithSteps, Step } from '../models';

// Base API URL - update this to point to your backend API
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api';

/**
 * Service for interacting with Plans and Steps
 */
export const PlanService = {
    /**
     * Get a plan by ID
     * @param sessionId Session identifier
     * @param planId Plan identifier
     * @returns Promise with the plan
     */
    async getPlan(sessionId: string, planId: string): Promise<Plan> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans/${planId}`);
        if (!response.ok) {
            throw new Error(`Failed to get plan: ${response.statusText}`);
        }
        return await response.json() as Plan;
    },

    /**
     * Get a plan with its steps
     * @param sessionId Session identifier
     * @param planId Plan identifier
     * @returns Promise with the plan and its steps
     */
    async getPlanWithSteps(sessionId: string, planId: string): Promise<PlanWithSteps> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans/${planId}/with-steps`);
        if (!response.ok) {
            throw new Error(`Failed to get plan with steps: ${response.statusText}`);
        }
        return await response.json() as PlanWithSteps;
    },

    /**
     * Get all plans for a session
     * @param sessionId Session identifier
     * @returns Promise with an array of plans
     */
    async getPlans(sessionId: string): Promise<Plan[]> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans`);
        if (!response.ok) {
            throw new Error(`Failed to get plans: ${response.statusText}`);
        }
        return await response.json() as Plan[];
    },

    /**
     * Create a new plan
     * @param plan Plan to create
     * @returns Promise with the created plan
     */
    async createPlan(plan: Omit<Plan, 'id' | 'timestamp'>): Promise<Plan> {
        const response = await fetch(`${API_BASE_URL}/sessions/${plan.session_id}/plans`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(plan),
        });
        if (!response.ok) {
            throw new Error(`Failed to create plan: ${response.statusText}`);
        }
        return await response.json() as Plan;
    },

    /**
     * Get a step by ID
     * @param sessionId Session identifier
     * @param planId Plan identifier
     * @param stepId Step identifier
     * @returns Promise with the step
     */
    async getStep(sessionId: string, planId: string, stepId: string): Promise<Step> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans/${planId}/steps/${stepId}`);
        if (!response.ok) {
            throw new Error(`Failed to get step: ${response.statusText}`);
        }
        return await response.json() as Step;
    },

    /**
     * Get all steps for a plan
     * @param sessionId Session identifier
     * @param planId Plan identifier
     * @returns Promise with an array of steps
     */
    async getSteps(sessionId: string, planId: string): Promise<Step[]> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans/${planId}/steps`);
        if (!response.ok) {
            throw new Error(`Failed to get steps: ${response.statusText}`);
        }
        return await response.json() as Step[];
    },

    /**
     * Update step status and provide feedback
     * @param sessionId Session identifier
     * @param planId Plan identifier
     * @param stepId Step identifier
     * @param update Update data
     * @returns Promise with the updated step
     */
    async updateStep(
        sessionId: string,
        planId: string,
        stepId: string,
        update: {
            status?: StepStatus,
            human_feedback?: string,
            updated_action?: string,
        }
    ): Promise<Step> {
        const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/plans/${planId}/steps/${stepId}`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(update),
        });
        if (!response.ok) {
            throw new Error(`Failed to update step: ${response.statusText}`);
        }
        return await response.json() as Step;
    }
};

export default PlanService;
