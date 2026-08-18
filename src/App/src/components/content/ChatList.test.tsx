import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FluentProvider, teamsLightTheme } from '@fluentui/react-components';

import ChatList from './ChatList';
import { Chat } from '@/models';
import { allRulesIncludingMediaQueries } from '@/testing/stylesheets';
import { PlanStatus } from '../../models/enums';
import { NO_CHATS_MESSAGE, chatStateLabel } from '../../models/chatState';
import {
    CANCEL_DELETE_LABEL,
    CONFIRM_DELETE_LABEL,
    DELETE_CHAT_LABEL,
    DELETE_CHAT_WARNING,
    DELETE_FAILED_TITLE,
    END_AND_DELETE_LABEL,
    STILL_RUNNING_REASON,
    chatMenuLabel,
} from '../../models/chatDeletion';

const chat = (id: string, name: string, status: PlanStatus): Chat => ({
    id,
    planId: `${id}-latest`,
    name,
    status,
    date: '14 August 2026',
});

const completed = (id: string, name: string): Chat =>
    chat(id, name, PlanStatus.COMPLETED);

const MORNING = [
    completed('chat-1', 'How do I close the store?'),
    completed('chat-2', 'The register is frozen'),
];

const renderList = (chats: Chat[], props: Record<string, unknown> = {}) =>
    render(
        <FluentProvider theme={teamsLightTheme}>
            <ChatList
                chats={chats}
                onChatSelect={vi.fn()}
                onChatDelete={vi.fn()}
                {...props}
            />
        </FluentProvider>,
    );

/** Open a row's overflow menu the way a mouse does. */
const openMenuFor = (name: string) => {
    fireEvent.click(screen.getByRole('button', { name: chatMenuLabel(name) }));
};

const deleteItem = () => screen.getByRole('menuitem', { name: DELETE_CHAT_LABEL });

describe('the chat list', () => {
    it('shows the morning of rehearsals it has been given', () => {
        renderList(MORNING);

        expect(screen.getByText('How do I close the store?')).toBeInTheDocument();
        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
    });

    it('says so rather than opening onto blank space when there is nothing to show', () => {
        renderList([]);

        expect(screen.getByText(NO_CHATS_MESSAGE)).toBeInTheDocument();
    });

    it('offers no control that hides a chat instead of deleting it', () => {
        /*
          ADR-026 supersedes ADR-022: the hide is gone rather than standing
          beside the delete. Two controls, one of which quietly leaves the
          record behind, is the ambiguity the delete label exists to remove.

          The menu is opened before looking. A hide reintroduced where it would
          now naturally go — beside the delete, as a `MenuItem` — is invisible
          to a check that only reads the closed row. Found by review.
        */
        renderList(MORNING);
        openMenuFor('How do I close the store?');

        expect(screen.getByRole('menu')).toBeInTheDocument();
        expect(screen.getAllByRole('menuitem')).toHaveLength(1);
        expect(
            screen.queryByRole('menuitem', { name: /hide|archive/i }),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole('button', { name: /hide|archive/i }),
        ).not.toBeInTheDocument();
    });
});

describe('the row‘s overflow menu', () => {
    /*
      The inverted guard (#75). ADR-022 removed a `Menu` carrying a
      `MenuTrigger` and no `MenuPopover`, having measured that on
      `@fluentui/react-components` 9.64 such a menu renders *nothing* — the
      trigger never reaches the DOM, so no test, no screen reader and no click
      could see it. That is why the old check was a source read. The pattern is
      live now, so every assertion here is against the DOM instead: build the
      menu wrong and the panel ships an invisible delete with the suite green.
    */

    it('puts a trigger on the row that the DOM can actually see', () => {
        renderList(MORNING);

        expect(
            screen.getByRole('button', { name: chatMenuLabel('How do I close the store?') }),
        ).toBeInTheDocument();
    });

    it('names each row‘s menu after its own chat', () => {
        // One of these per row. A screen reader offered several identically
        // named buttons cannot say which conversation it is about to destroy.
        renderList(MORNING);

        expect(
            screen.getByRole('button', { name: chatMenuLabel('The register is frozen') }),
        ).toBeInTheDocument();
    });

    it('opens from the keyboard, not only from a mouse', () => {
        // ArrowDown is the menu's own keyboard opener. Enter and Space reach it
        // through the click a browser synthesises on a focused `button`, which
        // jsdom does not — so this asserts the path Fluent implements itself
        // rather than one this environment cannot produce.
        renderList(MORNING);

        const trigger = screen.getByRole('button', {
            name: chatMenuLabel('How do I close the store?'),
        });
        trigger.focus();
        fireEvent.keyDown(trigger, { key: 'ArrowDown' });

        expect(deleteItem()).toBeInTheDocument();
    });

    it('reaches a delete item through a popover that renders', () => {
        renderList(MORNING);

        openMenuFor('How do I close the store?');

        expect(deleteItem()).toBeInTheDocument();
    });

    it('does not open the chat when the menu is used', () => {
        // The trigger sits inside the row, and the row is itself a button.
        const onChatSelect = vi.fn();
        renderList(MORNING, { onChatSelect });

        openMenuFor('How do I close the store?');

        expect(onChatSelect).not.toHaveBeenCalled();
    });
});

describe('deleting one chat', () => {
    it('asks before it destroys anything', async () => {
        const onChatDelete = vi.fn();
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());

        expect(await screen.findByText(DELETE_CHAT_WARNING)).toBeInTheDocument();
        expect(onChatDelete).not.toHaveBeenCalled();
    });

    it('names the chat it is about to delete', async () => {
        // Two rows, one dialog. A confirmation that does not name the
        // conversation is a confirmation nobody can actually check.
        renderList(MORNING);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        const dialog = await screen.findByRole('dialog');
        expect(dialog).toHaveTextContent('The register is frozen');
    });

    it('deletes the chat the menu was opened on, once confirmed', async () => {
        const onChatDelete = vi.fn().mockResolvedValue(undefined);
        renderList(MORNING, { onChatDelete });

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        await waitFor(() =>
            expect(onChatDelete).toHaveBeenCalledWith(
                expect.objectContaining({ id: 'chat-2' }),
            ),
        );
    });

    it('destroys nothing when the confirmation is declined', async () => {
        const onChatDelete = vi.fn();
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CANCEL_DELETE_LABEL }),
        );

        await waitFor(() =>
            expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
        );
        expect(onChatDelete).not.toHaveBeenCalled();
    });

    it('leaves the confirmation open when the delete fails', async () => {
        // A dialog that closes on a rejected delete tells the associate the
        // chat is gone. It is still in Cosmos, and the row is about to come
        // back on the next load.
        const onChatDelete = vi.fn().mockRejectedValue(new Error('conflict'));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        await waitFor(() => expect(onChatDelete).toHaveBeenCalled());
        expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('says why the delete failed, where the associate is looking', async () => {
        /*
          Found by review. The panel holds a Fluent `useToastController`
          bound to a `Toaster` this application has never mounted, so a
          failure thrown to a toast is a failure nobody is told about — a
          confirmation that stays open with the button apparently doing
          nothing. The reason belongs in the dialog that is already on screen.
        */
        const onChatDelete = vi
            .fn()
            .mockRejectedValue(new Error(STILL_RUNNING_REASON));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );

        const said = await screen.findByRole('alert');
        expect(said).toHaveTextContent(DELETE_FAILED_TITLE);
        expect(said).toHaveTextContent(STILL_RUNNING_REASON);
    });

    it('forgets the failure when the confirmation is dismissed', async () => {
        // Otherwise the next chat's confirmation opens already carrying the
        // last one's error, which is the dialog reporting a delete that has
        // not been attempted.
        const onChatDelete = vi.fn().mockRejectedValue(new Error('conflict'));
        renderList(MORNING, { onChatDelete });

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: CONFIRM_DELETE_LABEL }),
        );
        await screen.findByRole('alert');
        fireEvent.click(screen.getByRole('button', { name: CANCEL_DELETE_LABEL }));

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        expect(await screen.findByRole('dialog')).toBeInTheDocument();
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
});

describe('a running chat is a door rather than a wall', () => {
    const RUNNING = chat('chat-running', 'The register is frozen', PlanStatus.IN_PROGRESS);

    it('offers the delete rather than refusing it', () => {
        // #122, ADR-031 §5. The turn a walk-away destroyed leaves a row at
        // `in_progress` for ever, and a refusal is the only thing the surface
        // ever said about it. The way out is to end the turn, never to loosen
        // the guard — so the control is offered and says what it will do.
        renderList([RUNNING]);

        openMenuFor('The register is frozen');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });

    it('says the turn ends first, in the words the route answers with', () => {
        renderList([RUNNING]);

        openMenuFor('The register is frozen');

        expect(screen.getByText(STILL_RUNNING_REASON)).toBeInTheDocument();
    });

    it('names the act on the button that performs it', async () => {
        // ADR-033's discipline at the confirmation: the associate is about to
        // end an answer in progress, so the button says so rather than
        // repeating the label of a delete that takes nothing else with it.
        renderList([RUNNING]);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        expect(
            await screen.findByRole('button', { name: END_AND_DELETE_LABEL }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole('button', { name: CONFIRM_DELETE_LABEL }),
        ).not.toBeInTheDocument();
    });

    it('states what is ended as well as what is destroyed', async () => {
        renderList([RUNNING]);

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());

        const confirmation = await screen.findByRole('dialog');
        expect(confirmation).toHaveTextContent(STILL_RUNNING_REASON);
        expect(confirmation).toHaveTextContent(DELETE_CHAT_WARNING);
    });

    it('deletes the chat the confirmation named', async () => {
        const onChatDelete = vi.fn().mockResolvedValue(undefined);
        renderList([RUNNING], { onChatDelete });

        openMenuFor('The register is frozen');
        fireEvent.click(deleteItem());
        fireEvent.click(
            await screen.findByRole('button', { name: END_AND_DELETE_LABEL }),
        );

        await waitFor(() => expect(onChatDelete).toHaveBeenCalledWith(RUNNING));
    });

    it('is the same door for a state no label can be read from', () => {
        // Fail-closed, still: a status this build does not know is a chat
        // something may still be happening to, so the way through it is the
        // one that ends a turn first rather than the one that assumes none.
        renderList([{ ...RUNNING, status: 'archived' as PlanStatus }]);

        openMenuFor('The register is frozen');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });

    it('says nothing about ending a turn for a chat that already settled', async () => {
        // The offer is about the turn in flight. Made over a finished chat it
        // would be the surface describing an act it is not performing.
        renderList(MORNING);

        openMenuFor('How do I close the store?');
        fireEvent.click(deleteItem());

        const confirmation = await screen.findByRole('dialog');
        expect(confirmation).not.toHaveTextContent(STILL_RUNNING_REASON);
        expect(
            screen.getByRole('button', { name: CONFIRM_DELETE_LABEL }),
        ).toBeInTheDocument();
    });
});

describe('the list holds chats in every state', () => {
    // #74. `GET /plans` filtered to `completed`, so the chat most worth
    // resuming — the one that did not finish — never reached this panel.
    const RUNNING = chat('chat-running', 'The register is frozen', PlanStatus.IN_PROGRESS);
    const FAILED = chat('chat-failed', 'How do I swap a shift?', PlanStatus.FAILED);
    const DONE = completed('chat-done', 'How do I close the store?');

    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('shows a chat that is still running', () => {
        renderList([RUNNING]);

        expect(screen.getByText('The register is frozen')).toBeInTheDocument();
    });

    it('shows a failed chat', () => {
        renderList([FAILED]);

        expect(screen.getByText('How do I swap a shift?')).toBeInTheDocument();
    });

    it('states each row‘s state, so a broken chat need not be opened to find out', () => {
        renderList([RUNNING, FAILED, DONE]);

        // Anchored: the row's accessible name begins with the chat's name,
        // while its menu trigger's is *"More options for …"*.
        const stateOf = (name: RegExp) =>
            screen.getByRole('button', { name }).textContent ?? '';

        expect(stateOf(/^The register is frozen/)).toContain(
            chatStateLabel(PlanStatus.IN_PROGRESS),
        );
        expect(stateOf(/^How do I swap a shift\?/)).toContain(
            chatStateLabel(PlanStatus.FAILED),
        );
        expect(stateOf(/^How do I close the store\?/)).toContain(
            chatStateLabel(PlanStatus.COMPLETED),
        );
    });

    it('lets the rehearsal debris go, which is why deletion followed #74', () => {
        renderList([FAILED]);

        openMenuFor('How do I swap a shift?');

        expect(deleteItem()).not.toHaveAttribute('aria-disabled', 'true');
    });
});

/**
 * How tall the list is allowed to be (#178).
 *
 * jsdom has no layout engine, so a hidden row is not observable here. What *is*
 * observable is the **computed style** of the rendered element, and that is
 * what this asks: the surface's own stylesheets are loaded into the document,
 * the list is rendered, and each container between the panel and a row is asked
 * what height and overflow it ended up with.
 *
 * Three earlier versions of this suite parsed the stylesheets by hand and each
 * review found another hole in the parser rather than in the surface —
 * `:is()`'s commas split into invalid fragments, `var()` indirection read as a
 * literal, a selector jsdom could not parse silently treated as no match, an
 * inline `maxBlockSize` unrecognised beside a `maxHeight` that was. Every one of
 * those is CSS the browser understands perfectly well, so the engine answers
 * instead: it resolves the cascade, specificity, `!important`, selector lists,
 * inline styles and logical properties, because that is its job.
 *
 * Media queries are the one thing jsdom does not evaluate, so the rules inside
 * them are flattened in — every rule the stylesheets declare is loaded, whatever
 * query it sits in. That is stricter than the browser and deliberately so:
 * below the **Stacking breakpoint** this panel is not rendered at all, so a
 * rule capping it there would be dead code claiming to be a layout.
 */
describe("the chat list's height", () => {
    /**
     * The elements between the panel's scroll region and a chat row, taken from
     * the DOM the component actually produces.
     *
     * Read rather than listed because the containers are not all ours: Fluent's
     * `Accordion`, `AccordionItem` and `AccordionPanel` sit between our
     * container and our rows, and it was `.fui-AccordionPanel` — a class no
     * source file in this repository contains — that carried the cap. A list
     * typed here would have to be updated by whoever renames it, which is
     * exactly the person who would not know to.
     */
    const listContainers = (): HTMLElement[] => {
        renderList(MORNING);

        const row = screen.getByRole('button', { name: /^How do I close the store\?/ });
        const containers: HTMLElement[] = [];

        for (
            let node = row.parentElement;
            node !== null;
            node = node.classList.contains('task-list-container') ? null : node.parentElement
        ) {
            containers.push(node);
        }

        return containers;
    };

    /** A rule worth loading: one that could bound a box or scroll it. */
    const SIZES_OR_SCROLLS =
        /(?:^|[;{\s])(?:(?:max-)?(?:height|block-size)|overflow(?:-y|-block)?)\s*:/i;

    /**
     * The surface's own rules, in the document, for the containers they apply
     * to — so the engine resolves them and this suite only has to read the
     * answer.
     *
     * Loaded one rule at a time rather than as one sheet, because jsdom rejects
     * a *stylesheet* wholesale when any rule in it defeats its parser: the whole
     * surface silently failed to load behind a green assertion the first time
     * this was written as a single `<style>`. One rule at a time, a rule it
     * cannot parse is one rule, and it is returned rather than swallowed.
     *
     * Only rules that **match one of the containers** are loaded. That keeps the
     * set small, and it keeps `Chat.css`'s nested `.messages` — the one rule in
     * 273 that jsdom cannot parse, and a conversation class that matches nothing
     * here — from being reported as a hole in a guard it has nothing to do with.
     */
    const loadRulesFor = (
        containers: HTMLElement[],
    ): { unload: () => void; unreadable: string[] } => {
        const applies = (selector: string): boolean => {
            try {
                // Selector lists are handed over whole: `matches` understands
                // `.a, .b`, and splitting on commas is what broke `:is(a, b)`.
                return containers.some((container) => container.matches(selector));
            } catch {
                // A selector this engine cannot parse cannot be ruled out.
                return true;
            }
        };

        const injected: HTMLStyleElement[] = [];
        const unreadable: string[] = [];

        for (const rule of allRulesIncludingMediaQueries()) {
            if (!SIZES_OR_SCROLLS.test(rule.body)) continue;
            if (!applies(rule.selector)) continue;

            const style = document.createElement('style');
            style.textContent = `${rule.selector}{${rule.body}}`;
            document.head.appendChild(style);
            injected.push(style);

            if (style.sheet === null || style.sheet.cssRules.length !== 1) {
                unreadable.push(`${rule.file}: ${rule.selector}`);
            }
        }

        return { unload: () => injected.forEach((style) => style.remove()), unreadable };
    };

    /*
      The computed properties that bound a box, and the ones that open a scroll
      region — physical and logical spellings alike, because an element can be
      given either and the engine reports what it was given.

      A cap is free only when it is absent or `none`: `max-height: 100%` bounds
      the list to the panel while the rows overflow it, which is this ticket's
      defect with a different number in it. A size is free when it is absent,
      `auto`, or filling its parent, which is how the panel's height reaches the
      list. Anything else — including a `var()` this engine does not resolve — is
      reported rather than assumed harmless.
    */
    const CAPS = ['maxHeight', 'maxBlockSize'] as const;
    const SIZES = ['height', 'blockSize'] as const;
    const SCROLLERS = ['overflow', 'overflowY', 'overflowBlock'] as const;

    const UNCAPPED = ['', 'none'];
    const FILLS_PARENT = ['', 'auto', '100%', 'inherit', 'initial', 'unset', 'revert'];

    /** What bounds this element, as the engine resolved it. */
    const bounds = (element: HTMLElement): string[] => {
        const computed = getComputedStyle(element);

        return [
            ...CAPS.filter((property) => !UNCAPPED.includes(computed[property])).map(
                (property) => `${property}: ${computed[property]}`,
            ),
            ...SIZES.filter((property) => !FILLS_PARENT.includes(computed[property])).map(
                (property) => `${property}: ${computed[property]}`,
            ),
        ];
    };

    /** What opens a scroll region inside this element. */
    const scrolls = (element: HTMLElement): string[] => {
        const computed = getComputedStyle(element);

        return SCROLLERS.filter((property) => /\b(auto|scroll)\b/.test(computed[property])).map(
            (property) => `${property}: ${computed[property]}`,
        );
    };

    const describeElement = (element: HTMLElement): string =>
        `${element.tagName.toLowerCase()}.${Array.from(element.classList).join('.')}`;

    it('is bounded by the panel it sits in, not by anything of its own', () => {
        /*
          The defect: `max-height: 280px` with its own `overflow-y: auto` put
          five rows on screen and the rest behind a scrollbar *inside* a panel
          that is already full height and already scrolls — #60's "content
          hidden behind a second scrollbar", in the column on the other edge.
        */
        const containers = listContainers();
        const { unload, unreadable } = loadRulesFor(containers);

        try {
            expect(
                unreadable,
                `${unreadable.join(', ')} applies to the chat list and could not be read`,
            ).toEqual([]);

            for (const container of containers) {
                expect(
                    bounds(container),
                    `${describeElement(container)} bounds the chat list's height`,
                ).toEqual([]);
                expect(
                    scrolls(container),
                    `${describeElement(container)} opens a scroll region inside the panel`,
                ).toEqual([]);
            }
        } finally {
            unload();
        }
    });

    it('would say so if the rule that caused this ticket came back', () => {
        /*
          The guard, proved rather than trusted. The assertion above is "no
          container is bounded", which is also what a guard that has stopped
          looking says — and it *had* stopped looking once already: loaded as
          one sheet, jsdom rejected the surface's whole stylesheet over one
          nested rule and every assertion passed against no styles at all.

          So the deleted rule goes back, exactly as it was written: on
          `.fui-AccordionPanel`, a class no source file here contains, with
          `!important` on both declarations.
        */
        const containers = listContainers();
        const { unload } = loadRulesFor(containers);

        const cap = document.createElement('style');
        cap.textContent =
            '.fui-AccordionPanel { max-height: 280px !important; overflow-y: auto !important; }';
        document.head.appendChild(cap);

        try {
            const panel = containers.find((element) =>
                element.classList.contains('fui-AccordionPanel'),
            );

            expect(
                panel,
                'the Fluent accordion panel is no longer a container of the rows',
            ).toBeDefined();
            expect(bounds(panel as HTMLElement)).toContain('maxHeight: 280px');
            expect(scrolls(panel as HTMLElement)).toContain('overflowY: auto');
        } finally {
            cap.remove();
            unload();
        }
    });

    it('reads the surface it thinks it is reading', () => {
        /*
          The other half of the proof, and the one the single-sheet version
          needed: that this loader really pulls rules out of the surface's own
          stylesheets and gets them applying, rather than quietly loading
          nothing and reporting a clean list.

          Proved with a rule that exists — `storeSurface.css` declares
          `overflow: hidden` on `.panelContent`, the panel's own scroll region —
          asked of a probe element carrying that class. A rule of the suite's
          own invention would only prove that jsdom applies stylesheets, which
          was never in doubt; this proves the path from the repository's CSS
          files to a computed value.
        */
        const containers = listContainers();
        const probe = document.createElement('div');
        probe.className = 'panelContent';
        document.body.appendChild(probe);

        const { unload } = loadRulesFor([...containers, probe]);

        try {
            const classes = containers.flatMap((element) => Array.from(element.classList));

            expect(classes).toContain('task-list-container');
            expect(
                classes.some((className) => /^fui-Accordion/.test(className)),
                'the Fluent accordion is no longer between the list and its rows',
            ).toBe(true);

            expect(
                getComputedStyle(probe).overflow,
                "the surface's own stylesheets are not reaching the rendered surface",
            ).toBe('hidden');
        } finally {
            unload();
            probe.remove();
        }
    });
    it('renders every chat it has been given, not a windowful', () => {
        /*
          The claim the panel makes, asserted where it can be. The cap was a
          stylesheet, so this passed while the surface hid nine of these — it
          stands as the guard for the day someone answers a long history by
          slicing the list in JavaScript instead.
        */
        const morning = Array.from({ length: 12 }, (_, i) =>
            completed(`chat-${i}`, `Rehearsal question ${i}`),
        );

        renderList(morning);

        for (const chat of morning) {
            expect(screen.getByText(chat.name)).toBeInTheDocument();
        }
    });

    it('still collapses when the heading is pressed', async () => {
        /*
          What the deleted rules were nominally for. `AccordionPanel` mounts
          through a `Collapse` motion with `unmountOnExit`, so a closed panel is
          not in the DOM at all and the `max-height: 0` pair was answering a
          state that cannot occur — but "dead rule" is a claim about behaviour,
          so it is asserted rather than reasoned about.
        */
        renderList(MORNING);

        const heading = screen.getByRole('button', { name: /^Chats/ });
        expect(heading).toHaveAttribute('aria-expanded', 'true');

        fireEvent.click(heading);

        expect(heading).toHaveAttribute('aria-expanded', 'false');
        await waitFor(() =>
            expect(screen.queryByText('How do I close the store?')).not.toBeInTheDocument(),
        );

        fireEvent.click(heading);

        expect(heading).toHaveAttribute('aria-expanded', 'true');
        expect(screen.getByText('How do I close the store?')).toBeInTheDocument();
    });
});
