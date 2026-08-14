import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { resolveTarget } from './target';

/**
 * The **Demo validator**'s first assertion (issue #48, [ADR-018]).
 *
 * Every beat below this runs against whatever image the Container Apps happen
 * to be serving, and **Deployment drift** is silent by construction: the served
 * page changes only when the drift has already reached something visible, and
 * every other feedback loop in this repository runs against fakes. It cost a
 * day once. An integration branch was gated by this suite while the deployment
 * served `macaefrontend:a96b44815f80` — nine commits behind, predating the fix
 * being gated — and the beat that went red for the image reported
 * `toBeHidden() failed`, which is indistinguishable from a regression in the
 * code under review.
 *
 * So the build is dated **before** any beat runs, and the run stops if it is
 * not this commit. A suite that runs its beats and then explains itself in the
 * failure of one of them has already cost the reader the diagnosis.
 *
 * Three shapes were considered and two of them quietly delete the **Recorded
 * fallback** (#51):
 *
 * - **A spec** — ordered by filename, so "first" would rest on a leading `0`,
 *   and it drives no browser, so it produces a beat with no video. The
 *   walkthrough reporter refuses to record a run containing one.
 * - **A `setup` project the beats depend on** — genuinely first, and a second
 *   project. The reporter refuses a multi-project run, because both projects
 *   run every beat.
 * - **`globalSetup`** — first by construction, invisible to the reporter, and
 *   its failure aborts the run before a browser opens. This.
 *
 * The verdict itself is not computed here. `check-deployed-build.sh` owns it,
 * its decision logic is a pure importable module, and the CI-tooling loop
 * unit-tests that module without a tenant. A second implementation in
 * TypeScript is a second thing to disagree with it.
 *
 * [ADR-018]: ../docs/ADR/018-deployed-build-provenance-check.md
 */

const HERE = dirname(fileURLToPath(import.meta.url));

/** The preflight that owns the verdict. Named once, here. */
export const BUILD_CHECK = resolve(
    HERE,
    '..',
    'scripts/preflight/check-deployed-build.sh',
);

/**
 * The deliberate act that gets past a red build check.
 *
 * The **Stage driver** is what the presenter falls back to when clicking
 * through the walkthrough by hand goes wrong, and a refusal to start —
 * mid-demonstration, over a one-commit drift — is this check doing more harm
 * than the drift it found. So there is a way past, it is not a flag anybody
 * passes by accident, and it says out loud what it did not prove rather than
 * looking like a run that passed.
 */
export const SKIP = 'E2E_SKIP_BUILD_CHECK';

/**
 * What this run verified, published for the evidence ledger (#54).
 *
 * The gate dates the deployment and then, until this, kept the answer. The
 * **rehearsal** is a claim about ten consecutive runs of *one* build, so a run
 * that cannot name the build it observed cannot be part of one — and the gate
 * is the only thing in the suite that has asked.
 *
 * `process.env`, because `globalSetup` runs in the main process **before** any
 * worker is forked, so what it sets here is what the worker running the beat
 * inherits. `config.metadata` carries `target` and `baseURL` the same way and
 * would have been the tidier home, except that it is serialised from the
 * config at load time — which is before this function has run.
 */
export const DEPLOYED_BUILD = 'E2E_DEPLOYED_BUILD';
export const BUILD_VERIFIED = 'E2E_BUILD_VERIFIED';

/** What `check-deployed-build.sh --json` answers. */
interface BuildVerdict {
    ok: boolean;
    resourceGroup: string;
    deployedBuild: string | null;
    report: string;
}

/**
 * Read the preflight's verdict, or null when it did not produce one.
 *
 * Null is the honest answer for an `az` that failed, a login that expired or a
 * Python traceback — none of which is a verdict, and all of which used to be
 * indistinguishable from one because the report was prose either way.
 */
function readVerdict(stdout: string): BuildVerdict | null {
    try {
        const parsed = JSON.parse(stdout) as Partial<BuildVerdict>;
        if (typeof parsed?.report !== 'string') {
            return null;
        }
        return {
            ok: parsed.ok === true,
            resourceGroup: parsed.resourceGroup ?? '',
            deployedBuild: parsed.deployedBuild ?? null,
            report: parsed.report,
        };
    } catch {
        return null;
    }
}

/**
 * Record what was proved about the build, for whoever reads the ledger.
 *
 * Both variables are always written, including the negative case: an unset
 * variable left over from a previous process is exactly the state that would
 * make an unverified run look verified.
 */
function publish(verdict: BuildVerdict | null, verified: boolean): void {
    process.env[DEPLOYED_BUILD] = verified
        ? (verdict?.deployedBuild ?? '')
        : '';
    process.env[BUILD_VERIFIED] = verified ? '1' : '';
}

export default async function checkDeployedBuild(): Promise<void> {
    const target = resolveTarget();

    // `--target local` runs the same specs against a `npm run dev`. There is no
    // deployment to date, and a check that ran anyway would refuse every local
    // run for the wrong reason. It is still not a *verified* build — the
    // rehearsal says so out loud rather than counting the run.
    if (target.name === 'local') {
        publish(null, false);
        return;
    }

    const result = spawnSync('bash', [BUILD_CHECK, '--json'], {
        encoding: 'utf-8',
        stdio: ['ignore', 'pipe', 'pipe'],
    });
    // The rendered report travels inside the verdict, so the human text and
    // the commit come from one `az` read and `format_report` is never given a
    // second opinion in TypeScript.
    const verdict = readVerdict(result.stdout ?? '');
    const report =
        verdict?.report ??
        `${result.stdout ?? ''}${result.stderr ?? ''}`.trimEnd();

    // Read whether it passed *before* the opt-out, so a skipped run still
    // prints the verdict it is skipping.
    console.log(`\nDeployed build: ${verdict?.resourceGroup ?? ''}\n${report}\n`);

    if (process.env[SKIP]) {
        publish(verdict, false);
        console.log(
            `${SKIP} is set: the deployed build was NOT verified. Whatever ` +
                'the beats below report, they report it about an image this ' +
                'run did not date.\n',
        );
        return;
    }

    // Every non-zero exit stops the run, not only the drifted one. The check
    // exits 1 for "this is a different commit" and 3 for "nothing here could
    // say", and ADR-018 is explicit that treating the second as a pass
    // rebuilds the exact hole it closes.
    if (result.status !== 0) {
        publish(verdict, false);
        throw new Error(
            'The deployed build is not this commit, so no beat below would ' +
                'mean what it says.\n\n' +
                `${report}\n\n` +
                'Merge to `main` and let `Deploy main` run, or deploy by ' +
                'hand (docs/deploy-from-main.md), and re-run the validator. ' +
                `To go anyway — knowing the beats are about another build — ` +
                `set ${SKIP}=1.`,
        );
    }

    publish(verdict, true);
}
