// 사용자 가이드의 화면 캡처 자리 그림을 만들고, 캡처 목록(docs/캡처목록.md)을 쓴다.
//   - 목록: docs/images/captures.json
//   - 실제 캡처(같은 이름의 파일)가 이미 있으면 건드리지 않는다. 자리 그림만 다시 그린다.
//     (자리 그림은 PNG 안에 hwpx-placeholder 표시를 넣어 구분)
// 사용: node tools/make_placeholders.js   (Playwright와 한글 글꼴 필요)
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

const root = path.dirname(__dirname);
const dir = path.join(root, "docs", "images");
const list = JSON.parse(fs.readFileSync(path.join(dir, "captures.json"), "utf8")).items;
const MARK = "hwpx-placeholder";

const isPlaceholder = (p) => fs.existsSync(p) && fs.readFileSync(p).includes(Buffer.from(MARK));

// PNG의 IHDR 뒤에 tEXt 조각을 넣어 자리 그림임을 표시
function tagPng(buf) {
  const data = Buffer.from(`Comment\0${MARK}`, "latin1");
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from("tEXt"), data]);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(zlib.crc32(body) >>> 0);
  const at = 8 + 25; // 서명 8 + IHDR 25
  return Buffer.concat([buf.subarray(0, at), len, body, crc, buf.subarray(at)]);
}

const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
const html = (it, i) => `<!doctype html><meta charset="utf-8"><style>
body{margin:0;width:1600px;height:1000px;background:#EEF3F6;font-family:"NanumGothic","Malgun Gothic",sans-serif;display:flex;align-items:center;justify-content:center}
.f{box-sizing:border-box;width:1520px;height:920px;border:6px dashed #8FA3B5;border-radius:28px;background:#F8FAFB;padding:70px 90px;display:flex;flex-direction:column}
.n{display:inline-block;background:#1B2A41;color:#fff;font-size:40px;font-weight:800;padding:10px 28px;border-radius:14px;align-self:flex-start}
.t{font-size:72px;font-weight:800;color:#1B2A41;margin:34px 0 46px}
.k{font-size:30px;font-weight:800;color:#1F776D;margin-top:22px}
.v{font-size:38px;color:#1B2A41;margin-top:8px;line-height:1.35}
.p{margin-top:auto;font-size:28px;color:#5B6B7C;font-family:"NanumGothicCoding",monospace}
</style><div class="f"><span class="n">화면 캡처 자리 ${it.file.split("_")[0]}</span>
<div class="t">${esc(it.title)}</div>
<div class="k">찍을 화면</div><div class="v">${esc(it.shot)}</div>
<div class="k">표시할 곳(빨간 상자·화살표)</div><div class="v">${esc(it.mark)}</div>
<div class="p">이 그림을 실제 캡처로 바꾸려면 → docs/images/${esc(it.file)}</div></div>`;

(async () => {
  const { chromium } = require("playwright");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  let made = 0, kept = 0;
  for (const [i, it] of list.entries()) {
    const out = path.join(dir, it.file);
    if (fs.existsSync(out) && !isPlaceholder(out)) { kept += 1; continue; }
    await page.setContent(html(it, i), { waitUntil: "load" });
    fs.writeFileSync(out, tagPng(await page.screenshot({ type: "png" })));
    made += 1;
  }
  await browser.close();

  const rows = list.map((it, i) => {
    const real = !isPlaceholder(path.join(dir, it.file));
    return `| ${i + 1} | \`${it.file}\` | ${it.title} | ${it.shot} | ${it.mark} | ${real ? "넣음" : "자리 그림"} |`;
  });
  fs.writeFileSync(path.join(root, "docs", "캡처목록.md"), `# 사용자 가이드 화면 캡처 목록

사용자 가이드(md·pptx·hwpx·pdf)에 들어가는 Claude 데스크톱 앱 화면 캡처 목록입니다. 아직 캡처가 없는 자리에는 「화면 캡처 자리」 그림이 들어가 있습니다.

## 캡처 넣는 법

- (찍기) Windows에서 \`Win + Shift + S\` → 창 또는 영역 선택 → 그림판 등에 붙여 PNG로 저장
- (표시) 「표시할 곳」은 빨간 상자나 화살표로 표시(그림판 「도형」)
- (개인정보) 이메일·이름·다른 대화 제목·폴더 경로의 사용자 이름은 가리기
- (크기) 가로 1600픽셀 안팎, 가로:세로 16:10 정도면 슬라이드에 꽉 차게 들어감
- (넣기) 아래 파일 이름 그대로 \`docs/images/\`에 저장해 저장소에 올림 → 가이드를 다시 만들면 자리 그림 대신 들어감

## 목록

| 순서 | 파일 이름 | 제목 | 찍을 화면 | 표시할 곳 | 상태 |
|---|---|---|---|---|---|
${rows.join("\n")}

## 가이드 다시 만들기

\`\`\`
node tools/make_placeholders.js
node tools/build_slides.js docs/사용자가이드.slides.json
python -X utf8 skills/hwpx-template/scripts/md2hwpx.py examples/양식예시.hwpx docs/사용자가이드.md docs/사용자가이드.hwpx --pdf docs/사용자가이드.pdf
\`\`\`

- PDF는 Windows+한글에서 \`--pdf\`로 만들거나, 한글에서 사용자가이드.hwpx를 열어 「PDF로 저장」
`, "utf8");
  console.log(`자리 그림 ${made}장 만듦, 실제 캡처 ${kept}장 유지 → docs/캡처목록.md`);
})();
