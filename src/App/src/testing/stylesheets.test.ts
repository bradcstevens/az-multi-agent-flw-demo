import { readFileSync } from "node:fs";
import { indexStylesheet } from "./stylesheets";

describe("conversation measure stylesheet seam", () => {
  it("declares the winning 800px measure once", () => {
    const css = readFileSync(indexStylesheet, "utf8");
    expect(css.match(/max-width:\s*800px/g)).toHaveLength(1);
    expect(css).toContain(".conversation-measure");
  });
});
