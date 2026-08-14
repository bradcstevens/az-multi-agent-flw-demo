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

export interface QuickTask {
    id: string;
    name: string;
    prompt: string;
    lane?: string;
    followOn?: string;
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
    }));
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
