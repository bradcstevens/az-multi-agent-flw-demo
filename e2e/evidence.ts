import { appendFileSync, mkdirSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { BUILD_VERIFIED, DEPLOYED_BUILD } from './deployedBuild';

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
    /**
     * The commit the **deployment** was serving, as the gate dated it.
     *
     * The other half of the sentence above, and the one the rehearsal's proof
     * is actually about (#54). Null when nothing dated it.
     */
    deployedBuild: string | null;
    /**
     * Whether that dating actually happened on this run.
     *
     * The gate's own failure message ends by offering `E2E_SKIP_BUILD_CHECK`,
     * which is right for a presenter mid-demonstration and a lie in a
     * rehearsal's ledger: a run under that flag used to append a row
     * indistinguishable from a verified one, and ten of them printed *the beat
     * is proved*. `--target local` is the same hole through a different door.
     */
    buildVerified: boolean;
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
    row: Omit<Rehearsal, 'at' | 'commit' | 'deployedBuild' | 'buildVerified'>,
    ledger: string = LEDGER,
): void {
    try {
        mkdirSync(dirname(ledger), { recursive: true });
        const entry: Rehearsal = {
            at: new Date().toISOString(),
            commit: shortCommit(),
            // Read from the environment rather than taken as an argument,
            // because the spec has no way of knowing it: the gate runs in
            // `globalSetup`, in the main process, before this worker existed.
            // The spec would have to re-run `az` to answer, and a second
            // reading is a second thing that can disagree.
            deployedBuild: (process.env[DEPLOYED_BUILD] || '').trim() || null,
            buildVerified: Boolean(process.env[BUILD_VERIFIED]),
            ...row,
        };
        appendFileSync(ledger, `${JSON.stringify(entry)}\n`, 'utf-8');
    } catch (error) {
        console.warn(`the rehearsal evidence was not recorded: ${error}`);
    }
}
