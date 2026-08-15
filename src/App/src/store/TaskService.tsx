import { Plan } from "../models";
import { Chat } from "../models/chatList";
import { apiService } from "../api/apiService";
import { parsePolicyBlock, PolicyBlockError } from "../api/policyBlock";
import { InputTask, InputTaskResponse } from "../models/inputTask";
import {
  forgetSignedInDevice,
  rememberSignedInName,
  signedInName,
} from "../models/signedInDevice";

/**
 * TaskService - Service for handling plan and session operations.
 *
 * Named for the domain it talks to, not for the surface: it creates Plans,
 * signs a device in, and hands the left panel its rows. Only the row-shaped
 * half speaks the chat vocabulary (ADR-025).
 */
export class TaskService {
  /**
   * Transform Plan data into the rows the ChatList renders — one per Chat.
   *
   * A Chat is a Session (ADR-025) and can hold more than one Plan, so this
   * groups by `session_id`: the row is named by the conversation's **first**
   * plan and carries its **latest** as the plan the row opens.
   *
   * **Every state** (#74). This used to hand back an `inProgress` bucket and a
   * `completed` one, of which the panel rendered the second — and `GET /plans`
   * filtered to `completed` anyway, so the first could never be populated.
   * Dead code twice over, and it hid the chat most worth resuming. One list
   * now, each row carrying its own status for the panel to state.
   *
   * The order is the history's own, which `GET /plans` gives newest-first: a
   * `Map` keeps insertion order, so a chat sits where its newest plan came.
   *
   * @param plansData Array of PlanWithSteps to transform
   * @returns One Chat per session, in every PlanStatus
   */
  static transformPlansToChats(plansData: Plan[]): Chat[] {
    if (!plansData || plansData.length === 0) {
      return [];
    }

    // A Chat is a Session (ADR-025), and ADR-024 has the escalation continue
    // the troubleshooting turn's session — so a row is a `session_id`, never a
    // plan. Keying rows by session while building one per plan is what put two
    // rows carrying one key on screen at the walkthrough's centrepiece (#71).
    const bySession = new Map<string, Plan[]>();
    plansData.forEach((plan) => {
      const group = bySession.get(plan.session_id);
      if (group) {
        group.push(plan);
      } else {
        bySession.set(plan.session_id, [plan]);
      }
    });

    const chats: Chat[] = [];

    bySession.forEach((group) => {
      const ordered = this.orderPlansByTime(group);
      const first = ordered[0];
      const latest = ordered[ordered.length - 1];

      chats.push({
        id: first.session_id,
        planId: latest.id,
        name: first.initial_goal,
        // The latest plan's own status, not a two-valued surface word: a chat
        // mid-escalation is in progress, and a row that can only say "not
        // completed" cannot tell a failed chat from a running one.
        status: latest.overall_status,
        date: this.formatPlanDate(latest.timestamp),
      });
    });

    return chats;
  }

  /**
   * When this chat was last active, as the panel says it.
   *
   * Total. `Intl.DateTimeFormat.format` throws `RangeError` on an unreadable
   * timestamp, and it is called while building the whole history — so one
   * malformed record took out every row rather than its own date. `Chat.date`
   * is optional and the row already renders without one.
   */
  private static formatPlanDate(timestamp: string): string | undefined {
    const at = Date.parse(timestamp);
    if (Number.isNaN(at)) return undefined;

    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "long",
      // timeStyle: "short",
    }).format(at);
  }

  /**
   * Order one chat's plans oldest-first.
   *
   * By `timestamp`, because the list's order is the API's and says nothing
   * about which turn came first within a conversation.
   *
   * An unreadable timestamp is not comparable with a readable one, and mixing
   * the two orderings gives a comparator that disagrees with itself — for
   * `[10:00, 09:00, unreadable]` it holds `a > b`, `b < c` and `a < c` at
   * once, so which plan names the row is left to the engine's sort. One
   * unreadable timestamp therefore hands the whole group back in the order the
   * history gave it, which is a real order even if it is not this one.
   */
  private static orderPlansByTime(plans: Plan[]): Plan[] {
    const times = plans.map((plan) => Date.parse(plan.timestamp));
    if (times.some(Number.isNaN)) return plans;

    return plans
      .map((plan, index) => ({ plan, index, at: times[index] }))
      .sort((a, b) => (a.at === b.at ? a.index - b.index : a.at - b.at))
      .map((entry) => entry.plan);
  }

  /**
   * Generate a session ID using the specified algorithm
   * @returns Generated session ID in format "sid_" + timestamp + "_" + random
   */
  static generateSessionId(): string {
    const timestamp = new Date().getTime();
    const random = Math.floor(Math.random() * 10000);
    return `sid_${timestamp}_${random}`;
  }
  /**
   * Split subtask action into description and function/details parts
   * @param action The full action string to split
   * @returns Object containing description and functionOrDetails
   */
  static splitSubtaskAction(action: string): {
    description: string;
    functionOrDetails: string | null;
  } {
    // Check for "Function:" pattern (with period before Function)

    const functionMatch = action.match(/^(.+?)\.\s*Function:\s*(.+)$/);
    if (functionMatch) {
      return {
        description: functionMatch[1].trim(),
        functionOrDetails: functionMatch[2].trim(),
      };
    }

    // Check for any colon pattern - split on first colon
    const colonIndex = action.indexOf(":");
    if (colonIndex !== -1) {
      return {
        description: action.substring(0, colonIndex).trim(),
        functionOrDetails: null,
      };
    }

    // If no colon found, return the full action as description
    return {
      description: action,
      functionOrDetails: null,
    };
  }
  /**
   * Clean text by converting any non-alphanumeric character to spaces
   * @param text The text string to clean
   * @returns Cleaned text string with only letters, numbers, and spaces
   */
  static cleanTextToSpaces(text: string): string {
    if (!text) return "";

    let cleanedText = text
      .replace("Hr_Agent", "HR Agent")
      .replace("Hr Agent", "HR Agent")
      .trim();

    // Convert camelCase and PascalCase to spaces
    // This regex finds lowercase letter followed by uppercase letter
    cleanedText = cleanedText.replace(/([a-z])([A-Z])/g, '$1 $2');

    // Replace any remaining non-alphanumeric characters with spaces
    cleanedText = cleanedText.replace(/[^a-zA-Z0-9]/g, ' ');

    // Clean up multiple spaces and trim
    cleanedText = cleanedText.replace(/\s+/g, ' ').trim();

    // Capitalize each word for better readability
    cleanedText = cleanedText.replace(/\b\w/g, (char) => char.toUpperCase());

    return cleanedText;
  }

  static cleanHRAgent(text: string): string {
    if (!text) return "";
    // Replace any non-alphanumeric character with a space
    let cleanedText = text
      .replace("Hr_Agent", "HR Agent")
      .replace("Hr Agent", "HR Agent")
      .trim();

    return cleanedText;
  }

  /**
   * Create a new plan with RAI validation
   * @param description Task description
   * @param teamId Optional team ID to use for this plan
   * @param lane The Lane declared by the Quick Task that was tapped, if any.
   *   Omitted for free-typed input, which the backend's lane router then
   *   routes by its keyword fallback (issue #16, ADR-013).
   * @param sessionId An existing conversation to continue. Omitted when a
   *   chat starts a new conversation.
   * @param startingTaskId The authored Quick Task initiating this request.
   * @returns Promise with the response containing plan ID, status and the
   *   lane actually taken
   */
  static async createPlan(
    description: string,
    teamId?: string,
    lane?: string,
    sessionId?: string,
    startingTaskId?: string,
  ): Promise<InputTaskResponse> {
    const requestSessionId = sessionId ?? this.generateSessionId();

    // The **Mocked unlock** (#27), materialised into this request's own
    // session. A session is one conversation — one **Simulated ticket**, one
    // **Lane** taken, one troubleshooting record — so the tab cannot simply
    // re-use the session it signed in on; each new one has the identity
    // written into it as it is created.
    //
    // The gate belongs here rather than at the call site, for the reason #22's
    // approval seam and #26's chips do: a gate the caller owns is a gate the
    // second caller forgets, and forgetting it here means the closing beat
    // silently refuses.
    //
    // Fails closed. A sign-in that could not be written leaves the request
    // anonymous — and the device forgets, so the header stops naming an
    // associate the gate is about to decline to answer for.
    if (signedInName()) {
      try {
        await apiService.signIn(requestSessionId);
      } catch {
        forgetSignedInDevice();
      }
    }

    const inputTask: InputTask = {
      session_id: requestSessionId,
      description: description,
      team_id: teamId,
      lane: lane,
      starting_task_id: startingTaskId,
    };

    try {
      return await apiService.createPlan(inputTask);
    } catch (error: any) {

      // A Policy block is not a failure to create a plan — it is the Identity
      // boundary gate working (ADR-014). Rethrow it intact so the surface can
      // render it as policy; everything else keeps the generic message.
      const policyBlock = parsePolicyBlock(error);
      if (policyBlock) {
        throw new PolicyBlockError(policyBlock);
      }

      // You can customize this logic as needed
      let message = "Unable to create plan. Please try again.";

      throw new Error(message);
    }
  }

  /**
   * Sign this device in, the mocked way (issue #27).
   *
   * The closing beat's one tap. It writes an identity into server-side
   * **Session state** — which is what the acceptance criterion asks for and
   * what makes the sign-in survive a mid-demo reload — and remembers the name
   * the route returned so the header and every later request agree about who
   * is signed in.
   *
   * The session it writes into is a fresh one and is not itself re-used: a
   * session is one conversation, and `createPlan` signs each new one in as it
   * creates it. One spare session-state record is a cheaper price than a tab
   * whose every conversation shares a ticket and a lane.
   *
   * @returns The associate's name, or null if nobody was signed in
   */
  static async signInDevice(): Promise<string | null> {
    try {
      const state = await apiService.signIn(this.generateSessionId());
      rememberSignedInName(state?.identity?.display_name);
    } catch {
      // Fails closed: an unwritten identity is an anonymous device, and an
      // anonymous device is the refusing state. Nothing is claimed.
      forgetSignedInDevice();
    }
    return signedInName();
  }
}

export default TaskService;
