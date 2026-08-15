/**
 * What the surface says between a question being submitted and its answer
 * arriving (issue #64, ADR-023).
 *
 * One module, for the reason `storeSurface.ts` is one module: six components
 * each carried their own copy of this moment — *"Creating a plan"*, *"Creating
 * your plan..."*, *"Creating plan..."*, *"Plan is being generated..."*, a
 * 3000ms rotation through four authored stages — and they had already drifted
 * into telling the story backwards. Six places to disagree about what the
 * system is doing becomes one place to be correct.
 *
 * The rule is the transparency surfaces' rule applied to *progress*: a phase is
 * entered only when a **real signal reports it**, and where nothing has arrived
 * the surface holds the last true statement rather than inventing the next one.
 * Nothing here is on a timer. A scripted progress bar three inches from the
 * Token meter invites an audience to re-read the meter as scripted too.
 */

import { Lane, LANE_LABELS } from './lane';
import { getAgentDisplayNameWithSuffix } from '../utils/agentIconUtils';

/**
 * The phases, in the order they may be entered.
 *
 * Every one is an observable event — see ADR-023's table. There is deliberately
 * no "agents selected" phase, because no such event exists anywhere in the
 * system: the nearest real signal is an agent *producing output*, which is a
 * different claim and is the one `working` makes.
 */
export const REQUEST_PHASES = [
    'idle',
    'sent',
    'routed',
    'connected',
    'working',
    'done',
] as const;

export type RequestPhase = (typeof REQUEST_PHASES)[number];

/**
 * Whether a phase may be entered from the one the surface is in.
 *
 * Monotonic, and enforced here rather than at each call site: across two
 * components "only advances" is a coincidence, not a property. Re-entering the
 * current phase is not an advance either — a second `connection_status` on a
 * reconnect must not un-say which agent is responding.
 */
export const advancesTo = (from: RequestPhase, to: RequestPhase): boolean =>
    REQUEST_PHASES.indexOf(to) > REQUEST_PHASES.indexOf(from);

/** Everything a phase's words can be drawn from, and nothing else. */
export interface NarrationSubject {
    phase: RequestPhase;
    /** The lane the router decided, as `LaneBadge` reads it. */
    lane?: Lane | null;
    /** The executor named by `agent_message_streaming`, spelled as it arrived. */
    executor?: string | null;
}

/** What the surface says while the POST is in flight. */
export const SENDING = 'Sending your question...';

/**
 * What the chat page says while the plan record itself is being fetched.
 *
 * A different claim from the phases above — it is about the *record*, not about
 * the request — and it lives here for the same reason they do: a component
 * holding its own copy is how six of them came to disagree.
 */
export const LOADING_PLAN = 'Loading plan data...';

/**
 * What the two places a plan is shown say when one has been announced but its
 * steps have not arrived.
 *
 * Both of them, from here, because they are two views of one moment: the plan
 * card in the conversation and the rail's Plan Overview. It is said only where
 * a plan is actually coming — a Fast-lane request says *"No plan to review on
 * this request."*, and "being generated" for that one is a spinner that never
 * resolves.
 */
export const PLAN_ARRIVING = 'Plan is being generated...';

/** What the surface says when an agent is responding but is not named. */
export const AN_AGENT_RESPONDING = 'An agent is responding...';

/**
 * The lane, announced in the **Lane badge**'s own words.
 *
 * Reads `LANE_LABELS` rather than restating it, so the narration and the badge
 * cannot disagree about the lane a request took.
 */
export const routedTo = (lane: Lane): string => `Routed — ${LANE_LABELS[lane]}`;

/** Names the parsers and the orchestrator invent when a frame names nobody. */
const UNRESOLVED = new Set(['unknown', 'unknownagent', 'assistant', 'magenticagent']);

/**
 * The executor, resolved through the display-name pipeline the roster panels use.
 *
 * Returns `null` for a name that cannot be resolved rather than the pipeline's
 * own `Assistant Agent` fallback, which is an agent nobody configured appearing
 * on screen as though the frame had named it. The stand-ins the wire parsers
 * substitute — `UnknownAgent`, `unknown` — are the same claim in a different
 * spelling and are refused for the same reason.
 */
export const respondingAgent = (executor: string | null | undefined): string | null => {
    const raw = executor?.trim();
    if (!raw) return null;
    if (UNRESOLVED.has(raw.toLowerCase())) return null;
    return getAgentDisplayNameWithSuffix(raw);
};

/**
 * What the surface says, given everything a signal has reported so far.
 *
 * `null` means **say nothing** — before a question has been asked, and once the
 * answer or the plan has arrived. The second of those is the rule that makes
 * the narration *stop*: on the Fast lane there is no `plan_approval_request`
 * at all, so a `done` that did not silence the indicator would leave it running
 * for the rest of the conversation (#69).
 */
export const narrate = ({ phase, lane, executor }: NarrationSubject): string | null => {
    if (phase === 'idle' || phase === 'done') return null;

    if (phase === 'working') {
        return `${respondingAgent(executor) ?? 'An agent'} is responding...`;
    }

    // `connected` is plumbing and says nothing of its own, so it holds whatever
    // the last real signal reported — the lane, if the router has decided one.
    if (lane) return routedTo(lane);

    return SENDING;
};
