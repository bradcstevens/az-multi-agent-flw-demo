import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import CoralShellRow from './CoralShellRow';

const SRC = join(__dirname, '..', '..', '..');
const STYLES = join(SRC, 'styles');
const STYLESHEET = join(STYLES, 'storeSurface.css');
const RAIL_STYLESHEET = join(STYLES, 'transparency.css');
const STACKING_BREAKPOINT = '@media (max-width: 900px)';

interface Rule {
    /** Which stylesheet the rule was read out of, so a failure names a file. */
    file: string;
    selector: string;
    body: string;
}

const withoutComments = (css: string): string => css.replace(/\/\*[\s\S]*?\*\//g, '');

/**
 * The rules a media query can override — top level, at-rules skipped. Parsed
 * rather than matched on indentation, because indentation is not a contract.
 */
const rulesIn = (css: string, file: string): Rule[] => {
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
const classesIn = (selector: string): string[] =>
    Array.from(selector.matchAll(/\.([a-z0-9_-]+)/gi)).map((m) => m[1]);

/** The body of the shared stacking breakpoint, read from the shell's stylesheet. */
const stackingBlock = (): string => {
    const css = withoutComments(readFileSync(STYLESHEET, 'utf8'));
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
const stackingRules = (): Rule[] => rulesIn(stackingBlock(), STYLESHEET);

/** The class selectors inside the shared stacking breakpoint, read from the stylesheet. */
const stackingSelectors = (): string[] =>
    stackingRules().flatMap((rule) => classesIn(rule.selector));

/** Every source file under `src`, so a class can be looked for where it is rendered. */
const sourceFiles = (dir: string): string[] =>
    readdirSync(dir).flatMap((entry) => {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) return sourceFiles(path);
        return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
    });

/** Whether any component renders the class — a dead rule cannot mis-stack anything. */
const isRendered = (className: string): boolean => {
    const sources = sourceFiles(SRC).map((path) => readFileSync(path, 'utf8'));
    return sources.some((source) => source.includes(className));
};

/** Every top-level rule in every stylesheet the surface loads. */
const allRules = (): Rule[] =>
    readdirSync(STYLES)
        .filter((entry) => entry.endsWith('.css'))
        .flatMap((entry) => rulesIn(readFileSync(join(STYLES, entry), 'utf8'), entry));

/**
 * The rules that dress an element as a **side column**: a fixed pixel width and
 * a border down one side. Read out of the stylesheets rather than listed here,
 * because a list in a test agrees with itself forever — and the column this
 * missed the first time was the one that contains the rail rather than the rail.
 */
const sideColumns = (): { file: string; className: string }[] =>
    allRules()
        .filter(
            (rule) =>
                /(?:^|[;\s])width:\s*\d+px/.test(rule.body) &&
                /border-left:\s*\d/.test(rule.body),
        )
        .flatMap((rule) => classesIn(rule.selector).map((className) => ({ file: rule.file, className })))
        .filter(({ className }) => isRendered(className));

/** What the stacking breakpoint declares for one class, across every rule naming it. */
const stackedBody = (className: string): string =>
    stackingRules()
        .filter((rule) => classesIn(rule.selector).includes(className))
        .map((rule) => rule.body)
        .join('\n');

describe('the store surface on a phone-sized screen', () => {
    it('lets the shell stack, rather than pinning it to a row inline', () => {
        // The trap this exists for: an inline `display: flex; flex-direction:
        // row` beats a media query, so the phone stylesheet would be present,
        // correct and completely inert. The shell carries a class instead, and
        // its layout lives where a breakpoint can reach it.
        render(
            <CoralShellRow>
                <div>conversation</div>
            </CoralShellRow>,
        );

        const shell = screen.getByTestId('coral-shell-row');
        expect(shell).toHaveClass('coral-shell-row');
        expect(shell.style.display).toBe('');
        expect(shell.style.flexDirection).toBe('');
    });

    it('declares a shared stacking breakpoint at all', () => {
        expect(stackingSelectors().length).toBeGreaterThan(0);
    });

    it('targets only classes that something actually renders', () => {
        // Read out of the stylesheet rather than listed here, because a list in
        // a test agrees with itself forever. A class renamed in a component
        // while the breakpoint keeps the old name is a layout that silently
        // stops applying — and it would be discovered on a phone, on stage.
        const sources = sourceFiles(SRC).map((path) => readFileSync(path, 'utf8'));

        for (const selector of stackingSelectors()) {
            const rendered = sources.some((source) => source.includes(selector));
            expect(rendered, `no component renders .${selector}`).toBe(true);
        }
    });

    it('drops the task-history panel rather than squeezing it', () => {
        const css = readFileSync(STYLESHEET, 'utf8');
        const block = css.slice(css.indexOf(STACKING_BREAKPOINT));

        expect(block).toMatch(/\.panel-left-container\s*\{\s*display:\s*none/);
    });

    it('releases every side column when the shell stacks', () => {
        // A fixed width and a left border is what a column beside the
        // conversation looks like. Below the breakpoint there is nothing to its
        // left, so both are a lie: a 280px band with a left border, wearing the
        // dress of an orientation the shell is no longer in. The rail on the
        // plan surface is nested inside one of these, which is how it kept its
        // side-column width after the rail itself stopped keeping its own.
        const columns = sideColumns();
        expect(columns.length, 'no side columns found — the detector has stopped detecting').toBeGreaterThan(0);

        for (const { file, className } of columns) {
            const stacked = stackedBody(className);
            expect(
                stacked,
                `.${className} (${file}) is a side column the stacking breakpoint never names`,
            ).not.toBe('');

            if (/display:\s*none/.test(stacked)) continue;

            expect(
                /border-left:\s*none/.test(stacked),
                `.${className} (${file}) keeps a left border while stacked`,
            ).toBe(true);
            expect(
                /(?:^|[;\s])width:\s*100%/.test(stacked),
                `.${className} (${file}) keeps its side-column width while stacked`,
            ).toBe(true);
            expect(
                /box-sizing:\s*border-box/.test(stacked),
                `.${className} (${file}) is 100% wide plus its own padding, so it is wider than the surface it stacks into`,
            ).toBe(true);
        }
    });

    it('does not pin a stacked column to the viewport height', () => {
        // The stacked shell scrolls as one. A column still pinned to `100vh`
        // below the conversation is a viewport of furniture between the answer
        // and the panels that explain it.
        const pinned = allRules()
            .filter((rule) => /height:\s*100vh/.test(rule.body))
            .flatMap((rule) => classesIn(rule.selector).map((className) => ({ file: rule.file, className })))
            .filter(({ className }) => isRendered(className));

        for (const { file, className } of pinned) {
            const stacked = stackedBody(className);
            if (/display:\s*none/.test(stacked)) continue;

            expect(
                /height:\s*auto/.test(stacked),
                `.${className} (${file}) stays a viewport tall once the shell stacks`,
            ).toBe(true);
        }
    });

    it('declares the rail and shell stacking breakpoint once', () => {
        // The rail is beside the conversation until the shell stacks. Giving
        // it a second breakpoint creates a narrow side column styled as a
        // stacked band between the two widths.
        const shellCss = readFileSync(STYLESHEET, 'utf8');
        const railCss = readFileSync(RAIL_STYLESHEET, 'utf8');

        expect(shellCss).toMatch(
            /@media\s*\(max-width:\s*900px\)\s*\{[\s\S]*\.coral-shell-row[\s\S]*\.transparency-rail/,
        );
        expect(shellCss).toContain('.coral-shell-row .transparency-rail');
        expect(railCss).not.toContain('@media');
    });
});
