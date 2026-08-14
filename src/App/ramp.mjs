// Generate a perceptually even brand ramp in OKLCH and validate it against the
// Fluent slots that actually carry text.
//
// Constraints discovered from Fluent's own alias mapping:
//   light: brand[80]  = button fill (white label) AND foreground on white   -> >=4.5:1 vs #fff
//   light: brand[70]  = link foreground on white                            -> >=4.5:1 vs #fff
//   dark:  brand[70]  = button fill (white label)                           -> >=4.5:1 vs #fff
//   dark:  brand[100] = foreground on the dark canvas                       -> >=4.5:1 vs #292929

const srgb = (c) => (c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055);
const lin = (c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));

function oklchToHex(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  let r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  let g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  let bl = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s;
  const clamp = (v) => Math.max(0, Math.min(1, v));
  [r, g, bl] = [clamp(r), clamp(g), clamp(bl)];
  const to255 = (v) => Math.round(clamp(srgb(v)) * 255);
  return '#' + [to255(r), to255(g), to255(bl)].map((v) => v.toString(16).padStart(2, '0')).join('');
}

const relLum = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16) / 255));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [x, y] = [relLum(a), relLum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

const HUE = Number(process.argv[2] ?? 196);
const CMAX = Number(process.argv[3] ?? 0.09);

// Lightness curve: dark at 10, near-white at 160. Chroma peaks mid-ramp and
// falls off at both ends so the palest tints stay neutral rather than candied.
const keys = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160];
const L = [0.20, 0.26, 0.32, 0.37, 0.42, 0.46, 0.50, 0.545, 0.60, 0.655, 0.71, 0.765, 0.82, 0.875, 0.925, 0.965];

function inGamut(L, C, h) {
  const hr = (h * Math.PI) / 180;
  const a = C * Math.cos(hr), b = C * Math.sin(hr);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  const r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s;
  const g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s;
  const bl = -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s;
  return [r, g, bl].every((v) => v >= -0.0005 && v <= 1.0005);
}

/** The largest chroma that still renders at this lightness and hue. */
function maxChroma(L, h) {
  let lo = 0, hi = 0.4;
  for (let i = 0; i < 40; i++) {
    const mid = (lo + hi) / 2;
    if (inGamut(L, mid, h)) lo = mid; else hi = mid;
  }
  return lo;
}

// Chroma per step, as a fraction of CMAX. Peaks at 80 — the step Fluent uses
// for the primary fill and the brand foreground, so it is the one that should
// carry the most colour — and tapers at both ends: the darkest steps go muddy
// with chroma in them, and the palest are surface tints, where anything
// stronger reads as candy rather than as a tinted white.
const CHROMA_SHAPE = [
  0.37, 0.53, 0.68, 0.79, 0.86, 0.93, 0.97, 1.0,
  0.97, 0.89, 0.79, 0.68, 0.58, 0.46, 0.34, 0.19,
];

const ramp = {};
keys.forEach((k, i) => {
  // Never ask for more colour than the lightness can actually hold. Clipping is
  // what turned the palest step into an electric cyan.
  const chroma = Math.min(CMAX * CHROMA_SHAPE[i], 0.9 * maxChroma(L[i], HUE));
  ramp[k] = oklchToHex(L[i], chroma, HUE);
});

console.log(`hue ${HUE}  chroma ${CMAX}\n`);
console.log(JSON.stringify(ramp, null, 2).replace(/"(\d+)":/g, '  $1:'));

const DARK_CANVAS = '#292929';
const checks = [
  ['light  brand[80] fill / white label ', contrast(ramp[80], '#ffffff')],
  ['light  brand[70] link on white      ', contrast(ramp[70], '#ffffff')],
  ['dark   brand[70] fill / white label ', contrast(ramp[70], '#ffffff')],
  ['dark   brand[100] text on #292929   ', contrast(ramp[100], DARK_CANVAS)],
  ['dark   brand[110] text on #292929   ', contrast(ramp[110], DARK_CANVAS)],
];
console.log('\ncontrast:');
for (const [name, v] of checks) {
  console.log(`  ${name} ${v.toFixed(2)}  ${v >= 4.5 ? 'PASS' : v >= 3 ? 'pass(non-text)' : 'FAIL'}`);
}
