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

  static parsePlanApprovalRequest(rawData: any): ParsedPlanData | null {
    try {
      console.log('🔍 Parsing plan approval request:', rawData, 'Type:', typeof rawData);
      
      // Check if this is already a parsed plan approval request object
      if (rawData && typeof rawData === 'object' && rawData.type === 'parsed_plan_approval_request') {
        console.log('✅ Data is already parsed, returning parsedData directly');
        return rawData.parsedData || null;
      }
      
      // Handle v3 backend format where rawData has a plan property
      if (rawData && typeof rawData === 'object' && rawData.plan) {
        console.log('📝 Processing v3 format with MPlan object:', rawData.plan);
        const mplan = rawData.plan;

        // Extract user_request from ChatMessageContent or string
        let userRequestText = 'Plan approval required';
        if (mplan.user_request) {
          if (typeof mplan.user_request === 'string') {
            userRequestText = mplan.user_request;
          } else if (mplan.user_request.items && Array.isArray(mplan.user_request.items)) {
            // Handle ChatMessageContent format
            const textContent = mplan.user_request.items.find((item: any) => item.text);
            if (textContent && textContent.text) {
              userRequestText = textContent.text.replace(/\u200b/g, '').trim();
            }
          } else if (mplan.user_request.content) {
            userRequestText = mplan.user_request.content;
          }
        }

        return {
          id: mplan.id || mplan.plan_id || 'unknown',
          status: rawData.status || 'PENDING_APPROVAL',
          user_request: userRequestText,
          team: Array.isArray(mplan.team) ? mplan.team : [],
          facts: mplan.facts || '',
          steps: (mplan.steps || []).map((step: any, index: number) => ({
            id: index + 1,
            action: step.action || '',
            cleanAction: (step.action || '').replace(/\*\*/g, '').trim(),
            agent: step.agent || step._agent || 'System'
          })),
          context: {
            task: userRequestText,
            participant_descriptions: rawData.context?.participant_descriptions || {}
          }
        };
      }

      // Fallback for legacy string format parsing
      if (typeof rawData === 'string') {
        console.log('📝 Processing legacy string format');
        // Extract basic plan information
        const idMatch = rawData.match(/id='([^']+)'/);
        const statusMatch = rawData.match(/status=<PlanStatus\.([^>]+)>/);
        const userRequestMatch = rawData.match(/user_request='([^']+)'/);
        const teamMatch = rawData.match(/team=\[([^\]]*)\]/);
        const factsMatch = rawData.match(/facts='([^']*(?:'[^']*)*?)'/);

        const id = idMatch?.[1] || 'unknown';
        const status = statusMatch?.[1] || 'PENDING_APPROVAL';
        const user_request = userRequestMatch?.[1]?.replace(/\\u200b/g, '') || 'Plan approval required';
        
        // Parse team members
        let team: string[] = [];
        if (teamMatch?.[1]) {
          team = teamMatch[1]
            .split(',')
            .map(member => member.trim().replace(/['"]/g, ''))
            .filter(member => member.length > 0);
        }

        const facts = factsMatch?.[1]?.replace(/\\u200b/g, '') || '';

        // Parse steps - handle the complex nested string format
        let steps: Array<{ id: number; action: string; cleanAction: string; agent?: string }> = [];
        
        // First try to match the array of MStep objects
        const stepsMatch = rawData.match(/steps=\[(.*?)\](?=\))/s);
        if (stepsMatch?.[1]) {
          const stepContent = stepsMatch[1];
          
          // Match individual MStep objects
          const stepMatches = stepContent.match(/MStep\(action='([^']*(?:''[^']*)*)'\)/g);
          if (stepMatches) {
            steps = stepMatches.map((stepStr, index) => {
              const actionMatch = stepStr.match(/action='([^']*(?:''[^']*)*)'/);
              let action = actionMatch?.[1]?.replace(/''/g, "'") || '';
              
              // Clean up the action text
              const cleanAction = action
                .replace(/\*\*/g, '')
                .replace(/^\s*[-•]\s*/, '')
                .trim();
              
              // Skip empty, duplicate, or meaningless steps
              if (!cleanAction || 
                  cleanAction === 'Involvement' || 
                  cleanAction.length < 10 ||
                  cleanAction.includes('Here is a short bullet-point plan')) {
                return null;
              }
              
              return {
                id: index + 1,
                action,
                cleanAction,
                agent: 'System' // Default agent since not specified in string format
              };
            }).filter(step => step !== null) as Array<{ id: number; action: string; cleanAction: string; agent: string }>;
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
      }

      // If rawData is neither a parsed object, v3 object, nor a legacy string, return null
      console.warn('❌ Unrecognized plan approval request format:', typeof rawData, rawData);
      return null;

    } catch (error) {
      console.error('❌ Error parsing plan approval request:', error);
      return null;
    }
  }
}