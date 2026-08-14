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
const TICKET_MODULE = join(REPO_ROOT, 'src', 'backend', 'escalation', 'ticket.py');
const LANE_MODULE = join(REPO_ROOT, 'src', 'backend', 'lane', 'lane.py');

export interface QuickTask {
    id: string;
    name: string;
    prompt: string;
    lane?: string;
    /** The one-tap answers this task authors, if it provokes a Clarification. */
    rehearsedReplies: string[];
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
        id: task.id as string,
        name: task.name as string,
        prompt: task.prompt as string,
        lane: task.lane as string | undefined,
        rehearsedReplies: Array.isArray(task.rehearsed_replies)
            ? (task.rehearsed_replies as string[])
            : [],
    }));
}

/**
 * The troubleshooting beat's Quick Task — the one that asks a question back.
 *
 * Found by the property that *makes* it that beat rather than by its title.
 * Only the task that provokes a **Clarification** authors **Rehearsed
 * replies**, because there is nothing else for a one-tap answer to answer; a
 * suite naming the card instead would go green on a pack that renamed the beat
 * away and red on a pack that merely retitled the card.
 */
export function troubleshootingTask(): QuickTask {
    return sole(
        quickTasks().filter((task) => task.rehearsedReplies.length > 0),
        'Quick Task authoring Rehearsed replies',
    );
}

/**
 * The escalation beat's Quick Task — the one that declares the Deliberate lane.
 *
 * Same rule, and the same reason it is the *declaration* that identifies it:
 * the beat exists to show the approval step, and the approval step is the
 * Lane's one mechanical consequence (`lane.py`). A second task declaring
 * `deliberate` would make "the escalation" ambiguous, which is a pack that
 * needs reading rather than a test that needs a tie-break.
 */
export function escalationTask(): QuickTask {
    return sole(
        quickTasks().filter((task) => task.lane === deliberateLane()),
        `Quick Task declaring the ${deliberateLane()} lane`,
    );
}

/**
 * What the associate reports having already tried, when the escalation asks.
 *
 * The escalation Quick Task authors no **Rehearsed replies** of its own, so the
 * beat types one — and it types the pack's *own* first rehearsed reply rather
 * than a sentence invented here, for ADR-019's reason: an answer this file
 * carried a copy of would survive a rewrite of the runbook it is supposed to be
 * an answer to.
 */
export function attemptedStepAnswer(): string {
    const replies = troubleshootingTask().rehearsedReplies;
    if (replies.length === 0) {
        throw new Error('the troubleshooting Quick Task authors no rehearsed replies');
    }
    return replies[0];
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

/** The Deliberate lane's value on the wire, from the enum that defines it. */
export function deliberateLane(): string {
    const source = readFileSync(LANE_MODULE, 'utf-8');
    const match = source.match(/DELIBERATE\s*=\s*"([^"]*)"/);
    if (!match) {
        throw new Error(`Lane.DELIBERATE is not declared in ${LANE_MODULE}`);
    }
    return match[1];
}

/**
 * The shape a **Simulated ticket**'s number must have, from the module that
 * mints it.
 *
 * `SIM-` is not decoration: the number outlives the card it was rendered on —
 * an associate can read it down a telephone a week later — so it carries the
 * simulation with it. Read from `ticket.py` rather than pinned here, because a
 * prefix quietly changed to something that reads like a real service desk's is
 * exactly the change this assertion exists to catch.
 */
export function ticketNumberPattern(): RegExp {
    const prefix = pythonString(TICKET_MODULE, 'TICKET_ID_PREFIX');
    return new RegExp(`^${prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\d{4}$`);
}

/** TKT-001's answer for a field nothing answered, from the module that fills it. */
export function notReported(): string {
    return pythonString(TICKET_MODULE, 'NOT_REPORTED');
}

/** A module-level `NAME = "value"` out of a Python module. */
function pythonString(path: string, name: string): string {
    const source = readFileSync(path, 'utf-8');
    const match = source.match(new RegExp(`^${name}\\s*=\\s*"([^"]*)"`, 'm'));
    if (!match) {
        throw new Error(`no ${name} in ${path}`);
    }
    return match[1];
}

/** Exactly one, or a failure that names what was ambiguous. */
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
