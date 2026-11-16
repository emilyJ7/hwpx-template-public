// 사용자 가이드 원고(md)로 PDF를 만든다(한글 없이 쓰는 대체 방법).
//   한글이 있는 Windows에서는 md2hwpx.py --pdf 또는 한글 「PDF로 저장」으로 만든 PDF가 더 정확하다.
// 사용: npm install pptxgenjs@3.12.0 marked@12.0.2 → node tools/build_guide_pdf.js [원고.md] [출력.pdf]
// 글꼴: 맑은 고딕(없으면 나눔고딕)
const fs = require("fs");
const path = require("path");
const { marked } = require("marked");

const root = path.dirname(__dirname);
const src = path.resolve(process.argv[2] || path.join(root, "docs", "사용자가이드.md"));
const out = path.resolve(process.argv[3] || src.replace(/\.md$/, ".pdf"));

let md = fs.readFileSync(src, "utf8");
let header = "";
md = md.replace(/^---\n([\s\S]*?)\n---\n/, (_, fm) => {
  const m = fm.match(/^header:\s*(.+)$/m);
  if (m) header = m[1].trim();
  return "";
});
// ![캡션](그림.png){width=80%} → 그림 + 캡션
md = md.replace(/!\[([^\]]*)\]\(([^)]+)\)(\{width=(\d+)%\})?/g, (_, alt, p, __, w) => {
  const abs = path.resolve(path.dirname(src), p);
  const data = fs.readFileSync(abs).toString("base64");
  return `<figure style="width:${w || 80}%"><img src="data:image/png;base64,${data}"><figcaption>${alt}</figcaption></figure>`;
});

const body = marked.parse(md);
const html = `<!doctype html><html lang="ko"><meta charset="utf-8"><style>
@page{size:A4;margin:20mm 18mm 18mm}
body{font-family:"Malgun Gothic","맑은 고딕","NanumGothic",sans-serif;font-size:10.5pt;line-height:1.6;color:#111}
h1{font-size:19pt;text-align:center;border:2px solid #1B2A41;border-radius:6px;padding:10px;margin:0 0 6px}
h1+p{text-align:right;color:#444;margin-top:4px}
h2{font-size:14pt;margin:22px 0 8px;break-after:avoid}
h2::before{content:"□ "}
h3{font-size:11.5pt;margin:14px 0 6px;color:#1F3A5F;break-after:avoid}
ul{list-style:none;padding-left:1.2em;margin:4px 0}
ul>li{position:relative}
ul>li::before{content:"○";position:absolute;left:-1.2em}
ul ul>li::before{content:"-"}
blockquote{margin:10px 0;padding:8px 12px;border:1px solid #888;background:#F4F6F8;break-inside:avoid}
blockquote p{margin:0}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:9.5pt;break-inside:avoid}
th{background:#DCE4EC}
th,td{border:1px solid #777;padding:4px 6px;vertical-align:middle}
pre{background:#F1F3F5;border:1px solid #CCD;border-radius:4px;padding:8px 10px;white-space:pre-wrap;font-size:9.5pt;break-inside:avoid}
code{font-family:"NanumGothicCoding","Consolas",monospace}
figure{margin:8px auto 14px;text-align:center;break-inside:avoid}
figure img{width:100%;border:1px solid #BBB}
figcaption{font-size:9.5pt;color:#333;margin-top:4px}
</style><body>${body}</body></html>`;

(async () => {
  const { chromium } = require("playwright");
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: "load" });
  await page.pdf({
    path: out, format: "A4", printBackground: true, displayHeaderFooter: true,
    margin: { top: "20mm", bottom: "18mm", left: "18mm", right: "18mm" },
    headerTemplate: `<div style="width:100%;font-size:8pt;color:#666;text-align:right;padding:0 18mm;font-family:NanumGothic,sans-serif">${header}</div>`,
    footerTemplate: `<div style="width:100%;font-size:8pt;color:#666;text-align:center;font-family:NanumGothic,sans-serif">- <span class="pageNumber"></span> -</div>`,
  });
  await browser.close();
  console.log("written", path.relative(root, out));
})();
