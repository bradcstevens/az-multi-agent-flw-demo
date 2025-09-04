import {
  PlanWithSteps,
  Step,
  AgentType,
  ProcessedPlanData,
  PlanMessage,
  ParsedPlanData
} from "@/models";
import { apiService } from "@/api";

/**
 * Service for processing and managing plan data operations
 */
export class PlanDataService {
  /**
   * Fetch plan details by plan ID and process the data
   * @param planId Plan ID to fetch
   * @returns Promise with processed plan data
   */
  static async fetchPlanData(
    planId: string,
    useCache: boolean
  ): Promise<ProcessedPlanData> {
    try {
      // Use optimized getPlanById method for better performance
      const planBody = await apiService.getPlanById(planId, useCache);
      return this.processPlanData(
        planBody.plan_with_steps,
        planBody.messages || []
      );
    } catch (error) {
      console.log("Failed to fetch plan data:", error);
      throw error;
    }
  }

  /**
   * Process plan data to extract agents, steps, and clarification status
   * @param plan PlanWithSteps object to process
   * @returns Processed plan data
   */
  static processPlanData(
    plan: PlanWithSteps,
    messages: PlanMessage[]
  ): ProcessedPlanData {
    // Extract unique agents from steps
    console.log("Processing plan data for plan ID:", plan);
    const uniqueAgents = new Set<AgentType>();
    if (plan.steps && plan.steps.length > 0) {
      plan.steps.forEach((step) => {
        if (step.agent) {
          uniqueAgents.add(step.agent);
        }
      });
    }


    // Convert Set to Array for easier handling
    const agents = Array.from(uniqueAgents);

    // Get all steps
    const steps = plan.steps ?? [];

    // Check if human_clarification_request is not null
    const hasClarificationRequest =
      plan.human_clarification_request != null &&
      plan.human_clarification_request.trim().length > 0;
    const hasClarificationResponse =
      plan.human_clarification_response != null &&
      plan.human_clarification_response.trim().length > 0;
    const enableChat = hasClarificationRequest && !hasClarificationResponse;
    const enableStepButtons =
      (hasClarificationRequest && hasClarificationResponse) ||
      (!hasClarificationRequest && !hasClarificationResponse);
    return {
      plan,
      agents,
      steps,
      hasClarificationRequest,
      hasClarificationResponse,
      enableChat,
      enableStepButtons,
      messages,
    };
  }

  /**
   * Get steps for a specific agent type
   * @param plan Plan with steps
   * @param agentType Agent type to filter by
   * @returns Array of steps for the specified agent
   */
  static getStepsForAgent(plan: PlanWithSteps, agentType: AgentType): Step[] {
    return apiService.getStepsForAgent(plan, agentType);
  }

  /**
   * Get steps that are awaiting human feedback
   * @param plan Plan with steps
   * @returns Array of steps awaiting feedback
   */
  static getStepsAwaitingFeedback(plan: PlanWithSteps): Step[] {
    return apiService.getStepsAwaitingFeedback(plan);
  }

  /**
   * Check if plan is complete
   * @param plan Plan with steps
   * @returns Boolean indicating if plan is complete
   */
  static isPlanComplete(plan: PlanWithSteps): boolean {
    return apiService.isPlanComplete(plan);
  }

  /**
   * Get plan completion percentage
   * @param plan Plan with steps
   * @returns Completion percentage (0-100)
   */
  static getPlanCompletionPercentage(plan: PlanWithSteps): number {
    return apiService.getPlanCompletionPercentage(plan);
  }

  /**
   * Approve a plan step
   * @param step Step to approve
   * @returns Promise with API response
   */
  static async stepStatus(
    step: Step,
    action: boolean
  ): Promise<{ status: string }> {
    try {
      return apiService.stepStatus(
        step.plan_id,
        step.session_id,
        action, // approved
        step.id
      );
    } catch (error) {
      console.log("Failed to change step status:", error);
      throw error;
    }
  }

  /**
   * Submit human clarification for a plan
   * @param planId Plan ID
   * @param sessionId Session ID
   * @param clarification Clarification text
   * @returns Promise with API response
   */
  static async submitClarification(
    planId: string,
    sessionId: string,
    clarification: string
  ) {
    try {
      return apiService.submitClarification(planId, sessionId, clarification);
    } catch (error) {
      console.log("Failed to submit clarification:", error);
      throw error;
    }
  }

 static parsePlanApprovalRequest(rawData: string): ParsedPlanData | null {
  try {
    // Extract plan ID
    const idMatch = rawData.match(/id='([^']+)'/);
    const id = idMatch ? idMatch[1] : '';

    // Extract status
    const statusMatch = rawData.match(/status='([^']+)'/);
    const status = statusMatch ? statusMatch[1] : 'PENDING_APPROVAL';

    // Extract user request text
    const userRequestMatch = rawData.match(/text='([^']+)'/);
    const user_request = userRequestMatch ? userRequestMatch[1].replace(/\\u200b/g, '') : '';

    // Extract team members
    const teamMatch = rawData.match(/team=\[([^\]]+)\]/);
    let team: string[] = [];
    if (teamMatch) {
      team = teamMatch[1].split("'").filter((item, index) => index % 2 === 1);
    }

    // Extract facts
    const factsMatch = rawData.match(/facts="([^"]*(?:"[^"]*"[^"]*)*?)"/);
    const facts = factsMatch ? factsMatch[1].replace(/\\n/g, '\n') : '';

    // Extract steps
    const stepsMatch = rawData.match(/steps=\[([^\]]+MStep[^\]]*)\]/);
    let steps: Array<{ id: number; action: string; cleanAction: string }> = [];
    
    if (stepsMatch) {
      const stepMatches = stepsMatch[1].match(/MStep\(action='([^']+)'\)/g);
      if (stepMatches) {
        steps = stepMatches.map((stepMatch, index) => {
          const actionMatch = stepMatch.match(/action='([^']+)'/);
          const action = actionMatch ? actionMatch[1] : '';
          
          // Clean up the action text
          let cleanAction = action
            .replace(/^Involvement\s*/, '') // Remove "Involvement" prefix
            .replace(/^\*\*(.*?)\*\*:?$/, '$1') // Remove markdown bold formatting
            .trim();
          
          // Skip empty or duplicate "Involvement" steps
          if (!cleanAction || cleanAction === 'Involvement') {
            return null;
          }
          
          return {
            id: index + 1,
            action,
            cleanAction
          };
        }).filter(step => step !== null) as Array<{ id: number; action: string; cleanAction: string }>;
      }
    }

    // Extract context
    const contextMatch = rawData.match(/context=\{([^}]+)\}/);
    let context = { task: '', participant_descriptions: {} };
    
    if (contextMatch) {
      const taskMatch = rawData.match(/'task':\s*'([^']+)'/);
      if (taskMatch) {
        context.task = taskMatch[1].replace(/\\u200b/g, '');
      }
      
      // Extract participant descriptions
      const participantMatch = rawData.match(/'participant_descriptions':\s*\{([^}]+)\}/);
      if (participantMatch) {
        const descriptions: Record<string, string> = {};
        const descMatches = participantMatch[1].match(/'([^']+)':\s*'([^']*)'/g);
        if (descMatches) {
          descMatches.forEach(match => {
            const keyValueMatch = match.match(/'([^']+)':\s*'([^']*)'/);
            if (keyValueMatch) {
              descriptions[keyValueMatch[1]] = keyValueMatch[2];
            }
          });
        }
        context.participant_descriptions = descriptions;
      }
    }

    return {
      id,
      status,
      user_request,
      team: team.filter(member => member && member.trim()),
      facts,
      steps: steps.filter(step => step.cleanAction.length > 0),
      context
    };

  } catch (error) {
    console.error('Error parsing plan approval request:', error);
    return null;
  }
}


  
}
