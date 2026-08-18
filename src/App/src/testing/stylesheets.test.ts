import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import {
  allRulesIncludingMediaQueries,
  classesIn,
  indexStylesheet,
  loadedStylesheets,
} from "./stylesheets";

describe("conversation measure stylesheet seam", () => {
  it("reads the one winning 800px declaration from the loaded stylesheets", () => {
    const declarations = allRulesIncludingMediaQueries().filter((rule) =>
      /max-width:\s*800px/.test(rule.body),
    );
    const measureRules = allRulesIncludingMediaQueries().filter((rule) =>
      rule.selector.split(",").some((selector) => selector.trim() === ".conversation-measure"),
    );

    expect(declarations).toHaveLength(1);
    expect(measureRules).toHaveLength(1);
    expect(measureRules[0].body).toContain("max-width: 800px");
    expect(readFileSync(indexStylesheet, "utf8")).toContain(".conversation-measure");
  });
});

/**
 * What a stylesheet may not reach for (#59, #178).
 *
 * This lives here rather than in the suite of whichever component last got it
 * wrong, because it is a claim about the whole surface: #178 found the rule on
 * `.fui-AccordionPanel` in a stylesheet named after the chat list, where it
 * capped every accordion the application might ever render. The next one will
 * be written somewhere else, and a guard only the chat list's suite runs is a
 * guard only the chat list has to pass.
 */
describe("the surface's stylesheets", () => {
  it("are read from the entry point, so the evidence is what the browser loads", () => {
    const inventory = loadedStylesheets().map(({ file }) => file);

    // `App.tsx` imports this one from `src/`, and it was invisible to every
    // assertion in this file for as long as the inventory was a directory
    // listing of `src/styles`.
    expect(inventory).toContain("App.css");
    expect(inventory).toContain("index.css");
    expect(inventory).toContain("styles/storeSurface.css");

    /*
      And the reverse: `commonComponents/modules/Chat.tsx` and `ChatExample.tsx`
      are imported by nothing, and are the only importers of the stylesheets
      beside them. Reading every file's imports made dead files evidence, which
      is worse than missing evidence because it reads as proof.
    */
    expect(inventory).not.toContain("commonComponents/modules/Chat.css");
    expect(inventory).not.toContain("commonComponents/components/Content/Chat.css");
  });

  it("scope every Fluent class they style under a class of our own", () => {
    /*
      #59's finding, asserted rather than remembered: a class Fluent generates,
      "reached for from outside the component, kept winning with `!important`",
      "would have stopped matching without a word the day Fluent renamed it".

      What makes a rule a reach is that **no class of ours positively scopes
      it** — so `body .fui-AccordionPanel` is caught, while
      `.follow-on-task .fui-Button` is exactly how it should be done. A class
      inside a negation is not a scope: `.fui-Button:not(.ours)` styles every
      Fluent button on the surface *except* one, which is the reach with an
      exception clause, so negations are stripped before the question is asked.

      The property is deliberately not part of the question: the hazard is the
      reach itself, and a guard that only objected to heights would let the next
      one through on a different property. That breadth is wider than #178's own
      acceptance criterion and is tracked as its own decision in #181.
    */
    const rules = allRulesIncludingMediaQueries();

    const unscoped = rules.flatMap((rule) =>
      rule.selector
        .split(",")
        .map((selector) => selector.trim())
        .filter((selector) => {
          const scoping = classesIn(selector.replace(/:not\([^)]*\)/g, " "));
          return (
            scoping.length > 0 && scoping.every((className) => className.startsWith("fui-"))
          );
        })
        .map((selector) => `${rule.file}: ${selector}`),
    );

    expect(
      unscoped,
      `${unscoped.join(", ")} styles a Fluent class for the whole application`,
    ).toEqual([]);

    // And the scan reaches rules of this kind at all, rather than reporting a
    // clean surface because it is reading the wrong files.
    expect(
      rules.some((rule) =>
        classesIn(rule.selector).some((className) => className.startsWith("fui-")),
      ),
      "no loaded stylesheet mentions a Fluent class — the scan is looking in the wrong place",
    ).toBe(true);
  });
});
