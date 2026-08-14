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
const PROVENANCE_MODULE = join(
    REPO_ROOT,
    'src',
    'backend',
    'sop',
    'provenance.py',
);
const API_SERVICE_MODULE = join(
    REPO_ROOT,
    'src',
    'App',
    'src',
    'api',
    'apiService.tsx',
);
const CHORD_MODULE = join(
    REPO_ROOT,
    'src',
    'App',
    'src',
    'models',
    'presenterChord.ts',
);
const CHORD_HOOK = join(
    REPO_ROOT,
    'src',
    'App',
    'src',
    'hooks',
    'usePresenterChord.tsx',
);
const ALERT_ROSTER = join(
    REPO_ROOT,
    'src',
    'backend',
    'transparency',
    'alert.py',
);

export interface QuickTask {
    id: string;
    name: string;
    prompt: string;
    lane?: string;
}

export interface RehearsedHit {
    /** The words the presenter taps first. */
    question: string;
    /** The Quick Task card that carries them. */
    quickTask: string;
    /** The `SOP-NNN` the answer must cite. */
    docId: string;
}

export interface HonestMiss {
    /** The question the corpus deliberately cannot answer. */
    question: string;
    /** The Quick Task card that asks it. */
    quickTask: string;
}

/**
 * What the **cross-platform hop** must name, from the backend that names it.
 *
 * `sop/provenance.py` puts these two strings on the `source_used` payload, and
 * the Grounding panel puts them on the badge and the route. Every beat that
 * reads the panel asserts the same two constants, so they are read once rather
 * than transcribed into each spec — where the transcription that goes stale is
 * a beat failing, on a working demonstration, over a rename.
 */
export function sopProvenance(): { platform: string; source: string } {
    const source = readFileSync(PROVENANCE_MODULE, 'utf-8');
    return {
        platform: pythonString(source, 'SOP_PLATFORM'),
        source: pythonString(source, 'SOP_SOURCE'),
    };
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

/**
 * The rehearsed miss, from the corpus that decides it is one.
 *
 * The corpus is the *only* thing that makes this question a miss — `Store 223`
 * is written as a forecourt with no vehicle wash, and `absent_terms` is the
 * list somebody adding a procedure has to read. A validator that wrote the
 * question down here would go on asserting a miss after the library grew a car
 * wash procedure: the one change that breaks the beat, reported as no change
 * at all.
 */
export function honestMiss(): HonestMiss {
    const section = tomlSection(SOP_CORPUS, 'honest_miss');
    return {
        question: tomlString(section, 'question'),
        quickTask: tomlString(section, 'quick_task'),
    };
}

/** The Quick Tasks the store pack authors, in the order they render. */
export function quickTasks(): QuickTask[] {
    const pack = JSON.parse(readFileSync(STORE_PACK, 'utf-8'));
    return (pack.starting_tasks || []).map((task: Record<string, string>) => ({
        id: task.id,
        name: task.name,
        prompt: task.prompt,
        lane: task.lane,
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
 * The Quick Task with a given id.
 *
 * Two beats — the **boundary probe** and the **shift-task** question — have no
 * entry in the SOP corpus, because neither is answered from it: one is refused
 * before any agent runs and the other is the setup for a message nobody asked
 * for. The store pack is their only authored source, and the **id** is what the
 * pack keys them by. The words are still read rather than restated, which is
 * the whole rule: a card retitled or a prompt reworded must change the beat,
 * and a card *deleted* must fail it here rather than time out on a tap.
 */
export function quickTaskWithId(id: string): QuickTask {
    const found = quickTasks().find((task) => task.id === id);
    if (!found) {
        throw new Error(
            `the store pack has no Quick Task with id ${JSON.stringify(id)}`,
        );
    }
    return found;
}

/** The personal question the Identity boundary gate refuses (beat 5). */
export function boundaryProbe(): QuickTask {
    return quickTaskWithId('task-223-identity');
}

/** The shift-task question the proactive alert lands beside (beat 7). */
export function shiftTaskProbe(): QuickTask {
    return quickTaskWithId('task-223-shift-tasks');
}

/**
 * One route out of the surface's own endpoint table.
 *
 * A beat that watches what the browser asked has to name the route it is
 * watching, and a route named twice is a route that goes stale in one of the
 * two places. These are versioned (`/v4/`) and have moved before; a rename
 * would leave a beat observing no traffic at all and failing with *the surface
 * asked nothing*, which reads as a broken surface rather than a moved route.
 */
export function apiEndpoint(name: string): string {
    const source = readFileSync(API_SERVICE_MODULE, 'utf-8');
    const match = source.match(new RegExp(`^\\s*${name}:\\s*'([^']*)'`, 'm'));
    if (!match) {
        throw new Error(`API_ENDPOINTS has no ${name} in apiService.tsx`);
    }
    return match[1];
}

/** The hidden route the presenter chord POSTs to, from the hook that POSTs. */
export function presenterAlertEndpoint(): string {
    const source = readFileSync(CHORD_HOOK, 'utf-8');
    const match = source.match(/PRESENTER_ALERT_ENDPOINT = '([^']*)'/);
    if (!match) {
        throw new Error('usePresenterChord.tsx no longer names its route');
    }
    return match[1];
}

export interface PresenterChord {
    /** How the presenter is told to press it, and nowhere on screen. */
    label: string;
    /** The same combination in Playwright's spelling. */
    press: string;
    /** The physical key, as `KeyboardEvent.code` reports it. */
    code: string;
    ctrlKey: boolean;
    altKey: boolean;
    shiftKey: boolean;
}

/** Playwright's names for the modifiers the presenter is told to hold. */
const MODIFIERS: Record<string, string> = {
    ctrl: 'Control',
    control: 'Control',
    alt: 'Alt',
    shift: 'Shift',
    meta: 'Meta',
    cmd: 'Meta',
};

/**
 * The hidden chord, read off the label the presenter is given.
 *
 * `PRESENTER_CHORD_LABEL` is the only statement of the chord anybody outside
 * the code ever sees — it is what the runbook prints and what the presenter
 * memorises — so it is the one thing a change to the chord cannot leave
 * behind. A beat with the combination typed into it goes red on a working
 * demonstration the day somebody moves the chord off a key a European layout
 * needed, which is the failure this whole suite exists not to produce.
 */
export function presenterChord(): PresenterChord {
    const source = readFileSync(CHORD_MODULE, 'utf-8');
    const match = source.match(/PRESENTER_CHORD_LABEL = '([^']*)'/);
    if (!match) {
        throw new Error('presenterChord.ts no longer labels its chord');
    }
    const label = match[1];
    const parts = label.split('+').map((part) => part.trim());
    const held = parts.slice(0, -1).map((part) => {
        const modifier = MODIFIERS[part.toLowerCase()];
        if (!modifier) {
            throw new Error(`${part} in ${label} is not a modifier key`);
        }
        return modifier;
    });
    const key = parts[parts.length - 1];
    // The chord is matched on `event.code`, not `event.key`, so a beat has to
    // press the *physical* key — with Alt held, several layouts compose a
    // different character and a beat pressing the character misses.
    const code = /^[A-Za-z]$/.test(key) ? `Key${key.toUpperCase()}` : key;
    return {
        label,
        press: [...held, code].join('+'),
        code,
        ctrlKey: held.includes('Control'),
        altKey: held.includes('Alt'),
        shiftKey: held.includes('Shift'),
    };
}

/**
 * What the chord's default alert says, from the server that says it.
 *
 * The words are the **server's** — chosen from a rehearsed roster, never
 * written by a model — so unlike every other reply in this walkthrough they can
 * be asserted. The `SOP-NNN` in them is the point of the beat: an alert that
 * names no procedure is a proactive message with nowhere to go.
 */
export function rehearsedAlert(): { title: string; docId: string } {
    const source = readFileSync(ALERT_ROSTER, 'utf-8');
    const defaultName = source.match(/DEFAULT_ALERT = "([^"]*)"/);
    if (!defaultName) {
        throw new Error('alert.py no longer names a default alert');
    }
    const entry = source.slice(
        source.indexOf(`"${defaultName[1]}": PresenterAlert(`),
    );
    const title = entry.match(/title="([^"]*)"/);
    const docId = entry.match(/SOP-\d+/);
    if (!title || !docId) {
        throw new Error(
            `the ${defaultName[1]} alert names no title or no procedure`,
        );
    }
    return { title: title[1], docId: docId[0] };
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

/** One `NAME = "value"` module constant out of a Python source file. */
function pythonString(source: string, name: string): string {
    const match = source.match(new RegExp(`^${name}\\s*=\\s*"([^"]*)"`, 'm'));
    if (!match) {
        throw new Error(`${name} is not a module constant in provenance.py`);
    }
    return match[1];
}
