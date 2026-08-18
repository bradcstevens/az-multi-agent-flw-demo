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
});
