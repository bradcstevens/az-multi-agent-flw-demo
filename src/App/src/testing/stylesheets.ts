import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';

import { STACKING_BREAKPOINT_QUERY } from '@/models/panelDrawer';

/**
 * Reading the surface's layout **out of its stylesheets**.
 *
 * The frontend loop runs in jsdom, which has no layout engine, so a rendered
 * width is not observable here. What is observable is the rule that produces it
 * — and the #58 finding is that a rule *listed* in a test agrees with itself
 * forever, while a rule *read out of the stylesheet* keeps agreeing with the
 * surface. Both of that ticket's escapes were columns nobody had thought to put
 * in a list.
 *
 * So these helpers parse the stylesheets and hand back every rule, and the
 * suites that use them ask questions of the whole set rather than of a name
 * they already knew.
 */

export interface Rule {
    /** Which stylesheet the rule was read out of, so a failure names a file. */
    file: string;
    selector: string;
    body: string;
}

export const SRC = join(__dirname, '..');
export const STYLES = join(SRC, 'styles');
export const SHELL_STYLESHEET = join(STYLES, 'storeSurface.css');
export const indexStylesheet = join(SRC, 'index.css');
export const RAIL_STYLESHEET = join(STYLES, 'transparency.css');
export const PLAN_PANEL_STYLESHEET = join(STYLES, 'planpanelright.css');
/**
 * The shared **Stacking breakpoint**, built from the one number that declares
 * it rather than restated here. `TransparencyRail.test` reads `storeSurface.css`
 * and fails if that number and the stylesheet's ever disagree — so a helper
 * that quoted its own copy would be a third owner of a number this repository
 * has already paid for owning twice (#58).
 */
export const STACKING_BREAKPOINT = `@media ${STACKING_BREAKPOINT_QUERY}`;

export const withoutComments = (css: string): string => css.replace(/\/\*[\s\S]*?\*\//g, '');

/**
 * The rules a media query can override — top level, at-rules skipped. Parsed
 * rather than matched on indentation, because indentation is not a contract.
 */
export const rulesIn = (css: string, file: string): Rule[] => {
    const source = withoutComments(css);
    const rules: Rule[] = [];
    let depth = 0;
    let selectorStart = 0;
    let bodyStart = 0;

    for (let i = 0; i < source.length; i += 1) {
        if (source[i] === '{') {
            depth += 1;
            if (depth === 1) bodyStart = i;
        } else if (source[i] === '}') {
            depth -= 1;
            if (depth === 0) {
                const selector = source.slice(selectorStart, bodyStart).trim();
                if (!selector.startsWith('@')) {
                    rules.push({ file, selector, body: source.slice(bodyStart + 1, i) });
                }
                selectorStart = i + 1;
            }
        }
    }

    return rules;
};

/** Every class named anywhere in a selector, not just the first one. */
export const classesIn = (selector: string): string[] =>
    Array.from(selector.matchAll(/\.([a-z0-9_-]+)/gi)).map((m) => m[1]);

/** The body of the shared stacking breakpoint, read from the shell's stylesheet. */
export const stackingBlock = (): string => {
    const css = withoutComments(readFileSync(SHELL_STYLESHEET, 'utf8'));
    const block = css.slice(css.indexOf(STACKING_BREAKPOINT));
    let depth = 0;
    for (let i = block.indexOf('{'); i < block.length; i += 1) {
        if (block[i] === '{') depth += 1;
        if (block[i] === '}') {
            depth -= 1;
            if (depth === 0) return block.slice(block.indexOf('{') + 1, i);
        }
    }
    return '';
};

/** The rules the stacking breakpoint declares. */
export const stackingRules = (): Rule[] => rulesIn(stackingBlock(), SHELL_STYLESHEET);

/** The class selectors inside the shared stacking breakpoint. */
export const stackingSelectors = (): string[] =>
    stackingRules().flatMap((rule) => classesIn(rule.selector));

/** What the stacking breakpoint declares for one class, across every rule naming it. */
export const stackedBody = (className: string): string =>
    stackingRules()
        .filter((rule) => classesIn(rule.selector).includes(className))
        .map((rule) => rule.body)
        .join('\n');

/**
 * Every source file under `src`, so a class can be looked for where it is
 * rendered. Test files and the test helpers beside this one are skipped: a
 * class name quoted in a test proves nothing about the surface.
 */
export const sourceFiles = (dir: string = SRC): string[] =>
    readdirSync(dir).flatMap((entry) => {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) {
            return path === __dirname ? [] : sourceFiles(path);
        }
        return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
    });

/**
 * The class tokens a source file actually renders — every whitespace-separated
 * word of every string literal in it. A substring search says `.left` is
 * rendered because some rule says `border-left`; a token search does not.
 */
export const classTokensIn = (source: string): Set<string> => {
    // Comments first: an apostrophe in prose ("the rail's width") would
    // otherwise open a string that swallows every class literal after it, and
    // the set would come back quietly short.
    const code = source.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/[^\n]*/g, ' ');
    const literals = Array.from(code.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)).map(
        (match) => match[1] ?? match[2] ?? match[3] ?? '',
    );
    return new Set(literals.flatMap((literal) => literal.split(/\s+/).filter(Boolean)));
};

/** Whether any component renders the class — a dead rule cannot mis-size anything. */
export const isRendered = (className: string): boolean =>
    sourceFiles().some((path) => readFileSync(path, 'utf8').includes(className));

/**
 * Every stylesheet the application **actually loads**, walked from the entry
 * point the browser starts at rather than listed or globbed.
 *
 * Three inventories have been wrong here in turn. `index.css` plus
 * `src/styles/*.css` missed `App.css`, which `App.tsx` imports from `src/` and
 * which holds a third copy of the chat list's row rules, so every rule in it
 * was invisible to every assertion in this file. Scanning *every* source file's
 * imports then over-corrected: `commonComponents/modules/Chat.tsx` and
 * `ChatExample.tsx` are imported by nothing, and they are the only importers of
 * the three stylesheets under `commonComponents/` — so dead files became
 * evidence, which is worse than missing evidence because it looks like proof.
 *
 * Reachability from `index.tsx` is the only definition that matches what the
 * browser loads, and it is derived, for #58's reason one level up: a *list* of
 * stylesheets agrees with itself forever, while an import graph keeps agreeing
 * with the application. A stylesheet is covered the moment something the entry
 * point can reach imports it, and never while nothing does.
 */
export const ENTRY_POINT = join(SRC, 'index.tsx');

const withoutAnyComments = (code: string): string =>
    code.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/\/\/[^\n]*/g, ' ');

/**
 * One import specifier, resolved the way the bundler resolves it. A bare
 * specifier is a package and stops the walk; `@/` is the alias `vite.config`
 * and `tsconfig` both point at `src`.
 */
const resolveImport = (from: string, specifier: string): string | null => {
    if (!specifier.startsWith('.') && !specifier.startsWith('@/')) return null;

    const base = specifier.startsWith('@/')
        ? join(SRC, specifier.slice(2))
        : resolve(dirname(from), specifier);

    const candidates = [
        base,
        `${base}.ts`,
        `${base}.tsx`,
        join(base, 'index.ts'),
        join(base, 'index.tsx'),
    ];

    return candidates.find((path) => existsSync(path) && statSync(path).isFile()) ?? null;
};

/**
 * The inventory, computed once per test process.
 *
 * Cached because it is read *per call*, and some suites call it per table cell:
 * the walk reads every reachable module and every stylesheet, so an uncached
 * inventory turned a cheap `readdir` into hundreds of file reads per suite. It
 * measurably starved the rest of the run — `index.test.tsx`'s bootstrap test,
 * which is already close to its 5s budget on this machine, went from failing
 * one full-suite run in four to three in four. Nothing writes a stylesheet
 * while a process is running, so the answer cannot go stale within one.
 */
let inventory: { file: string; path: string }[] | null = null;

export const loadedStylesheets = (): { file: string; path: string }[] => {
    if (inventory !== null) return inventory;

    const stylesheets = new Set<string>();
    const walked = new Set<string>();
    const queue = [ENTRY_POINT];

    while (queue.length > 0) {
        const module = queue.pop() as string;
        if (walked.has(module)) continue;
        walked.add(module);

        const code = withoutAnyComments(readFileSync(module, 'utf8'));
        /*
          Static, re-exported and dynamic alike: `import x from 'y'`, the
          side-effect `import 'y'` that loads every stylesheet here, and
          `await import('y')`.

          `export … from` is not optional. Half this application's modules are
          reached through a barrel — `pages/index.tsx`, `models/index.tsx`,
          `store/index.ts`, `api/index.tsx` — and a barrel re-exports rather
          than imports, so a walk that reads only `import` stops dead at the
          first one and reports two stylesheets for the whole surface.
        */
        for (const match of code.matchAll(/\b(?:import|export)\b[^'"();]*\(?\s*['"]([^'"]+)['"]/g)) {
            const resolved = resolveImport(module, match[1]);
            if (resolved === null) continue;
            if (resolved.endsWith('.css')) stylesheets.add(resolved);
            else if (/\.tsx?$/.test(resolved)) queue.push(resolved);
        }
    }

    inventory = Array.from(stylesheets)
        .sort()
        .map((path) => ({ file: relative(SRC, path), path }));

    return inventory;
};

/**
 * Every top-level rule in every stylesheet the surface loads.
 *
 * Reads the same inventory as `allRulesIncludingMediaQueries`, because two
 * answers to "which stylesheets are there" is two answers to every question
 * asked of them — the defect class this repository has already paid for with
 * widths (#58) and breakpoints (#66). The difference between the two readers is
 * what they read *inside* a stylesheet, and nothing else.
 *
 * Parsed once per process, for the reason the inventory is: these are called
 * inside loops over cells and rules, and re-parsing every stylesheet each time
 * is load the rest of the suite pays for in timeouts.
 */
let topLevelRules: Rule[] | null = null;

export const allRules = (): Rule[] =>
    (topLevelRules ??= loadedStylesheets().flatMap(({ file, path }) =>
        rulesIn(readFileSync(path, 'utf8'), file),
    ));

/** Every rule the stylesheets declare, inside media queries as well as out. */
let everyRule: Rule[] | null = null;

export const allRulesIncludingMediaQueries = (): Rule[] =>
    (everyRule ??= loadedStylesheets().flatMap(({ file, path }) => {
        const css = withoutComments(readFileSync(path, 'utf8'));
        // Media-query bodies are parsed as their own stylesheets, so a rule
        // inside one is read exactly like a rule outside one.
        const inner = Array.from(css.matchAll(/@media[^{]*\{/g)).flatMap((match) => {
            const open = (match.index ?? 0) + match[0].length - 1;
            let depth = 0;
            for (let i = open; i < css.length; i += 1) {
                if (css[i] === '{') depth += 1;
                if (css[i] === '}') {
                    depth -= 1;
                    if (depth === 0) return rulesIn(css.slice(open + 1, i), file);
                }
            }
            return [];
        });
        return [...rulesIn(css, file), ...inner];
    }));
