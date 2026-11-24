// Builds assets/banner.svg from assets/src/banner.src.svg, looking the same but far lighter
// to animate. The source draws its heavy parts from thousands of elements (the 0/1
// background field, the 0/1 portrait, the VANNI wordmark made of 1,144 glyph copies), and
// with the scan line and the reveal running non-stop, a browser redraws all of them on every
// frame: phones drop to a few fps. Here each heavy part is rendered once, in Chrome, at 2x,
// and put back as a picture; everything that moves still moves the same way:
//   - the background field's rows that flash: one small overlay per row, on its own delay
//   - the portrait: still revealed and wiped by the same animated mask; its bright rows that
//     flicker get an overlay
//   - the wordmark: still fades for the portrait; the glyphs that flash cream are overlays,
//     grouped by their delay (to the nearest 0.25s)
// It also bakes the contributions panel's two entities (assets/src/figures.src.svg, written by
// `python3 scripts/contrib.py --figures-src`) into assets/src/figures.json, which contrib.py
// embeds, so the GitHub Action keeps building the panel with plain Python.
// Usage: npm run bake  (uses your installed Google Chrome; `npm i` once first)
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright-core';

const ROOT = new URL('..', import.meta.url).pathname;
const SRC = `${ROOT}assets/src/banner.src.svg`;
const OUT = `${ROOT}assets/banner.svg`;
const W = 1280;
const H = 460;

const src = readFileSync(SRC, 'utf8');

// the element starting at `start` (an index of its "<tag"), through its matching close tag
function element(s, start) {
  const tag = s.slice(start + 1).match(/^[a-zA-Z]+/)[0];
  const re = new RegExp(`<(/?)${tag}\\b[^>]*?(/?)>`, 'g');
  re.lastIndex = start;
  let depth = 0;
  let m;
  while ((m = re.exec(s))) {
    if (m[1]) depth--;
    else if (!m[2]) depth++;
    if (depth === 0) return s.slice(start, re.lastIndex);
  }
  throw new Error(`no end for <${tag}> at ${start}`);
}
const find = (s, open) => {
  const i = s.indexOf(open);
  if (i < 0) throw new Error(`not found: ${open}`);
  return element(s, i);
};

const style = find(src, '<style>');
const defs = find(src, '<defs>');
const bgf = find(src, '<g class="bgf"');
const face = find(src, '<g class="face"');
const lg = find(src, '<svg class="lg"');
// the face's mask is defined in the body, not in <defs>
const faceMask = find(src, '<mask id="fmk"');

// a standalone picture of one layer, animations off (every flash at rest)
const still = style.replace('</style>', '*{animation:none!important}</style>');
const doc = (body) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${still}${defs}<g id="bake">${body}</g></svg>`;

const layers = [];
// scale: pixels per unit; opaque: drawn on black as a jpeg (the background, nothing under it)
const add = (name, body, place, opts = {}) => layers.push({ name, svg: doc(body), place, scale: 2, ...opts });

/* the background field, and its flashing rows */
// the background field is nearly black, at the very bottom: 1x, flat on black, is plenty
add('bgf', `<rect width="${W}" height="${H}" fill="#000"/>${bgf}`, null, { scale: 1, opaque: true });
const rowRe = /<text[^>]*class="b"[^>]*>[^<]*<\/text>/g;
const bRows = bgf.match(rowRe) || [];
const bgfOpen = bgf.slice(0, bgf.indexOf('>') + 1);
bRows.forEach((row, i) => {
  const delay = row.match(/animation-delay:([\d.]+)s/)?.[1] ?? '0';
  const lit = row.replace(/ class="b"/, '').replace(/ style="[^"]*"/, ' style="fill:#3a1e08"');
  add(`b${i}`, `${bgfOpen}${lit}</g>`, { cls: 'bo', delay }, { scale: 1 });
});

/* the portrait (unmasked: the mask stays live in the final file), and its flickering rows */
const faceOpen = face.slice(0, face.indexOf('>') + 1);
add('face', face.replace(' mask="url(#fmk)"', ''));
const fhRows = face.match(/<text[^>]*class="fh"[^>]*>[^<]*<\/text>/g) || [];
add(
  'fh',
  faceOpen.replace(' mask="url(#fmk)"', '') +
    fhRows.map((r) => r.replace(/ class="fh"/, '').replace(/ fill="[^"]*"/, ' fill="#FFF1C2"')).join('') +
    '</g>'
);

/* the wordmark, and its glyphs that flash cream, grouped by delay */
const lgPlain = lg.replace(' class="lg"', '');
add('lg', lgPlain);
const hUses = lg.match(/<use class="h"[^>]*\/>/g) || [];
const buckets = new Map();
for (const u of hUses) {
  const d = (Math.round(parseFloat(u.match(/animation-delay:([\d.]+)s/)?.[1] ?? '0') * 4) / 4).toFixed(2);
  if (!buckets.has(d)) buckets.set(d, []);
  buckets.get(d).push(u.replace(/ class="h"/, '').replace(/ style="[^"]*"/, ''));
}
// keep the wordmark's own box, clip and defs, but only these glyphs, in cream
const lgHead = lg.slice(0, lg.indexOf('<g clip-path'));
const lgClipOpen = lg.slice(lg.indexOf('<g clip-path'), lg.indexOf('>', lg.indexOf('<g clip-path')) + 1);
for (const [d, uses] of buckets) {
  add(`h${d}`, `${lgHead.replace(' class="lg"', '')}${lgClipOpen}<g fill="#FFF1C2">${uses.join('')}</g></g></svg>`, { cls: 'ho', delay: d });
}

/* render */
const browser = await chromium.launch({ channel: 'chrome' });
const pages = {};
for (const l of layers) {
  pages[l.scale] ??= await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: l.scale });
  const page = pages[l.scale];
  await page.setContent(`<!doctype html><style>html,body{margin:0;background:transparent}svg{display:block}</style>${l.svg}`);
  const box = await page.evaluate(() => {
    // the union of what's actually drawn (not the wordmark's whole box, or the masks' rects)
    const leaves = [...document.querySelectorAll('#bake text, #bake use, #bake path, #bake rect')].filter(
      (el) => !el.closest('defs, clipPath, mask')
    );
    const r = leaves.map((el) => el.getBoundingClientRect()).filter((q) => q.width && q.height);
    const b = {
      x: Math.min(...r.map((q) => q.x)),
      y: Math.min(...r.map((q) => q.y)),
      right: Math.max(...r.map((q) => q.right)),
      bottom: Math.max(...r.map((q) => q.bottom)),
    };
    const x = Math.max(0, Math.floor(b.x - 2));
    const y = Math.max(0, Math.floor(b.y - 2));
    return { x, y, width: Math.min(1280, Math.ceil(b.right + 2)) - x, height: Math.min(460, Math.ceil(b.bottom + 2)) - y };
  });
  const buf = l.opaque
    ? await page.screenshot({ clip: { x: 0, y: 0, width: W, height: H }, type: 'jpeg', quality: 72 })
    : await page.screenshot({ clip: box, omitBackground: true, type: 'webp', quality: 90 });
  if (l.opaque) Object.assign(box, { x: 0, y: 0, width: W, height: H });
  l.box = box;
  l.kb = buf.length / 1024;
  l.href = `data:image/${l.opaque ? 'jpeg' : 'webp'};base64,${buf.toString('base64')}`;
}

/* the contributions panel's two entities: each piece of the sheet contrib.py writes, as a
   picture in the piece's own coordinates (they sit at 300,300 on the sheet) */
const FIG_SRC = `${ROOT}assets/src/figures.src.svg`;
if (existsSync(FIG_SRC)) {
  const sheet = readFileSync(FIG_SRC, 'utf8');
  const ids = [...sheet.matchAll(/<g id="([^"]+)"/g)].map((m) => m[1]);
  const page = await browser.newPage({ viewport: { width: 600, height: 700 }, deviceScaleFactor: 2 });
  const out = {};
  for (const id of ids) {
    await page.setContent(`<!doctype html><style>html,body{margin:0;background:transparent}svg{display:block}g[id]{display:none}#${id}{display:inline}</style>${sheet}`);
    const box = await page.evaluate((id) => {
      const b = document.getElementById(id).getBoundingClientRect();
      const x = Math.floor(b.x - 1);
      const y = Math.floor(b.y - 1);
      return { x, y, width: Math.ceil(b.right + 1) - x, height: Math.ceil(b.bottom + 1) - y };
    }, id);
    const buf = await page.screenshot({ clip: box, omitBackground: true, type: 'webp', quality: 88 });
    out[id] = { x: box.x - 300, y: box.y - 300, w: box.width, h: box.height, href: `data:image/webp;base64,${buf.toString('base64')}` };
  }
  writeFileSync(`${ROOT}assets/src/figures.json`, JSON.stringify(out));
  console.log(`figures.json: ${ids.length} pieces, ${(JSON.stringify(out).length / 1024).toFixed(0)} KB`);
}

await browser.close();

/* assemble */
const img = (l, extra = '') =>
  `<image${extra} x="${l.box.x}" y="${l.box.y}" width="${l.box.width}" height="${l.box.height}" href="${l.href}"/>`;
const by = (name) => layers.find((l) => l.name === name);
const overlays = (cls) =>
  layers
    .filter((l) => l.place?.cls === cls)
    .map((l) => img(l, ` class="${cls}" opacity="0" style="animation-delay:${l.place.delay}s"`))
    .join('');

let out = src;
out = out.replace(bgf, `${img(by('bgf'))}${overlays('bo')}`);
out = out.replace(face, `<g mask="url(#fmk)">${img(by('face'))}${img(by('fh'), ' class="fho" opacity="0"')}</g>`);
out = out.replace(lg, `<g class="lg">${img(by('lg'))}${overlays('ho')}</g>`);
// the overlays take over the old fill flashes: same timing, shown and hidden by opacity
out = out.replace(
  '</style>',
  [
    '.bo{animation:bo 6s steps(1) infinite}@keyframes bo{0%,100%{opacity:0}48%{opacity:1}52%{opacity:0}}',
    '.fho{animation:fho 2.2s steps(1) infinite}@keyframes fho{0%,100%{opacity:0}40%{opacity:1}46%{opacity:0}}',
    '.ho{animation:ho 4s steps(1) infinite}@keyframes ho{0%,100%{opacity:0}10%{opacity:1}14%{opacity:0}60%{opacity:1}62%{opacity:0}}',
    '</style>',
  ].join('\n')
);
if (!out.includes(faceMask)) throw new Error('the face mask went missing');
writeFileSync(OUT, out);
for (const l of layers) if (l.kb > 20) console.log(`  ${l.name}: ${l.kb.toFixed(0)} KB, ${l.box.width}x${l.box.height}`);
console.log(`banner.svg: ${layers.length} layers baked, ${(out.length / 1024).toFixed(0)} KB (source ${(src.length / 1024).toFixed(0)} KB)`);
