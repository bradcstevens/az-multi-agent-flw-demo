import {
  PlanWithSteps,
  Step,
  AgentType,
  ProcessedPlanData,
  PlanMessage,
  MPlanData,
  StepStatus
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
    return plan.steps.filter(step => step.agent === agentType);
  }

  /**
   * Get steps that are awaiting human feedback
   * @param plan Plan with steps
   * @returns Array of steps awaiting feedback
   */
  static getStepsAwaitingFeedback(plan: PlanWithSteps): Step[] {
    return plan.steps.filter(step => step.status === StepStatus.AWAITING_FEEDBACK);
  }

  /**
   * Check if plan is complete
   * @param plan Plan with steps
   * @returns Boolean indicating if plan is complete
   */
  static isPlanComplete(plan: PlanWithSteps): boolean {
    return plan.steps.every(step =>
      [StepStatus.COMPLETED, StepStatus.FAILED].includes(step.status)
    );
  }

  /**
   * Get plan completion percentage
   * @param plan Plan with steps
   * @returns Completion percentage (0-100)
   */
  static getPlanCompletionPercentage(plan: PlanWithSteps): number {
    if (!plan.steps.length) return 0;

    const completedSteps = plan.steps.filter(
      step => [StepStatus.COMPLETED, StepStatus.FAILED].includes(step.status)
    ).length;

    return Math.round((completedSteps / plan.steps.length) * 100);
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


  static parsePlanApprovalRequest(rawData: any): MPlanData | null {
    try {
      console.log('🔍 Parsing plan approval request:', rawData, 'Type:', typeof rawData);

      // Already parsed object
      if (rawData && typeof rawData === 'object' && rawData.type === 'parsed_plan_approval_request') {
        return rawData.parsedData || null;
      }

      // v3 backend format with plan property
      if (rawData && typeof rawData === 'object' && rawData.plan) {
        const mplan = rawData.plan;

        // Extract user_request text
        let userRequestText = 'Plan approval required';
        if (mplan.user_request) {
          if (typeof mplan.user_request === 'string') {
            userRequestText = mplan.user_request;
          } else if (Array.isArray(mplan.user_request.items)) {
            const textContent = mplan.user_request.items.find((item: any) => item.text);
            if (textContent?.text) {
              userRequestText = textContent.text.replace(/\u200b/g, '').trim();
            }
          } else if (mplan.user_request.content) {
            userRequestText = mplan.user_request.content;
          }
        }

        // Parse steps with generic cleaning (remove task-specific prefixes)
        const steps = (mplan.steps || []).map((step: any, index: number) => {
          let action = step.action || '';

          // Generic cleanup - remove common prefixes and formatting
          let cleanAction = action
            .replace(/\*\*/g, '') // Remove markdown bold
            .replace(/^Certainly!\s*/i, '') // Remove "Certainly!"
            .replace(/^Given the team composition and the available facts,?\s*/i, '') // Remove team composition prefix
            .replace(/^here is a (?:concise )?plan to address the original request[^.]*\.\s*/i, '') // Remove plan introduction
            .replace(/^(?:here is|this is) a (?:concise )?(?:plan|approach|strategy)[^.]*[.:]\s*/i, '') // Remove other plan intros
            .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ') // Convert **text**: to text:
            .replace(/^[-•]\s*/, '') // Remove bullet points
            .replace(/\s+/g, ' ') // Normalize whitespace
            .trim();

          return {
            id: index + 1,
            action,
            cleanAction,
            agent: step.agent || step._agent || 'System'
          };
        }).filter((step: any) =>
          step.cleanAction.length > 3 && // Filter out very short actions
          !step.cleanAction.match(/^(?:involvement|certainly|given|here is)/i) // Filter out meaningless steps
        );

        return {
          id: mplan.id || mplan.plan_id || 'unknown',
          status: mplan.overall_status || rawData.status || 'PENDING_APPROVAL',
          user_request: userRequestText,
          team: Array.isArray(mplan.team) ? mplan.team : [],
          facts: mplan.facts || '',
          steps,
          context: {
            task: userRequestText,
            participant_descriptions: rawData.context?.participant_descriptions || {}
          },
          // Additional m_plan fields
          user_id: mplan.user_id,
          team_id: mplan.team_id,
          plan_id: mplan.plan_id,
          overall_status: mplan.overall_status,
          raw_data: rawData // Store for debugging
        };
      }

      // Handle string format (generic parsing)
      if (typeof rawData === 'string') {
        // Extract user request from text field
        let user_request = 'Plan approval required';
        const textMatch = rawData.match(/text="([^"]+)"/);
        if (textMatch?.[1]) {
          user_request = textMatch[1].replace(/\\u200b/g, '').trim();
        }

        // Extract basic information
        const id = rawData.match(/id='([^']+)'/)?.[1] || 'unknown';
        const status = rawData.match(/overall_status=<PlanStatus\.([^>]+)>/)?.[1] || 'PENDING_APPROVAL';
        const team = rawData.match(/team=\[([^\]]*)\]/)?.[1]
          ?.split(',')
          .map(member => member.trim().replace(/['"]/g, ''))
          .filter(member => member.length > 0) || [];

        // Extract facts
        const factsMatch = rawData.match(/facts="([^"]*(?:\\.[^"]*)*)"/);
        const facts = factsMatch?.[1]?.replace(/\\n/g, '\n').replace(/\\"/g, '"') || '';

        // Extract steps with generic parsing
        const stepMatches = rawData.match(/MStep\([^)]*action="([^"]+)"/g);
        const steps = [];

        if (stepMatches) {
          const uniqueActions = new Set();
          let stepIndex = 1;

          for (const stepStr of stepMatches) {
            const actionMatch = stepStr.match(/action="([^"]+)"/);
            if (actionMatch?.[1]) {
              let action = actionMatch[1];

              // Generic action cleaning
              let cleanAction = action
                .replace(/^Certainly!\s*/i, '') // Remove "Certainly!"
                .replace(/^Given the team composition and the available facts,?\s*/i, '') // Remove team prefix
                .replace(/^here is a (?:concise )?plan to[^.]*\.\s*/i, '') // Remove plan introduction
                .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ') // Convert **text**: to text:
                .replace(/^[-•]\s*/, '') // Remove bullet points
                .replace(/\s+/g, ' ') // Normalize whitespace
                .trim();

              // Generic filtering - avoid very short, duplicate, or meaningless steps
              if (cleanAction.length > 5 &&
                !uniqueActions.has(cleanAction.toLowerCase()) &&
                !cleanAction.match(/^(?:here is|this is a|given|certainly|involvement)/i)) {

                uniqueActions.add(cleanAction.toLowerCase());
                steps.push({
                  id: stepIndex++,
                  action,
                  cleanAction,
                  agent: 'System'
                });
              }
            }
          }
        }

        return {
          id,
          status,
          user_request,
          team,
          facts,
          steps,
          context: {
            task: user_request,
            participant_descriptions: {}
          },
          raw_data: rawData
        };
      }

      return null;
    } catch (error) {
      console.error('Error parsing plan approval request:', error);
      return null;
    }
  }
}