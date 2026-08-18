import { readFileSync } from "node:fs";
import { allRulesIncludingMediaQueries, indexStylesheet } from "./stylesheets";

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

  it("centres the measure in whatever width the side columns leave it (#168)", () => {
    /*
      A measure is a cap on the line, not an instruction to hug the left edge.
      Capped and unmargined, the transcript rendered in the left 800px of a
      1600px column and the remaining 800px was empty background between the
      answer and the rail that explains it — read from a projector, the gutter
      is the widest thing on the surface.

      `margin-inline`, not `margin`, because the vertical margins here belong
      to the components that stack these blocks; the one thing this rule owns
      is the horizontal placement of the column it caps.
    */
    const [measure] = allRulesIncludingMediaQueries().filter((rule) =>
      rule.selector.split(",").some((selector) => selector.trim() === ".conversation-measure"),
    );

    expect(measure.body).toMatch(/margin-inline:\s*auto/);
    expect(measure.body).not.toMatch(/(?:^|[;{\s])margin:/);
  });
});
