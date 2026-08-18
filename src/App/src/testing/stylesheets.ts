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
 * Every stylesheet the application **actually loads**, derived from the imports
 * that load them rather than from a directory listing.
 *
 * The list used to be `index.css` plus `src/styles/*.css`, which is neither the
 * set the browser loads nor a superset of it. `App.tsx` imports `App.css` from
 * `src/`, so every rule in it was invisible to every assertion here — and what
 * it holds is a third copy of the chat list's row rules. Meanwhile three
 * stylesheets under `commonComponents/` are imported by nothing at all, so a
 * directory listing would have made dead files evidence.
 *
 * Derived, for #58's reason one level up: a *list* of stylesheets in a helper
 * agrees with itself forever, while an import is what actually loads one. A
 * stylesheet added tomorrow is covered the moment something imports it, and a
 * stylesheet nobody imports never is.
 */
export const loadedStylesheets = (): { file: string; path: string }[] => {
    const imported = new Set<string>();

    for (const source of sourceFiles()) {
        const code = readFileSync(source, 'utf8');
        for (const match of code.matchAll(/import\s+['"]([^'"]+\.css)['"]/g)) {
            const specifier = match[1];
            imported.add(
                specifier.startsWith('@/')
                    ? join(SRC, specifier.slice(2))
                    : resolve(dirname(source), specifier),
            );
        }
    }

    return Array.from(imported)
        .filter((path) => existsSync(path))
        .sort()
        .map((path) => ({ file: relative(SRC, path), path }));
};

/** Every top-level rule in every stylesheet the surface loads. */
export const allRules = (): Rule[] =>
    readdirSync(STYLES)
        .filter((entry) => entry.endsWith('.css'))
        .flatMap((entry) => rulesIn(readFileSync(join(STYLES, entry), 'utf8'), entry));

/** Every rule the stylesheets declare, inside media queries as well as out. */
export const allRulesIncludingMediaQueries = (): Rule[] =>
    loadedStylesheets().flatMap(({ file, path }) => {
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
    });
