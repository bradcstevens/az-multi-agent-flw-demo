import { appendFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * The **evidence ledger** for the rehearsed hit (issue #54).
 *
 * The centrepiece beat came back as the honest miss two runs in eight on the
 * afternoon this suite first ran, and the difference between the runs was the
 * question: `check-deployed-surface.sh` asks the SOP agent the corpus's own
 * words, while the orchestrator hands the tool whatever the model rephrased
 * them into. Which rephrasings arrive, and how often one of them misses, is a
 * claim about a **distribution** — and a distribution cannot be read off the
 * run in front of you.
 *
 * So every validator run appends one line here, passing runs included. The file
 * is append-only and lives under `artifacts/` with the videos and the traces,
 * because it is an observation of a deployment rather than something this
 * repository authored: a committed copy would be a measurement that stopped
 * being measured.
 *
 * `scripts/sop_rehearsal.py` reads it back — for the ten-consecutive-run proof
 * the issue asks for, and for the attribution, which is the part that must not
 * be guessed. A red run is attributed to the orchestrator's **routing** when no
 * tool call happened at all, to its **rephrasing** when the corpus was searched
 * for the model's own wording, and to the agent's **Dataverse index** when the
 * corpus's own wording was searched for and missed. Each has a different fix.
 */

const HERE = dirname(fileURLToPath(import.meta.url));

/** Beside the videos and the traces, and gitignored with them. */
export const LEDGER = resolve(HERE, 'artifacts/sop-evidence.jsonl');

/** What one run saw. Mirrored by `scripts/sop_rehearsal.py`. */
export type Outcome =
    | 'grounded'
    | 'honest-miss'
    | 'no-tool-call'
    | 'clarified'
    | 'unknown';

/** The two signals that separate the outcomes, plus the one that hides them. */
export interface Seen {
    grounded: boolean;
    honestMiss: boolean;
    clarified: boolean;
}

export interface Rehearsal {
    /** When the run ended. */
    at: string;
    /** `deployed` or `local`. */
    target: string;
    baseURL: string;
    /** The commit the **harness** ran from, which is not the deployed build. */
    commit: string | null;
    passed: boolean;
    outcome: Outcome;
    /** What the orchestrator handed `search_store_procedures`. */
    toolQuery: string | null;
    /** What the backend retrieved against, after its input alias. */
    retrievalQuery: string | null;
    /** The documents the answer came back with. */
    citations: string[];
    /**
     * Which agents the cost table billed. Not a pass/fail signal — the reason
     * it is here is that it separates two very different fixes (#54): whether
     * a green run is one where the troubleshooting specialist stayed out of
     * the turn, or one where it ran and lost the last word. Guessing between
     * those cost three deploys.
     */
    agentsBilled: string[];
}

function shortCommit(): string | null {
    try {
        return execFileSync('git', ['rev-parse', '--short', 'HEAD'], {
            cwd: HERE,
            encoding: 'utf-8',
            stdio: ['ignore', 'pipe', 'ignore'],
        }).trim();
    } catch {
        return null;
    }
}

/**
 * Which of the four things a run saw, from the two signals that distinguish
 * them.
 *
 * The distinction that matters is between an **honest miss** and **no tool
 * call**, because they implicate different layers and look alike from a
 * distance — both leave the beat red with no citation. The Grounding panel is
 * what tells them apart: it lights only when the backend pushed `source_used`,
 * which it does only when a Direct Line answer actually came back.
 *
 * `clarified` is checked **before** `grounded` is reported, because it is the
 * outcome that hides inside a success: the hop completed, the citation is on
 * screen, and the conversation still shows a question asked back at the
 * presenter. Reported as `grounded`, that run says the beat worked and the
 * harness is broken — which is what it looked like until this outcome existed.
 */
export function outcomeOf(seen: Seen): Outcome {
    if (!seen.grounded) {
        return 'no-tool-call';
    }
    if (seen.honestMiss) {
        return 'honest-miss';
    }
    return seen.clarified ? 'clarified' : 'grounded';
}

/**
 * Append one run's evidence.
 *
 * Never throws. This is an observation of the run, not part of it: a full disk
 * or a read-only checkout must not turn a working demonstration into a red
 * beat, which is the same rule `_push_source_used` follows on the backend.
 */
export function recordRehearsal(
    row: Omit<Rehearsal, 'at' | 'commit'>,
    ledger: string = LEDGER,
): void {
    try {
        mkdirSync(dirname(ledger), { recursive: true });
        const entry: Rehearsal = {
            at: new Date().toISOString(),
            commit: shortCommit(),
            ...row,
        };
        appendFileSync(ledger, `${JSON.stringify(entry)}\n`, 'utf-8');
    } catch (error) {
        console.warn(`the rehearsal evidence was not recorded: ${error}`);
    }
}
