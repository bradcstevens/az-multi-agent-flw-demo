import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import CoralShellRow from './CoralShellRow';

const SRC = join(__dirname, '..', '..', '..');
const STYLESHEET = join(SRC, 'styles', 'storeSurface.css');
const RAIL_STYLESHEET = join(SRC, 'styles', 'transparency.css');

/** The class selectors inside the shared stacking breakpoint, read from the stylesheet. */
const stackingSelectors = (): string[] => {
    const css = readFileSync(STYLESHEET, 'utf8');
    const block = css.slice(css.indexOf('@media (max-width: 900px)'));
    let depth = 0;
    let end = 0;
    for (let i = block.indexOf('{'); i < block.length; i += 1) {
        if (block[i] === '{') depth += 1;
        if (block[i] === '}') {
            depth -= 1;
            if (depth === 0) {
                end = i;
                break;
            }
        }
    }
    return Array.from(block.slice(0, end).matchAll(/^\s{4}\.([a-z0-9_-]+)/gim)).map((m) => m[1]);
};

/** Every source file under `src`, so a class can be looked for where it is rendered. */
const sourceFiles = (dir: string): string[] =>
    readdirSync(dir).flatMap((entry) => {
        const path = join(dir, entry);
        if (statSync(path).isDirectory()) return sourceFiles(path);
        return /\.tsx?$/.test(path) && !/\.test\.tsx?$/.test(path) ? [path] : [];
    });

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
        const block = css.slice(css.indexOf('@media (max-width: 900px)'));

        expect(block).toMatch(/\.panel-left-container\s*\{\s*display:\s*none/);
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
