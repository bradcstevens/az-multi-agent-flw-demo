import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * What this repository authored, read out of the repository.
 *
 * The same rule `scripts/preflight/deployed_surface.py` follows, and for the
 * same reason: a check carrying its own copy of the surface's strings passes a
 * rebrand it never saw (the ADR-019 lesson). The **Rehearsed hit** is the
 * sharpest case — `corpus.toml` names both the question the walkthrough opens
 * with *and* the `SOP-NNN` that answers it, precisely because renaming the
 * document away leaves a one-tap task that still resolves, honestly, as *that
 * procedure is not in the library*. Nothing goes red, and the centrepiece beat
 * has quietly become the honest-miss beat played twice.
 *
 * So the validator asks the corpus which document it must be answered from,
 * rather than being told once and believing it forever.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(HERE, '..');

const SOP_CORPUS = join(REPO_ROOT, 'content', 'sop', 'corpus.toml');
const STORE_PACK = join(
    REPO_ROOT,
    'content_packs',
    'store_assistant',
    'agent_teams',
    'store_assistant.json',
);
const SURFACE_MODULE = join(
    REPO_ROOT,
    'src',
    'App',
    'src',
    'models',
    'storeSurface.ts',
);
const TICKET_MODULE = join(
    REPO_ROOT,
    'src',
    'backend',
    'escalation',
    'ticket.py',
);
const LANE_MODULE = join(REPO_ROOT, 'src', 'backend', 'lane', 'lane.py');

export interface QuickTask {
    id: string;
    name: string;
    prompt: string;
    lane?: string;
    followOn?: string;
    rehearsedReplies: string[];
    planSteps: PlanStep[];
}

/** One authored Reviewable-plan step on a Quick Task. */
export interface PlanStep {
    id: number;
    assignee?: PlanAssignee;
}

/**
 * Who an authored step reaches.
 *
 * `simulated` is the field ADR-037 hangs the disclosure on, and it is the one
 * that separates the two invented colleagues from the associate holding the
 * device — so a beat that grades *the plan shows its stand-ins by name* reads
 * it rather than deciding for itself which of the three names is which.
 */
export interface PlanAssignee {
    kind?: string;
    name?: string;
    relation?: string;
    simulated?: boolean;
}

/** The people an authored Quick Task's plan reaches, in its declared order. */
export function planPeople(task: QuickTask): PlanAssignee[] {
    return task.planSteps
        .map((step) => step.assignee)
        .filter(
            (assignee): assignee is PlanAssignee =>
                assignee?.kind === 'person' && typeof assignee.name === 'string',
        );
}

/** One member of the **Store assistant roster**, as the pack authors it. */
export interface RosterAgent {
    /** The pack's own name — `WorkforceAgent`, and the roster panel's testid. */
    name: string;
    /** The tool domain it holds, which is what makes it that specialist. */
    toolbox: string;
    deploymentName: string;
}

export interface RehearsedHit {
    /** The words the presenter taps first. */
    question: string;
    /** The Quick Task card that carries them. */
    quickTask: string;
    /** The `SOP-NNN` the answer must cite. */
    docId: string;
}

/** The name the store surface calls itself, from its own module. */
export function assistantName(): string {
    const source = readFileSync(SURFACE_MODULE, 'utf-8');
    const match = source.match(/export const ASSISTANT_NAME = '([^']*)'/);
    if (!match) {
        throw new Error(`ASSISTANT_NAME is not exported by ${SURFACE_MODULE}`);
    }
    return match[1];
}

/** The walkthrough's opening beat, from the corpus it was written against. */
export function rehearsedHit(): RehearsedHit {
    const section = tomlSection(SOP_CORPUS, 'rehearsed_hit');
    return {
        question: tomlString(section, 'question'),
        quickTask: tomlString(section, 'quick_task'),
        docId: tomlString(section, 'doc_id'),
    };
}

/** The Quick Tasks the store pack authors, in the order they render. */
export function quickTasks(): QuickTask[] {
    const pack = JSON.parse(readFileSync(STORE_PACK, 'utf-8'));
    return (pack.starting_tasks || []).map((task: Record<string, unknown>) => ({
        id: requiredTaskString(task, 'id'),
        name: requiredTaskString(task, 'name'),
        prompt: requiredTaskString(task, 'prompt'),
        lane: optionalTaskString(task, 'lane'),
        followOn: optionalTaskString(task, 'follow_on'),
        rehearsedReplies: Array.isArray(task.rehearsed_replies)
            ? task.rehearsed_replies.filter(
                  (reply): reply is string =>
                      typeof reply === 'string' && reply.trim() !== '',
              )
            : [],
        planSteps: Array.isArray(task.plan_steps)
            ? task.plan_steps.filter(
                  (step): step is PlanStep =>
                      typeof step === 'object' &&
                      step !== null &&
                      typeof (step as PlanStep).id === 'number',
              )
            : [],
    }));
}

/** The **Store assistant roster**, as the pack authors it. */
export function rosterAgents(): RosterAgent[] {
    const pack = JSON.parse(readFileSync(STORE_PACK, 'utf-8'));
    return (pack.agents || []).map((agent: Record<string, unknown>) => ({
        name: String(agent.name ?? ''),
        toolbox: String(agent.toolbox_filter ?? ''),
        deploymentName: String(agent.deployment_name ?? ''),
    }));
}

/**
 * The specialist that holds one tool domain.
 *
 * A beat is about a *specialist*, and the durable thing about a specialist is
 * the domain it holds — `workforce`, the MCP server's own tool domain — not the
 * name somebody gave it. Read this way, a renamed agent is followed rather than
 * reported as a missing one.
 */
export function agentHoldingToolbox(toolbox: string): RosterAgent {
    const found = rosterAgents().filter((agent) => agent.toolbox === toolbox);
    if (found.length !== 1) {
        throw new Error(
            `the store pack roster has ${found.length} agents holding the ` +
                `${JSON.stringify(toolbox)} toolbox. One domain has one holder, ` +
                'so this is a pack that needs reading, not a tie-break',
        );
    }
    return found[0];
}

/**
 * A roster name and a cost-table cell, compared without their presentation.
 *
 * The **Agent display name** rule has three implementations between the pack
 * and the pixel — the backend humanises the executor id, the frontend strips
 * the suffix the column heading already carries, and both apply casing rules of
 * their own (`HRHelperAgent` reaches the screen as `HR Helper`). A fourth copy
 * here would be a check that goes red on a spelling both of the others agree
 * about, which is the ADR-019 lesson pointing the other way.
 *
 * So the comparison drops everything the presentation decides — case, spaces,
 * punctuation and the `Agent` suffix — and keeps what identifies the
 * specialist. `WorkforceAgent`, `workforce_agent`, `Workforce Agent` and
 * `Workforce` are one agent; `ShiftTasksAgent` is not that agent, which is the
 * only distinction this beat has to make.
 */
export function agentKey(name: string): string {
    return name
        .replace(/[^a-z0-9]+/gi, '')
        .toLowerCase()
        .replace(/agents?$/, '');
}

/** The Quick Task carrying a given card title. */
export function quickTaskNamed(name: string): QuickTask {
    const found = quickTasks().find((task) => task.name === name);
    if (!found) {
        throw new Error(
            `no Quick Task named ${JSON.stringify(name)} in the store pack — ` +
                'the corpus and the pack have drifted apart',
        );
    }
    return found;
}

/**
 * The one task that offers both rehearsed replies and a conversation follow-on.
 *
 * The validator reads the handoff from the authored roster rather than carrying
 * either task's title or prompt as a second description of the walkthrough.
 */
export function troubleshootingTask(): QuickTask {
    return sole(
        quickTasks().filter(
            (task) => task.followOn && task.rehearsedReplies.length > 0,
        ),
        'a troubleshooting Quick Task with a follow-on and rehearsed replies',
    );
}

/** The task the authored troubleshooting card continues to. */
export function followOnTaskFor(task: QuickTask): QuickTask {
    if (!task.followOn) {
        throw new Error(`Quick Task ${task.id} has no follow-on`);
    }

    return sole(
        quickTasks().filter((candidate) => candidate.id === task.followOn),
        `the follow-on ${task.followOn} for Quick Task ${task.id}`,
    );
}

/** The Deliberate lane's value, from the router that defines it. */
export function deliberateLane(): string {
    return pythonString(LANE_MODULE, 'DELIBERATE');
}

/** The shape a simulated ticket's number has, from the ticket module. */
export function ticketNumberPattern(): RegExp {
    const prefix = pythonString(TICKET_MODULE, 'TICKET_ID_PREFIX');
    return new RegExp(
        `^${prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\d{4}$`,
    );
}

function requiredTaskString(task: Record<string, unknown>, key: string): string {
    const value = optionalTaskString(task, key);
    if (!value) {
        throw new Error(`a Quick Task has no non-empty ${key}`);
    }
    return value;
}

function optionalTaskString(
    task: Record<string, unknown>,
    key: string,
): string | undefined {
    const value = task[key];
    return typeof value === 'string' && value.trim() ? value : undefined;
}

/** A module-level `NAME = "value"` read from its authored definition. */
function pythonString(path: string, name: string): string {
    const source = readFileSync(path, 'utf-8');
    const match = source.match(
        new RegExp(`^\\s*${name}\\s*=\\s*"([^"]*)"`, 'm'),
    );
    if (!match) {
        throw new Error(`${name} is not declared by ${path}`);
    }
    return match[1];
}

/** Exactly one authored task, or a failure that names the ambiguous roster. */
function sole(found: QuickTask[], what: string): QuickTask {
    if (found.length !== 1) {
        throw new Error(
            `the store pack has ${found.length} of: ${what}. The walkthrough ` +
                'has one of each beat, so a beat this suite cannot identify ' +
                'is a pack that needs reading, not a test that needs a tie-break',
        );
    }
    return found[0];
}

/**
 * Read one `[section]` out of a TOML file.
 *
 * A hand-rolled reader rather than a dependency, and **scoped to one section**
 * rather than searching the whole file: `question` is a key in both
 * `[rehearsed_hit]` and `[honest_miss]`, so a whole-file match would answer the
 * opening beat with the question the corpus deliberately cannot answer.
 */
function tomlSection(path: string, name: string): string {
    const source = readFileSync(path, 'utf-8');
    const start = source.indexOf(`[${name}]`);
    if (start < 0) {
        throw new Error(`${path} has no [${name}] section`);
    }
    const rest = source.slice(start + name.length + 2);
    const next = rest.search(/^\[/m);
    return next < 0 ? rest : rest.slice(0, next);
}

function tomlString(section: string, key: string): string {
    const match = section.match(new RegExp(`^${key}\\s*=\\s*"([^"]*)"`, 'm'));
    if (!match) {
        throw new Error(`no ${key} in the section read`);
    }
    return match[1];
}
