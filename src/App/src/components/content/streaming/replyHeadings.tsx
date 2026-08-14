import React, { CSSProperties, createElement } from 'react';
import type { Components } from 'react-markdown';

/**
 * A reply's own Markdown headings, kept out of the surface's **heading
 * outline** (issue #57).
 *
 * The words in a reply come from a language model, and `react-markdown` renders
 * a `#` as a real `<h1>`. So a reply that happened to open with one put a
 * second top-level heading on the plan surface — above the very panels that
 * explain where that reply came from and what it cost. A screen-reader user
 * skimming by heading would meet the model's prose before **Grounding** and
 * **What this cost**, with nothing to tell the surface's structure apart from
 * the answer's.
 *
 * The outline is the surface's to declare. A `#` a model emitted is a
 * formatting choice, not a claim about this page — so the element keeps its
 * appearance and gives up its **semantics**: `role="presentation"` rather than
 * a different tag, so nothing at all changes on screen, and no styling has to
 * be restated here in order to strip a role.
 *
 * The alternative — demoting them below `SECTION_HEADING` — was rejected
 * because the conversation itself has no section heading to descend from, so
 * every reply heading would skip a level.
 */

type HeadingTag = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';

const HEADING_TAGS: HeadingTag[] = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];

/**
 * The heading overrides for one Markdown reply.
 *
 * Styling stays with the caller: the finalised reply sizes its own headings
 * and the streaming buffer does not, and unifying the two here would be a
 * visual change smuggled in behind an accessibility one.
 */
export const replyHeadings = (
    styles: Partial<Record<HeadingTag, CSSProperties>> = {},
): Components =>
    Object.fromEntries(
        HEADING_TAGS.map((tag) => [
            tag,
            ({ node: _node, ...props }: { node?: unknown } & React.HTMLAttributes<HTMLElement>) =>
                createElement(tag, {
                    style: styles[tag],
                    ...props,
                    // After the spread: a model's markup may not opt back in.
                    role: 'presentation',
                }),
        ]),
    ) as Components;
