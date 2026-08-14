import { execFileSync } from 'node:child_process';
import {
    copyFileSync,
    existsSync,
    mkdirSync,
    renameSync,
    rmSync,
    writeFileSync,
} from 'node:fs';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import type {
    FullConfig,
    FullResult,
    Reporter,
    Suite,
    TestCase,
    TestResult,
} from '@playwright/test/reporter';

/**
 * The **recorded fallback** (issue #51).
 *
 * The demonstration is being handed to a presenter who will be alone in the
 * room, whose primary access is a URL, and for whom "the Container App is cold"
 * is not a recoverable situation. A recording of the real system — produced by
 * the run that *proved* it works, not assembled afterwards by hand — is the
 * floor under that.
 *
 * Playwright already records a video per test under `artifacts/runs/`, in
 * directories named after a hash of the test's title. That is a debugging
 * artefact: nothing in it says which beat is which, what order they go in, or
 * whether the run they came from was any good. This reporter turns it into
 * something a presenter can open:
 *
 *   e2e/artifacts/walkthrough/
 *     walkthrough.html      the beats in order, one after another, in a browser
 *     walkthrough.json      what was recorded, from where, and when
 *     01-<beat>.webm        one video per beat, in the order they were run
 *
 * Three rules, each of them the point rather than an implementation detail:
 *
 * - **Only a run in which every beat passed replaces it.** A fallback made of a
 *   demonstration failing is worse than no fallback: the presenter finds out
 *   what is on it in front of the customer. A red run leaves the last good
 *   recording exactly where it was, and says so.
 * - **The beats are read off the run**, never from a list here. A roster in
 *   this file stops covering the beat added after it was written, and nothing
 *   goes red — the recording just quietly becomes partial.
 * - **A filtered or multi-project run does not qualify.** `--grep` and a shard
 *   run a subset by construction, and both projects run every beat twice; each
 *   would produce a recording that is not the walkthrough while looking exactly
 *   like one.
 */

const HERE = dirname(fileURLToPath(import.meta.url));

/** The predictable place. Written down once, here and in `docs/stage-driver.md`. */
export const WALKTHROUGH_DIR = resolve(HERE, '..', 'artifacts/walkthrough');

interface Beat {
    order: number;
    project: string;
    title: string;
    status: TestResult['status'];
    durationMs: number;
    video?: string;
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

function slugify(title: string): string {
    return (
        title
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '-')
            .replace(/^-+|-+$/g, '')
            .slice(0, 60) || 'beat'
    );
}

/**
 * A beat's name, as the presenter would say it: everything below the spec file,
 * so the `describe` and the test read as one line.
 *
 * Derived from the title path rather than indexed into it — the path's leading
 * entries are Playwright's (a nameless root suite, the project, the file), and
 * how many there are has changed between versions.
 */
function beatTitle(test: TestCase): string {
    const path = test.titlePath().filter(Boolean);
    const file = path.findIndex((part) => part.endsWith('.spec.ts'));
    return path.slice(file + 1).join(' — ') || test.title;
}

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

/**
 * The player.
 *
 * One file, no stylesheet, no script tag pointing anywhere, no dependency on
 * this repository or on Playwright's report viewer. Copy the directory onto a
 * memory stick and it opens on a machine that has never seen the project —
 * which is the situation it exists for.
 */
function playerHtml(beats: Beat[], meta: Record<string, unknown>): string {
    const recorded = beats.filter((beat) => beat.video);
    const playlist = recorded.map((beat) => ({
        file: beat.video,
        title: beat.title,
    }));
    const rows = recorded
        .map(
            (beat, index) => `
      <li data-index="${index}">
        <span class="n">${String(index + 1).padStart(2, '0')}</span>
        <span class="t">${escapeHtml(beat.title)}</span>
        <span class="d">${Math.round(beat.durationMs / 1000)}s</span>
      </li>`,
        )
        .join('');

    return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>The walkthrough — recorded ${escapeHtml(String(meta.recordedAt))}</title>
<style>
  :root { color-scheme: dark; }
  body { margin: 0; font: 15px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif;
         background: #16181d; color: #e8eaed; display: grid;
         grid-template-columns: minmax(280px, 22vw) 1fr; height: 100vh; }
  aside { border-right: 1px solid #2b2f37; padding: 20px; overflow-y: auto; }
  h1 { font-size: 15px; margin: 0 0 4px; letter-spacing: .02em; }
  p.meta { margin: 0 0 18px; font-size: 12px; color: #9aa0a6; }
  ol { list-style: none; margin: 0; padding: 0; }
  li { display: grid; grid-template-columns: 26px 1fr auto; gap: 8px; align-items: baseline;
       padding: 10px 8px; border-radius: 6px; cursor: pointer; }
  li:hover { background: #22262e; }
  li.playing { background: #1f3b2f; }
  .n { color: #6f7681; font-variant-numeric: tabular-nums; }
  .d { color: #6f7681; font-size: 12px; }
  main { display: grid; grid-template-rows: 1fr auto; min-width: 0; }
  video { width: 100%; height: 100%; object-fit: contain; background: #000; min-height: 0; }
  footer { padding: 10px 20px; font-size: 12px; color: #9aa0a6; border-top: 1px solid #2b2f37; }
</style>
</head>
<body>
<aside>
  <h1>The walkthrough</h1>
  <p class="meta">
    ${escapeHtml(String(meta.target))} &middot; ${escapeHtml(String(meta.baseURL))}<br />
    recorded ${escapeHtml(String(meta.recordedAt))}${
        meta.commit ? ` &middot; ${escapeHtml(String(meta.commit))}` : ''
    }<br />
    every beat passed on this run
  </p>
  <ol id="beats">${rows}</ol>
</aside>
<main>
  <video id="player" controls autoplay playsinline></video>
  <footer id="now"></footer>
</main>
<script>
  const beats = ${JSON.stringify(playlist, null, 2).replace(/</g, '\\u003c')};
  const player = document.getElementById('player');
  const items = [...document.querySelectorAll('#beats li')];
  const now = document.getElementById('now');
  let current = -1;

  function play(index) {
    if (index < 0 || index >= beats.length) return;
    current = index;
    player.src = beats[index].file;
    player.play().catch(() => {});
    items.forEach((li, i) => li.classList.toggle('playing', i === index));
    now.textContent = (index + 1) + ' of ' + beats.length + ' — ' + beats[index].title;
  }

  items.forEach((li, i) => li.addEventListener('click', () => play(i)));
  player.addEventListener('ended', () => play(current + 1));
  play(0);
</script>
</body>
</html>
`;
}

/**
 * Which command-line filter narrowed this run, or `null` if none did.
 *
 * Read from `process.argv` rather than from the config, because Playwright
 * applies `--grep` and positional filters to the *suite* and leaves
 * `FullConfig.grep` at its default — so a config-only check reports a run of
 * one beat out of four as the whole walkthrough. Verified against a real
 * filtered run rather than assumed.
 *
 * Every **positional** argument is a filter to `playwright test`: it is a
 * regular expression matched against the test file's path, so `cross-platform`
 * narrows the run exactly as `specs/cross-platform.spec.ts` does. They are
 * therefore found by elimination — skip the flags, skip the values the flags
 * consume, and whatever is left is a filter — rather than by recognising what a
 * spec filename looks like.
 *
 * The elimination is deliberately biased. An unknown flag that takes a value
 * leaves that value looking like a positional, and the consequence is a
 * *refusal* to replace the recording: the run is reported as filtered when it
 * was not. That is the direction to be wrong in — the other one silently
 * publishes half a walkthrough as the whole thing.
 */
export function filteredBy(argv: string[]): string | null {
    /** Filters that announce themselves. */
    const filterFlags = [
        '--grep',
        '-g',
        '--grep-invert',
        '--last-failed',
        '--only-changed',
        '--shard',
        '--repeat-each',
        '--test-list',
        '--test-list-invert',
    ];
    /** Everything else that swallows the argument after it. */
    const valued = [
        '--project',
        '-p',
        '--reporter',
        '--workers',
        '-j',
        '--timeout',
        '--global-timeout',
        '--output',
        '--retries',
        '--max-failures',
        '--config',
        '-c',
        '--trace',
        '--tsconfig',
        '--update-snapshots',
        '-u',
        '--debug',
    ];

    // Everything before the `test` command is node's and Playwright's own.
    const start = argv.indexOf('test');
    const args = start === -1 ? argv : argv.slice(start + 1);

    for (let index = 0; index < args.length; index += 1) {
        const arg = args[index];
        const named = arg.split('=')[0];

        if (filterFlags.includes(named)) {
            return arg;
        }
        if (valued.includes(named)) {
            if (!arg.includes('=')) {
                index += 1;
            }
            continue;
        }
        if (arg.startsWith('-')) {
            continue;
        }
        return arg;
    }
    return null;
}

export default class WalkthroughReporter implements Reporter {
    private beats: Beat[] = [];
    private config!: FullConfig;
    private order = 0;

    onBegin(config: FullConfig, _suite: Suite): void {
        this.config = config;
    }

    onTestEnd(test: TestCase, result: TestResult): void {
        // Read off the run. Whatever beats exist when this runs are the beats
        // the recording covers, including the ones added after this file.
        const video = result.attachments.find(
            (attachment) => attachment.name === 'video' && attachment.path,
        );
        this.beats.push({
            order: this.order++,
            project: test.parent.project()?.name ?? 'unknown',
            title: beatTitle(test),
            status: result.status,
            durationMs: result.duration,
            video: video?.path,
        });
    }

    async onEnd(result: FullResult): Promise<void> {
        const refusal = this.whyNotRecorded(result);
        if (refusal) {
            console.log(`\nWalkthrough recording not replaced: ${refusal}`);
            return;
        }

        const target = (this.config.metadata as Record<string, unknown>) ?? {};
        const meta = {
            recordedAt: new Date().toISOString().replace('T', ' ').slice(0, 16) + 'Z',
            commit: shortCommit(),
            target: target.target ?? 'unknown',
            baseURL: target.baseURL ?? 'unknown',
            project: this.beats[0]?.project ?? 'unknown',
            beats: this.beats.map((beat) => ({
                title: beat.title,
                status: beat.status,
                durationMs: beat.durationMs,
            })),
        };

        // Assembled beside the recording and swapped in at the end, never
        // written over it in place. A copy that throws half way through — a
        // video Playwright has not finished flushing, a full disk — would
        // otherwise have deleted a good fallback and left a partial one
        // wearing its name.
        //
        // The staging directory carries this run's pid, so two runs on one
        // machine cannot assemble into the same place; and the recording being
        // replaced is moved aside rather than deleted, then restored if the
        // swap fails. What must never happen is the state where there is no
        // fallback at all.
        const staging = `${WALKTHROUGH_DIR}.incoming.${process.pid}`;
        const displaced = `${WALKTHROUGH_DIR}.replaced.${process.pid}`;
        rmSync(staging, { recursive: true, force: true });
        mkdirSync(staging, { recursive: true });

        const recorded: Beat[] = this.beats.map((beat, index) => {
            if (!beat.video) {
                return beat;
            }
            const name = `${String(index + 1).padStart(2, '0')}-${slugify(
                beat.title,
            )}${extname(beat.video) || '.webm'}`;
            copyFileSync(beat.video, resolve(staging, name));
            return { ...beat, video: name };
        });

        writeFileSync(
            resolve(staging, 'walkthrough.json'),
            JSON.stringify({ ...meta, files: recorded.map((beat) => beat.video) }, null, 2),
            'utf-8',
        );
        writeFileSync(
            resolve(staging, 'walkthrough.html'),
            playerHtml(recorded, meta),
            'utf-8',
        );

        const hadOne = existsSync(WALKTHROUGH_DIR);
        if (hadOne) {
            renameSync(WALKTHROUGH_DIR, displaced);
        }
        try {
            renameSync(staging, WALKTHROUGH_DIR);
        } catch (error) {
            if (hadOne) {
                renameSync(displaced, WALKTHROUGH_DIR);
            }
            rmSync(staging, { recursive: true, force: true });
            throw error;
        }
        rmSync(displaced, { recursive: true, force: true });

        console.log(
            `\nWalkthrough recorded: ${recorded.length} beat(s) in ` +
                `${WALKTHROUGH_DIR}\n  open walkthrough.html — it plays without ` +
                'this repository.',
        );
    }

    /**
     * Why this run must not replace the fallback, or `null` if it may.
     *
     * Stated as refusals rather than as one condition because the presenter
     * reads the reason, and "3 of 4 beats" and "you passed --grep" are
     * different mornings.
     */
    private whyNotRecorded(result: FullResult): string | null {
        const bad = this.beats.filter((beat) => beat.status !== 'passed');
        if (result.status !== 'passed' || bad.length) {
            // `FullResult.status` is `passed` for a run whose beats were all
            // **skipped**, so the beats are counted rather than trusted to the
            // run's own verdict: a walkthrough nobody performed is not a
            // walkthrough that worked.
            return (
                `the run did not pass (${bad.length} of ${this.beats.length} ` +
                'beat(s) not green). The last good recording is untouched; this ' +
                "run's video is under artifacts/runs/ and in the HTML report."
            );
        }
        if (!this.beats.length) {
            return 'no beats ran.';
        }
        if (this.beats.some((beat) => !beat.video)) {
            return 'a beat produced no video; is `video` still on in playwright.config.ts?';
        }

        const projects = new Set(this.beats.map((beat) => beat.project));
        if (projects.size > 1) {
            return (
                `${projects.size} projects ran (${[...projects].join(', ')}), so ` +
                'every beat was recorded more than once. Choose one with ' +
                '`bash scripts/e2e-tests.sh` or `--stage`.'
            );
        }

        const grep = filteredBy(process.argv);
        if (grep) {
            return `the run was filtered (${grep}), so it cannot cover every beat.`;
        }
        if (this.config.shard) {
            return 'the run was sharded, so it cannot cover every beat.';
        }
        return null;
    }
}
