import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';

import CoralShellRow from './CoralShellRow';
import Content from '../Content/Content';
import {
    allRules,
    SRC,
    stackingBlock,
    classesIn,
    isRendered,
    RAIL_STYLESHEET,
    SHELL_STYLESHEET,
    sourceFiles,
    stackedBody,
    stackingRules,
    stackingSelectors,
    STACKING_BREAKPOINT,
} from '@/testing/stylesheets';

const STYLESHEET = SHELL_STYLESHEET;

/**
 * The rules that dress an element as a **side column**: a width it would not
 * have if it were a band, and a border down one side. Read out of the
 * stylesheets rather than listed here, because a list in a test agrees with
 * itself forever — and the column this missed the first time was the one that
 * contains the rail rather than the rail.
 *
 * A width is a column's width whenever it is not the band's own `100%`: a
 * length, or a content keyword like `min-content`, which is how the rail's
 * container sizes to the rail since #60.
 */
const BAND_WIDTHS = ['100%', 'auto', 'inherit', 'initial', 'unset'];

const declaresColumnWidth = (body: string): boolean =>
    Array.from(body.matchAll(/(?:^|[;{\s])width:([^;}]+)/g))
        .map((match) => match[1].trim())
        .some((value) => !BAND_WIDTHS.includes(value));

const sideColumns = (): { file: string; className: string }[] =>
    allRules()
        .filter((rule) => declaresColumnWidth(rule.body) && /border-left:\s*\d/.test(rule.body))
        .flatMap((rule) => classesIn(rule.selector).map((className) => ({ file: rule.file, className })))
        .filter(({ className }) => isRendered(className));

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

    it('lets the conversation stack too, rather than pinning it inline', () => {
        // The same trap as the shell's, one column over, and it made half of
        // #60's stacking fix inert: `.content` carried an inline `flex: 1`,
        // `height: 100%` and `min-width: 320px`, every one of which beats a
        // media query. So the breakpoint could say the stacked columns do not
        // shrink and the conversation would shrink anyway — and it is the
        // column the shell crushed first.
        render(
            <CoralShellRow>
                <Content>
                    <div>conversation</div>
                </Content>
            </CoralShellRow>,
        );

        const content = screen.getByTestId('coral-shell-row').querySelector('.content') as HTMLElement;
        expect(content, 'the conversation column is not rendered').not.toBeNull();
        expect(content.style.flex, 'an inline flex beats the breakpoint').toBe('');
        expect(content.style.height, 'an inline height beats the breakpoint').toBe('');
        expect(content.style.minWidth, 'an inline min-width beats the breakpoint').toBe('');
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

    it('does not leave chat history as a shell column', () => {
        const css = readFileSync(STYLESHEET, 'utf8');

        expect(css).not.toContain('.panel-left-container');
    });

    it('outranks every unconditional rule it has to overrule', () => {
        // The escape the assertion above cannot see, and the one that shipped
        // (#66): a breakpoint rule can be present, correct and still lose.
        //
        // A media query adds no specificity. So a single-class rule inside the
        // breakpoint ties with a single-class rule for the same property
        // outside it, and the tie goes to whichever stylesheet the bundler
        // imported second — which is decided by an import order in a component,
        // nowhere near either stylesheet. The chat-history Panel drawer is no
        // longer a shell column, while every remaining stacked rule must still
        // outrank the unconditional declaration it changes.
        //
        // Read out of the stylesheets rather than listed, for #58's reason: a
        // list agrees with itself forever.
        const unconditional = allRules();

        for (const stacked of stackingRules()) {
            const classes = classesIn(stacked.selector);
            // A selector naming more than one class already outranks any
            // single-class rule, which is how the rail's own width survives.
            if (classes.length > 1) continue;

            const properties = Array.from(
                stacked.body.matchAll(/(?:^|[;{\s])([a-z-]+)\s*:/g),
                (match) => match[1],
            );

            for (const className of classes) {
                for (const property of properties) {
                    const contested = unconditional.filter(
                        (rule) =>
                            classesIn(rule.selector).length === 1 &&
                            classesIn(rule.selector)[0] === className &&
                            new RegExp(`(?:^|[;{\\s])${property}\\s*:`).test(rule.body),
                    );

                    expect(
                        contested.map((rule) => rule.file),
                        `.${className} { ${property} } is declared unconditionally in ` +
                            `${contested.map((r) => r.file).join(', ')}, at the same ` +
                            `specificity as the stacking breakpoint — the breakpoint ` +
                            `only wins if that stylesheet happens to load first`,
                    ).toEqual([]);
                }
            }
        }
    });

    it('releases every side column when the shell stacks', () => {
        // A fixed width and a left border is what a column beside the
        // conversation looks like. Below the breakpoint there is nothing to its
        // left, so both are a lie: a 280px band with a left border, wearing the
        // dress of an orientation the shell is no longer in. The rail on the
        // chat surface is nested inside one of these, which is how it kept its
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

    it('lets the stacked shell scroll rather than crushing what it holds', () => {
        // Every column the shell stacks has a non-visible `overflow`, and a
        // flex item with one has an automatic minimum size of **zero**. So the
        // shell's `overflow-y: auto` was a promise it could never keep: its
        // children shrank to fit before it ever scrolled. Measured at 320px
        // before this landed — a 900px conversation rendered 17px tall, the
        // rail 32px around 189px of content, and the shell's scrollHeight
        // equalled its clientHeight. Nothing scrolled; everything was crushed.
        expect(
            stackingBlock(),
            "the stacked shell's children may still shrink, so it will crush them rather than scroll",
        ).toMatch(/\.coral-shell-row\s*>\s*\*[^{]*\{[^}]*flex-shrink:\s*0/);
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
