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

      // Already parsed object passthrough
      if (rawData && typeof rawData === 'object' && rawData.type === 'parsed_plan_approval_request') {
        return rawData.parsedData || null;
      }

      // Wrapper form: { type: 'plan_approval_request', data: 'PlanApprovalRequest(plan=MPlan(...), ...)' }
      if (
        rawData &&
        typeof rawData === 'object' &&
        rawData.type === 'plan_approval_request' &&
        typeof rawData.data === 'string'
      ) {
        // Recurse using the contained string
        return this.parsePlanApprovalRequest(rawData.data);
      }

      // Structured v3 style: { plan: { id, steps, user_request, ... }, context?: {...} }
      if (rawData && typeof rawData === 'object' && rawData.plan && typeof rawData.plan === 'object') {
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

        const steps = (mplan.steps || [])
          .map((step: any, index: number) => {
            const action = step.action || '';
            const cleanAction = action
              .replace(/\*\*/g, '')
              .replace(/^Certainly!\s*/i, '')
              .replace(/^Given the team composition and the available facts,?\s*/i, '')
              .replace(/^here is a (?:concise )?plan to address the original request[^.]*\.\s*/i, '')
              .replace(/^(?:here is|this is) a (?:concise )?(?:plan|approach|strategy)[^.]*[.:]\s*/i, '')
              .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ')
              .replace(/^[-•]\s*/, '')
              .replace(/\s+/g, ' ')
              .trim();

            return {
              id: index + 1,
              action,
              cleanAction,
              agent: step.agent || step._agent || 'System'
            };
          })
          .filter((s: any) =>
            s.cleanAction.length > 3 &&
            !/^(?:involvement|certainly|given|here is)/i.test(s.cleanAction)
          );

        return {
          id: mplan.id || mplan.plan_id || 'unknown',
          status: (mplan.overall_status || rawData.status || 'PENDING_APPROVAL'),
          user_request: userRequestText,
          team: Array.isArray(mplan.team) ? mplan.team : [],
          facts: mplan.facts || '',
          steps,
          context: {
            task: userRequestText,
            participant_descriptions: rawData.context?.participant_descriptions || {}
          },
          user_id: mplan.user_id,
          team_id: mplan.team_id,
          plan_id: mplan.plan_id,
          overall_status: mplan.overall_status,
          raw_data: rawData
        };
      }

      // String representation parsing (PlanApprovalRequest(...MPlan(...)) or raw repr)
      if (typeof rawData === 'string') {
        const source = rawData;

        // Extract MPlan(...) block (optional)
        // Not strictly needed but could be used for scoping later.
        // const mplanBlock = source.match(/MPlan\(([\s\S]*?)\)\)/);

        // User request (first text='...')
        let user_request =
          source.match(/text=['"]([^'"]+?)['"]/)
            ?.[1]
            ?.replace(/\\u200b/g, '')
            .trim() || 'Plan approval required';

        const id = source.match(/MPlan\(id=['"]([^'"]+)['"]/)?.[1] ||
          source.match(/id=['"]([^'"]+)['"]/)?.[1] ||
          'unknown';

        let status =
          source.match(/overall_status=<PlanStatus\.([a-zA-Z_]+):/)?.[1] ||
          source.match(/overall_status=['"]([^'"]+)['"]/)?.[1] ||
          'PENDING_APPROVAL';
        if (status) {
          status = status.toUpperCase();
        }

        const teamRaw =
          source.match(/team=\[([^\]]*)\]/)?.[1] || '';
        const team = teamRaw
          .split(',')
          .map(s => s.trim().replace(/['"]/g, ''))
          .filter(Boolean);

        const facts =
          source
            .match(/facts="([^"]*(?:\\.[^"]*)*)"/)?.[1]
            ?.replace(/\\n/g, '\n')
            .replace(/\\"/g, '"') || '';

        // Steps: accept single or double quotes: action='...' or action="..."
        const stepRegex = /MStep\(([^)]*?)\)/g;
        const steps: any[] = [];
        const uniqueActions = new Set<string>();
        let match: RegExpExecArray | null;
        let stepIndex = 1;

        while ((match = stepRegex.exec(source)) !== null) {
          const chunk = match[1];
          const agent =
            chunk.match(/agent=['"]([^'"]+)['"]/)?.[1] || 'System';
          const actionRaw =
            chunk.match(/action=['"]([^'"]+)['"]/)?.[1] || '';

          if (!actionRaw) continue;

          let cleanAction = actionRaw
            .replace(/\*\*/g, '')
            .replace(/^Certainly!\s*/i, '')
            .replace(/^Given the team composition and the available facts,?\s*/i, '')
            .replace(/^here is a (?:concise )?plan to[^.]*\.\s*/i, '')
            .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ')
            .replace(/^[-•]\s*/, '')
            .replace(/\s+/g, ' ')
            .trim();

          if (
            cleanAction.length > 3 &&
            !uniqueActions.has(cleanAction.toLowerCase()) &&
            !/^(?:here is|this is|given|certainly|involvement)$/i.test(cleanAction)
          ) {
            uniqueActions.add(cleanAction.toLowerCase());
            steps.push({
              id: stepIndex++,
              action: actionRaw,
              cleanAction,
              agent
            });
          }
        }

        // participant_descriptions (best-effort)
        let participant_descriptions: Record<string, string> = {};
        const pdMatch =
          source.match(/participant_descriptions['"]?\s*:\s*({[^}]*})/) ||
          source.match(/'participant_descriptions':\s*({[^}]*})/);

        if (pdMatch?.[1]) {
          const transformed = pdMatch[1]
            .replace(/'/g, '"')
            .replace(/([a-zA-Z0-9_]+)\s*:/g, '"$1":');
          try {
            participant_descriptions = JSON.parse(transformed);
          } catch {
            participant_descriptions = {};
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
            participant_descriptions
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
  // ...existing code...

  /**
   * Parse an agent message object or repr string:
   * Input forms supported:
   *  - { type: 'agent_message', data: "AgentMessage(agent_name='X', timestamp=..., content='...')"}
   *  - "AgentMessage(agent_name='X', timestamp=..., content='...')"
   * Returns a structured object with steps parsed from markdown-ish content.
   */
  static parseAgentMessage(rawData: any): {
    agent: string;
    timestamp: number | null;
    steps: Array<{
      title: string;
      fields: Record<string, string>;
      summary?: string;
      raw_block: string;
    }>;
    next_steps: string[];
    raw_content: string;
    raw_data: any;
  } | null {
    try {
      // Unwrap wrapper
      if (rawData && typeof rawData === 'object' && rawData.type === 'agent_message' && typeof rawData.data === 'string') {
        return this.parseAgentMessage(rawData.data);
      }

      if (typeof rawData !== 'string') return null;
      if (!rawData.startsWith('AgentMessage(')) return null;

      const source = rawData;

      const agent =
        source.match(/agent_name='([^']+)'/)?.[1] ||
        source.match(/agent_name="([^"]+)"/)?.[1] ||
        'UnknownAgent';

      const timestampStr =
        source.match(/timestamp=([\d.]+)/)?.[1];
      const timestamp = timestampStr ? Number(timestampStr) : null;

      // Extract content='...'
      const contentMatch = source.match(/content='((?:\\'|[^'])*)'/);
      let raw_content = contentMatch ? contentMatch[1] : '';
      // Unescape
      raw_content = raw_content
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\');

      // Parse sections of the form "##### Title Completed"
      // Each block ends at --- line or next "##### " or end.
      const lines = raw_content.split('\n');
      const steps: Array<{ title: string; fields: Record<string, string>; summary?: string; raw_block: string; }> = [];
      let i = 0;
      while (i < lines.length) {
        const headingMatch = lines[i].match(/^#####\s+(.+?)\s+Completed\s*$/i);
        if (headingMatch) {
          const title = headingMatch[1].trim();
          const blockLines: string[] = [];
          i++;
          while (i < lines.length && !/^---\s*$/.test(lines[i]) && !/^#####\s+/.test(lines[i])) {
            blockLines.push(lines[i]);
            i++;
          }
          // Skip separator line if present
          if (i < lines.length && /^---\s*$/.test(lines[i])) i++;

          const fields: Record<string, string> = {};
          let summary: string | undefined;
          for (const bl of blockLines) {
            const fieldMatch = bl.match(/^\*\*(.+?)\*\*:\s*(.*)$/);
            if (fieldMatch) {
              const fieldName = fieldMatch[1].trim().replace(/:$/, '');
              const value = fieldMatch[2].trim().replace(/\\s+$/, '');
              if (fieldName) fields[fieldName] = value;
            } else {
              const summaryMatch = bl.match(/^AGENT SUMMARY:\s*(.+)$/i);
              if (summaryMatch) {
                summary = summaryMatch[1].trim();
              }
            }
          }

          steps.push({
            title,
            fields,
            summary,
            raw_block: blockLines.join('\n').trim()
          });
        } else {
          i++;
        }
      }

      // Next Steps section
      const nextSteps: string[] = [];
      const nextIdx = lines.findIndex(l => /^Next Steps:/.test(l.trim()));
      if (nextIdx !== -1) {
        for (let j = nextIdx + 1; j < lines.length; j++) {
          const l = lines[j].trim();
          if (!l) continue;
          if (/^[-*]\s+/.test(l)) {
            nextSteps.push(l.replace(/^[-*]\s+/, '').trim());
          }
        }
      }

      return {
        agent,
        timestamp,
        steps,
        next_steps: nextSteps,
        raw_content,
        raw_data: rawData
      };
    } catch (e) {
      console.error('Failed to parse agent message:', e);
      return null;
    }
  }
  // ...inside export class PlanDataService { (place near other parsers)

  /**
   * Parse streaming agent message fragments.
   * Supports:
   *  - { type: 'agent_message_streaming', data: "AgentMessageStreaming(agent_name='X', content='partial', is_final=False)" }
   *  - "AgentMessageStreaming(agent_name='X', content='partial', is_final=False)"
   */
  static parseAgentMessageStreaming(rawData: any): {
    agent: string;
    content: string;
    is_final: boolean;
    raw_data: any;
  } | null {
    try {
      // Unwrap wrapper
      if (rawData && typeof rawData === 'object' && rawData.type === 'agent_message_streaming' && typeof rawData.data === 'string') {
        return this.parseAgentMessageStreaming(rawData.data);
      }

      if (typeof rawData !== 'string') return null;
      if (!rawData.startsWith('AgentMessageStreaming(')) return null;

      const source = rawData;

      const agent =
        source.match(/agent_name='([^']+)'/)?.[1] ||
        source.match(/agent_name="([^"]+)"/)?.[1] ||
        'UnknownAgent';

      const contentMatch = source.match(/content='((?:\\'|[^'])*)'/);
      let content = contentMatch ? contentMatch[1] : '';
      content = content
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\');

      let is_final = false;
      const finalMatch = source.match(/is_final=(True|False)/i);
      if (finalMatch) {
        is_final = /True/i.test(finalMatch[1]);
      }

      return { agent, content, is_final, raw_data: rawData };
    } catch (e) {
      console.error('Failed to parse streaming agent message:', e);
      return null;
    }
  }

}