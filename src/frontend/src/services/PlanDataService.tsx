import {
  PlanWithSteps,
  Step,
  AgentType,
  ProcessedPlanData,
  PlanMessage,
  MPlanData,
  StepStatus,
  WebsocketMessageType,
  ParsedUserClarification,
  AgentMessageType
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
  static async submitClarification({
    request_id,
    answer,
    plan_id,
    m_plan_id
  }: {
    request_id: string;
    answer: string;
    plan_id: string;
    m_plan_id: string;
  }) {
    try {
      return apiService.submitClarification(request_id, answer, plan_id, m_plan_id);
    } catch (error) {
      console.log("Failed to submit clarification:", error);
      throw error;
    }
  }

  static parsePlanApprovalRequest(rawData: any): MPlanData | null {
    try {
      if (!rawData) return null;

      // Normalize to the PlanApprovalRequest(...) string that contains MPlan(...)
      let source: string | null = null;

      if (typeof rawData === 'object') {
        if (typeof rawData.data === 'string' && /PlanApprovalRequest\(plan=MPlan\(/.test(rawData.data)) {
          source = rawData.data;
        } else if (rawData.plan && typeof rawData.plan === 'object') {
          // Already structured style
          const mplan = rawData.plan;
          const userRequestText =
            typeof mplan.user_request === 'string'
              ? mplan.user_request
              : (Array.isArray(mplan.user_request?.items)
                ? (mplan.user_request.items.find((i: any) => i.text)?.text || '')
                : (mplan.user_request?.content || '')
              ).replace?.(/\u200b/g, '').trim() || 'Plan approval required';

          const steps = (mplan.steps || []).map((step: any, i: number) => {
            const action = step.action || '';
            const cleanAction = action
              .replace(/\*\*/g, '')
              .replace(/^Certainly!\s*/i, '')
              .replace(/^Given the team composition and the available facts,?\s*/i, '')
              .replace(/^here is a (?:concise )?plan[^.]*\.\s*/i, '')
              .replace(/^(?:here is|this is) a (?:concise )?(?:plan|approach|strategy)[^.]*[.:]\s*/i, '')
              .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ')
              .replace(/^[-•]\s*/, '')
              .replace(/\s+/g, ' ')
              .trim();
            return {
              id: i + 1,
              action,
              cleanAction,
              agent: step.agent || step._agent || 'System'
            };
          }).filter((s: any) => s.cleanAction.length > 3 && !/^(?:involvement|certainly|given|here is)/i.test(s.cleanAction));


          const result: MPlanData = {
            id: mplan.id || mplan.plan_id || 'unknown',
            status: (mplan.overall_status || rawData.status || 'PENDING_APPROVAL').toString().toUpperCase(),
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
          return result;
        }
      } else if (typeof rawData === 'string') {
        if (/PlanApprovalRequest\(plan=MPlan\(/.test(rawData)) {
          source = rawData;
        } else if (/^MPlan\(/.test(rawData)) {
          source = `PlanApprovalRequest(plan=${rawData})`;
        }
      }

      if (!source) return null;

      // Extract inner MPlan body
      const mplanMatch =
        source.match(/plan=MPlan\(([\s\S]*?)\),\s*status=/) ||
        source.match(/plan=MPlan\(([\s\S]*?)\)\s*\)/);
      const body = mplanMatch ? mplanMatch[1] : null;
      if (!body) return null;

      const pick = (re: RegExp, upper = false): string | undefined => {
        const m = body.match(re);
        return m ? (upper ? m[1].toUpperCase() : m[1]) : undefined;
      };

      const id = pick(/id='([^']+)'/) || pick(/id="([^"]+)"/) || 'unknown';
      const user_id = pick(/user_id='([^']*)'/) || '';
      const team_id = pick(/team_id='([^']*)'/) || '';
      const plan_id = pick(/plan_id='([^']*)'/) || '';
      let overall_status =
        pick(/overall_status=<PlanStatus\.([a-zA-Z_]+):/, true) ||
        pick(/overall_status='([^']+)'/, true) ||
        'PENDING_APPROVAL';

      const outerStatus =
        source.match(/status='([^']+)'/)?.[1] ||
        source.match(/status="([^"]+)"/)?.[1];
      const status = (outerStatus || overall_status || 'PENDING_APPROVAL').toUpperCase();

      let user_request =
        source.match(/text='([^']+)'/)?.[1] ||
        source.match(/text="([^"]+)"/)?.[1] ||
        'Plan approval required';
      user_request = user_request.replace(/\\u200b/g, '').trim();

      const teamRaw = body.match(/team=\[([^\]]*)\]/)?.[1] || '';
      const team = teamRaw
        .split(',')
        .map(s => s.trim().replace(/['"]/g, ''))
        .filter(Boolean);

      const facts =
        body
          .match(/facts="([^"]*(?:\\.[^"]*)*)"/)?.[1]
          ?.replace(/\\n/g, '\n')
          .replace(/\\"/g, '"') || '';

      const steps: MPlanData['steps'] = [];
      const stepRegex = /MStep\(([^)]*?)\)/g;
      let stepMatch: RegExpExecArray | null;
      let idx = 1;
      const seen = new Set<string>();
      while ((stepMatch = stepRegex.exec(body)) !== null) {
        const chunk = stepMatch[1];
        const agent =
          chunk.match(/agent='([^']+)'/)?.[1] ||
          chunk.match(/agent="([^"]+)"/)?.[1] ||
          'System';
        const actionRaw =
          chunk.match(/action='([^']+)'/)?.[1] ||
          chunk.match(/action="([^"]+)"/)?.[1] ||
          '';
        if (!actionRaw) continue;

        const cleanAction = actionRaw
          .replace(/\*\*/g, '')
          .replace(/^Certainly!\s*/i, '')
          .replace(/^Given the team composition and the available facts,?\s*/i, '')
          .replace(/^here is a (?:concise )?plan to[^.]*\.\s*/i, '')
          .replace(/^\*\*([^*]+)\*\*:?\s*/g, '$1: ')
          .replace(/^[-•]\s*/, '')
          .replace(/\s+/g, ' ')
          .trim();

        const key = cleanAction.toLowerCase();
        if (
          cleanAction.length > 3 &&
          !seen.has(key) &&
          !/^(?:here is|this is|given|certainly|involvement)$/i.test(cleanAction)
        ) {
          seen.add(key);
          steps.push({
            id: idx++,
            action: actionRaw,
            cleanAction,
            agent
          });
        }
      }

      let participant_descriptions: Record<string, string> = {};
      const pdMatch =
        source.match(/participant_descriptions['"]?\s*:\s*({[^}]*})/) ||
        source.match(/'participant_descriptions':\s*({[^}]*})/);
      if (pdMatch?.[1]) {
        const jsonish = pdMatch[1]
          .replace(/'/g, '"')
          .replace(/([a-zA-Z0-9_]+)\s*:/g, '"$1":');
        try {
          participant_descriptions = JSON.parse(jsonish);
        } catch {
          participant_descriptions = {};
        }
      }

      const result: MPlanData = {
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
        user_id,
        team_id,
        plan_id,
        overall_status,
        raw_data: rawData
      };

      return result;
    } catch (e) {
      console.error('parsePlanApprovalRequest failed:', e);
      return null;
    }
  }

  /**
   * Parse an agent message object or repr string:
   * Input forms supported:
   *  - { type: 'agent_message', data: "AgentMessage(agent_name='X', timestamp=..., content='...')"}
   *  - "AgentMessage(agent_name='X', timestamp=..., content='...')"
   * Returns a structured object with steps parsed from markdown-ish content.
   */
  // ...inside class PlanDataService
  static parseAgentMessage(rawData: any): {
    agent: string;
    agent_type: AgentMessageType;
    timestamp: number | null;
    steps: Array<{
      title: string;
      fields: Record<string, string>;
      summary?: string;
      raw_block: string;
    }>;
    next_steps: string[];
    content: string;
    raw_data: any;
  } | null {
    try {
      // Unwrap wrapper
      if (rawData && typeof rawData === 'object' &&
        rawData.type === WebsocketMessageType.AGENT_MESSAGE &&
        typeof rawData.data === 'string') {
        return this.parseAgentMessage(rawData.data);
      }

      if (typeof rawData !== 'string') return null;
      if (!rawData.startsWith('AgentMessage(')) return null;

      const source = rawData;

      const agent =
        source.match(/agent_name='([^']+)'/)?.[1] ||
        source.match(/agent_name="([^"]+)"/)?.[1] ||
        'UnknownAgent';

      const timestampStr = source.match(/timestamp=([\d.]+)/)?.[1];
      const timestamp = timestampStr ? Number(timestampStr) : null;

      // Support single or double quoted content
      const contentMatch = source.match(/content=(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)')/);
      let content = contentMatch ? (contentMatch[1] ?? contentMatch[2] ?? '') : '';
      content = content
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\');

      // Simplify human clarification inline if present
      content = this.simplifyHumanClarification(content);

      // Parse sections
      const lines = content.split('\n');
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
              if (summaryMatch) summary = summaryMatch[1].trim();
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

      // Next Steps
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
        agent_type: AgentMessageType.AI_AGENT,
        timestamp,
        steps,
        next_steps: nextSteps,
        content,
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
  // Replace the body of parseAgentMessageStreaming with this improved version
  static parseAgentMessageStreaming(rawData: any): {
    agent: string;
    content: string;
    is_final: boolean;
    raw_data: any;
  } | null {
    try {
      // Unwrap wrapper object
      if (
        rawData &&
        typeof rawData === 'object' &&
        rawData.type === WebsocketMessageType.AGENT_MESSAGE_STREAMING &&
        typeof rawData.data === 'string'
      ) {
        return this.parseAgentMessageStreaming(rawData.data);
      }

      if (typeof rawData !== 'string') return null;
      if (!rawData.startsWith('AgentMessageStreaming(')) return null;

      const source = rawData;

      const agent =
        source.match(/agent_name='([^']+)'/)?.[1] ||
        source.match(/agent_name="([^"]+)"/)?.[1] ||
        'UnknownAgent';

      // Support content='...' OR content="..." with escapes
      const contentMatch = source.match(/content=(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)')/);
      let content = contentMatch ? (contentMatch[1] ?? contentMatch[2] ?? '') : '';
      content = content
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .trim();

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
  // Place inside export class PlanDataService (near other parsers)

  /**
   * Simplify a human clarification streaming line.
   * Input example:
   *   Human clarification: UserClarificationResponse(request_id='uuid', answer='no more steps', plan_id='', m_plan_id='')
   * Output (markdown/plain):
   *   Human clarification: no more steps
   * If pattern not found, returns the original string.
   */
  static simplifyHumanClarification(line: string): string {
    if (
      typeof line !== 'string' ||
      !line.includes('Human clarification:') ||
      !line.includes('UserClarificationResponse(')
    ) {
      return line;
    }

    // Capture the inside of UserClarificationResponse(...)
    const outerMatch = line.match(/Human clarification:\s*UserClarificationResponse\((.*?)\)/s);
    if (!outerMatch) return line;

    const inner = outerMatch[1];

    // Find answer= '...' | "..."
    const answerMatch = inner.match(/answer=(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)')/);
    if (!answerMatch) return line;

    let answer = answerMatch[1] ?? answerMatch[2] ?? '';
    // Unescape common sequences
    answer = answer
      .replace(/\\n/g, '\n')
      .replace(/\\'/g, "'")
      .replace(/\\"/g, '"')
      .replace(/\\\\/g, '\\')
      .trim();

    return `Human clarification: ${answer}`;
  }
  /**
   * Parse a user clarification request message (possibly deeply nested).
   * Accepts objects like:
   * {
   *   type: 'user_clarification_request',
   *   data: { type: 'user_clarification_request', data: { type: 'user_clarification_request', data: "UserClarificationRequest(...)" } }
   * }
   * Returns ParsedUserClarification or null if not parsable.
   */
  // ...existing code...
  /**
   * Parse a user clarification request message (possibly deeply nested).
   * Enhanced to support:
   *  - question in single OR double quotes
   *  - request_id in single OR double quotes
   *  - escaped newline / quote sequences
   */
  static parseUserClarificationRequest(rawData: any): ParsedUserClarification | null {
    try {
      const extractString = (val: any, depth = 0): string | null => {
        if (depth > 15) return null;
        if (typeof val === 'string') {
          return val.startsWith('UserClarificationRequest(') ? val : null;
        }
        if (val && typeof val === 'object') {
          // Prefer .data traversal
          if (val.data !== undefined) {
            const inner = extractString(val.data, depth + 1);
            if (inner) return inner;
          }
          for (const k of Object.keys(val)) {
            if (k === 'data') continue;
            const inner = extractString(val[k], depth + 1);
            if (inner) return inner;
          }
        }
        return null;
      };

      const source = extractString(rawData);
      if (!source) return null;

      // question=( "...") OR ('...')
      const questionRegex = /question=(?:"((?:\\.|[^"])*)"|'((?:\\.|[^'])*)')/;
      const qMatch = source.match(questionRegex);
      if (!qMatch) return null;

      let question = (qMatch[1] ?? qMatch[2] ?? '')
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .trim();

      // request_id='uuid' or "uuid"
      const requestIdRegex = /request_id=(?:"([a-fA-F0-9-]+)"|'([a-fA-F0-9-]+)')/;
      const rMatch = source.match(requestIdRegex);
      if (!rMatch) return null;
      const request_id = rMatch[1] ?? rMatch[2];

      return {
        type: WebsocketMessageType.USER_CLARIFICATION_REQUEST,
        question,
        request_id
      };
    } catch (e) {
      console.error('parseUserClarificationRequest failed:', e);
      return null;
    }
  }
  // ...inside export class PlanDataService (place near other parsers) ...

  /**
   * Parse a final result message (possibly nested).
   * Accepts structures like:
   * {
   *   type: 'final_result_message',
   *   data: { type: 'final_result_message', data: { content: '...', status: 'completed', timestamp: 12345.6 } }
   * }
   * Returns null if not parsable.
   */
  static parseFinalResultMessage(rawData: any): {
    type: WebsocketMessageType;
    content: string;
    status: string;
    timestamp: number | null;
    raw_data: any;
  } | null {
    try {
      const extractPayload = (val: any, depth = 0): any => {
        if (depth > 10) return null;
        if (!val || typeof val !== 'object') return null;
        // If it has content & status, assume it's the payload
        if (('content' in val) && ('status' in val)) return val;
        if ('data' in val) {
          const inner = extractPayload(val.data, depth + 1);
          if (inner) return inner;
        }
        // Scan other keys as fallback
        for (const k of Object.keys(val)) {
          if (k === 'data') continue;
          const inner = extractPayload(val[k], depth + 1);
          if (inner) return inner;
        }
        return null;
      };

      const payload = extractPayload(rawData);
      if (!payload) return null;

      let content = typeof payload.content === 'string' ? payload.content : '';
      content = content
        .replace(/\\n/g, '\n')
        .replace(/\\'/g, "'")
        .replace(/\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .trim();

      const statusRaw = (payload.status || 'completed').toString().trim();
      const status = statusRaw.toLowerCase();

      let timestamp: number | null = null;
      if (payload.timestamp != null) {
        const num = Number(payload.timestamp);
        if (!Number.isNaN(num)) timestamp = num;
      }

      return {
        type: WebsocketMessageType.FINAL_RESULT_MESSAGE,
        content,
        status,
        timestamp,
        raw_data: rawData
      };
    } catch (e) {
      console.error('parseFinalResultMessage failed:', e);
      return null;
    }
  }


}