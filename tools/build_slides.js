// 슬라이드 원본(JSON)으로 PPTX를 만든다.
//   - docs/발표자료/slides.json → 발표자료.pptx(발표자 노트 포함) + 발표대본.md
//   - docs/사용자가이드.slides.json → 사용자가이드.pptx
// 출력 파일 이름은 JSON의 "output"(없으면 발표자료.pptx), 노트가 있는 장이 있으면 대본도 만든다.
// PDF는 PowerPoint에서 「PDF로 저장」으로 만든다.
// 사용: npm install pptxgenjs@3.12.0 → node tools/build_slides.js [원본.json]
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const root = path.dirname(__dirname);
const src = path.resolve(process.argv[2] || path.join(root, "docs", "발표자료", "slides.json"));
const base = path.dirname(src);
const deck = JSON.parse(fs.readFileSync(src, "utf8"));
const outName = deck.output || "발표자료.pptx";

const FONT = "맑은 고딕";
const INK = "1B2A41", TEAL = "2A9D8F", TEAL_D = "1F776D", MIST = "EEF3F6", LINE = "CBD5DE", MUTED = "5B6B7C", WHITE = "FFFFFF", AMBER = "E9C46A";
const W = 13.333, M = 0.6;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = deck.title;
pres.author = "hwpx-template";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: WHITE },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.4, w: W - 2 * M, h: 0.9, fontFace: FONT, fontSize: 30, bold: true, color: INK, align: "left", valign: "middle", margin: 0 }, text: "" } },
    { text: { text: deck.title, options: { x: M, y: 7.0, w: 6, h: 0.3, fontFace: FONT, fontSize: 10, color: MUTED, margin: 0 } } },
  ],
  slideNumber: { x: W - M - 0.6, y: 7.0, w: 0.6, h: 0.3, fontFace: FONT, fontSize: 10, color: MUTED, align: "right" },
});
pres.defineSlideMaster({ title: "DARK", background: { color: INK }, objects: [] });

const txt = (s, text, o) => s.addText(text, Object.assign({ fontFace: FONT, isTextBox: true, margin: 0, valign: "top" }, o));
const badge = (s, label, x, y, d, fill, color) => {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill } });
  txt(s, label, { x, y, w: d, h: d, fontSize: d > 0.6 ? 20 : 14, bold: true, color, align: "center", valign: "middle" });
};
const foot = (s, text, y = 6.05) => {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: W - 2 * M, h: 0.7, fill: { color: MIST }, line: { color: MIST }, rectRadius: 0.08 });
  txt(s, text, { x: M + 0.3, y, w: W - 2 * M - 0.6, h: 0.7, fontSize: 15, color: INK, valign: "middle" });
};
const card = (s, x, y, w, h) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
  x, y, w, h, fill: { color: WHITE }, line: { color: LINE, width: 1 }, rectRadius: 0.1,
  shadow: { type: "outer", color: "000000", opacity: 0.12, blur: 6, offset: 2, angle: 90 },
});

const R = {
  cover(s, d) {
    s.addShape(pres.shapes.OVAL, { x: 8.9, y: -1.6, w: 6.2, h: 6.2, fill: { color: TEAL_D }, line: { color: TEAL_D } });
    s.addShape(pres.shapes.OVAL, { x: 10.6, y: 3.9, w: 3.6, h: 3.6, fill: { color: TEAL }, line: { color: TEAL } });
    txt(s, d.sub, { x: 0.9, y: 2.0, w: 8, h: 0.5, fontSize: 18, color: AMBER, bold: true });
    txt(s, d.title.replace(", ", ",\n"), { x: 0.9, y: 2.6, w: 7.9, h: 2.0, fontSize: 44, bold: true, color: WHITE });
    txt(s, deck.version, { x: 0.9, y: 5.6, w: 6, h: 0.4, fontSize: 14, color: "C9D4E2" });
  },
  flow3(s, d) {
    const cw = 3.5, gap = 0.75, y = 1.8, h = 3.7;
    d.items.forEach(([t, desc], i) => {
      const x = M + 0.35 + i * (cw + gap);
      card(s, x, y, cw, h);
      badge(s, String(i + 1), x + 0.35, y + 0.4, 0.75, i === 2 ? TEAL : INK, WHITE);
      txt(s, t, { x: x + 0.35, y: y + 1.4, w: cw - 0.7, h: 0.6, fontSize: 24, bold: true, color: INK });
      txt(s, desc, { x: x + 0.35, y: y + 2.1, w: cw - 0.7, h: 1.4, fontSize: 16, color: MUTED });
      if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + cw + 0.15, y: y + h / 2 - 0.25, w: 0.45, h: 0.5, fill: { color: TEAL }, line: { color: TEAL } });
    });
    foot(s, d.foot);
  },
  cards(s, d) {
    const n = d.items.length, cols = 3, rows = Math.ceil(n / cols), gap = 0.35;
    const cw = (W - 2 * M - gap * (cols - 1)) / cols, ch = rows === 2 ? 2.3 : 3.5, y0 = 1.65;
    d.items.forEach(([t, desc], i) => {
      const r = Math.floor(i / cols), c = i % cols;
      const inRow = Math.min(cols, n - r * cols);
      const off = (cols - inRow) * (cw + gap) / 2;
      const x = M + off + c * (cw + gap), y = y0 + r * (ch + gap);
      card(s, x, y, cw, ch);
      badge(s, String(i + 1), x + 0.3, y + 0.3, 0.55, TEAL, WHITE);
      txt(s, t, { x: x + 1.05, y: y + 0.3, w: cw - 1.3, h: 0.55, fontSize: 20, bold: true, color: INK, valign: "middle" });
      txt(s, desc, { x: x + 0.3, y: y + 1.05, w: cw - 0.6, h: ch - 1.25, fontSize: 16, color: MUTED });
    });
    if (d.foot) foot(s, d.foot);
  },
  table(s, d) {
    const head = d.head.map((h) => ({ text: h, options: { bold: true, color: WHITE, fill: { color: INK }, align: "center" } }));
    const two = d.head.length === 2;
    const rows = d.rows.map((r) => r.map((c, j) => ({ text: c, options: { align: j === 0 || two ? "left" : "center", bold: j === 0, color: INK } })));
    const rowH = d.rowH || (two ? 0.8 : 0.95);
    const first = (d.colW || [])[0] || (two ? 4.0 : 3.6);
    s.addTable([head, ...rows], {
      x: M, y: 1.7, w: W - 2 * M, colW: two ? [first, W - 2 * M - first] : [first, 1.6, 2.1, 2.9, W - 2 * M - first - 6.6],
      fontFace: FONT, fontSize: 16, rowH, valign: "middle", margin: [0.08, 0.15, 0.08, 0.15],
      border: { type: "solid", pt: 1, color: LINE }, fill: { color: WHITE },
    });
    if (d.foot) foot(s, d.foot, 1.7 + rowH * (d.rows.length + 1) + 0.45);
  },
  case1(s, d) {
    const lw = 4.3, gap = 0.4, rx = M + lw + gap, rw = W - M - rx, y = 1.6, h = 5.0;
    card(s, M, y, lw, h);
    [["상황", d.situation], ["첨부", d.attach]].forEach(([k, v], i) => {
      const yy = y + 0.35 + i * 1.55;
      txt(s, k, { x: M + 0.35, y: yy, w: lw - 0.7, h: 0.4, fontSize: 15, bold: true, color: TEAL_D });
      txt(s, v, { x: M + 0.35, y: yy + 0.45, w: lw - 0.7, h: 1.0, fontSize: 16, color: INK });
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 0.35, y: y + 3.5, w: 0.7, h: 0.45, fill: { color: AMBER }, line: { color: AMBER }, rectRadius: 0.06 });
    txt(s, "팁", { x: M + 0.35, y: y + 3.5, w: 0.7, h: 0.45, fontSize: 14, bold: true, color: INK, align: "center", valign: "middle" });
    txt(s, d.tip, { x: M + 0.35, y: y + 4.05, w: lw - 0.7, h: 0.85, fontSize: 14, color: MUTED });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: rx, y, w: rw, h, fill: { color: INK }, line: { color: INK }, rectRadius: 0.1 });
    txt(s, "이렇게 요청하세요", { x: rx + 0.4, y: y + 0.35, w: rw - 0.8, h: 0.4, fontSize: 15, bold: true, color: AMBER });
    txt(s, d.prompt, { x: rx + 0.4, y: y + 0.95, w: rw - 0.8, h: h - 1.3, fontSize: 18, color: "E6ECF4", paraSpaceAfter: 6 });
  },
  steps(s, d) {
    const n = d.items.length, gap = 0.3, cw = (W - 2 * M - gap * (n - 1)) / n, y = 1.75, h = 3.8;
    d.items.forEach(([t, desc], i) => {
      const x = M + i * (cw + gap);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h, fill: { color: i === n - 1 ? INK : MIST }, line: { color: i === n - 1 ? INK : MIST }, rectRadius: 0.1 });
      const dark = i === n - 1;
      badge(s, String(i + 1), x + 0.3, y + 0.35, 0.75, dark ? AMBER : TEAL, dark ? INK : WHITE);
      txt(s, t, { x: x + 0.3, y: y + 1.35, w: cw - 0.6, h: 0.6, fontSize: 22, bold: true, color: dark ? WHITE : INK });
      txt(s, desc, { x: x + 0.3, y: y + 2.05, w: cw - 0.6, h: 1.6, fontSize: 16, color: dark ? "D6DEE8" : MUTED });
    });
    foot(s, d.foot);
  },
  code(s, d) {
    const gap = 0.4, cw = (W - 2 * M - gap) / 2, y = 1.7, h = 3.9;
    d.blocks.forEach(([t, code], i) => {
      const x = M + i * (cw + gap);
      card(s, x, y, cw, h);
      badge(s, String(i + 1), x + 0.35, y + 0.35, 0.55, i === 0 ? TEAL : INK, WHITE);
      txt(s, t, { x: x + 1.1, y: y + 0.35, w: cw - 1.4, h: 0.55, fontSize: 20, bold: true, color: INK, valign: "middle" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.35, y: y + 1.25, w: cw - 0.7, h: 2.3, fill: { color: INK }, line: { color: INK }, rectRadius: 0.08 });
      txt(s, code, { x: x + 0.6, y: y + 1.45, w: cw - 1.2, h: 1.9, fontSize: 14, color: "E6ECF4", fontFace: "Consolas" });
    });
    foot(s, d.foot);
  },
  cases(s, d) {
    const gap = 0.4, cw = (W - 2 * M - gap) / 2, y = 1.6, h = 4.95;
    d.cases.forEach(([tag, attach, prompt, tip], i) => {
      const x = M + i * (cw + gap);
      card(s, x, y, cw, h);
      txt(s, tag, { x: x + 0.35, y: y + 0.3, w: cw - 0.7, h: 0.5, fontSize: 20, bold: true, color: TEAL_D });
      txt(s, attach, { x: x + 0.35, y: y + 0.85, w: cw - 0.7, h: 0.4, fontSize: 14, color: MUTED });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.35, y: y + 1.4, w: cw - 0.7, h: 2.2, fill: { color: INK }, line: { color: INK }, rectRadius: 0.08 });
      txt(s, prompt, { x: x + 0.6, y: y + 1.6, w: cw - 1.2, h: 1.9, fontSize: 17, color: "E6ECF4" });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.35, y: y + 3.95, w: 0.7, h: 0.45, fill: { color: AMBER }, line: { color: AMBER }, rectRadius: 0.06 });
      txt(s, "팁", { x: x + 0.35, y: y + 3.95, w: 0.7, h: 0.45, fontSize: 14, bold: true, color: INK, align: "center", valign: "middle" });
      txt(s, tip, { x: x + 1.2, y: y + 3.95, w: cw - 1.55, h: 0.8, fontSize: 15, color: INK });
    });
  },
  closing(s, d) {
    txt(s, d.title, { x: 0.9, y: 0.7, w: 11.5, h: 0.9, fontSize: 36, bold: true, color: WHITE });
    d.items.forEach(([t, desc], i) => {
      const y = 2.1 + i * 1.3;
      badge(s, String(i + 1), 0.9, y, 0.65, TEAL, WHITE);
      txt(s, t, { x: 1.8, y: y - 0.05, w: 5.5, h: 0.45, fontSize: 20, bold: true, color: WHITE });
      txt(s, desc, { x: 1.8, y: y + 0.42, w: 5.8, h: 0.7, fontSize: 15, color: "C9D4E2" });
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.9, y: 2.0, w: 4.8, h: 3.8, fill: { color: "24364F" }, line: { color: "24364F" }, rectRadius: 0.12 });
    d.links.forEach(([k, v], i) => {
      const y = 2.35 + i * 1.15;
      txt(s, k, { x: 8.25, y, w: 4.2, h: 0.4, fontSize: 14, color: AMBER, bold: true });
      txt(s, v, { x: 8.25, y: y + 0.4, w: 4.2, h: 0.5, fontSize: 15, color: WHITE });
    });
  },
};

const notes = [];
let n = 0;
for (const sec of deck.sections) {
  pres.addSection({ title: sec.title });
  for (const d of sec.slides) {
    n += 1;
    const dark = d.type === "cover" || d.type === "closing";
    const s = pres.addSlide({ masterName: dark ? "DARK" : "CONTENT", sectionTitle: sec.title });
    if (!dark) s.addText(d.title, { placeholder: "title" });
    R[d.type](s, d);
    if (d.notes) {
      s.addNotes(d.notes);
      notes.push(`## ${String(n).padStart(2, "0")}. ${d.title}\n\n${d.notes}\n`);
    }
  }
}

pres.writeFile({ fileName: path.join(base, outName) }).then(() => {
  if (notes.length) {
    fs.writeFileSync(path.join(base, "발표대본.md"), `# ${deck.title} — 발표 대본\n\n` + notes.join("\n"), "utf8");
  }
  console.log("written", outName, notes.length ? "+ 발표대본.md" : "", "|", n, "장");
});
