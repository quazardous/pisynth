// A small XML reader for MusicXML (#2657): elements, attributes and text — no namespaces, no DTD. Pure, so
// the score code is tested under Node (which has no DOMParser); fast enough for a long piano score.

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'" };
const decode = s => s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) =>
  e[0] === "#" ? String.fromCodePoint(e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)) : ENTITIES[e] ?? m);

// text → the root element {name, attrs, children, text}
export function parseXml(text) {
  const root = { name: "#document", attrs: {}, children: [], text: "" };
  const stack = [root];
  let i = 0;
  const n = text.length;
  while (i < n) {
    const lt = text.indexOf("<", i);
    if (lt < 0) break;
    if (lt > i) stack.at(-1).text += decode(text.slice(i, lt));
    if (text.startsWith("<!--", lt)) { i = text.indexOf("-->", lt + 4) + 3; if (i < 3) break; continue; }
    if (text.startsWith("<![CDATA[", lt)) {
      const end = text.indexOf("]]>", lt + 9);
      stack.at(-1).text += text.slice(lt + 9, end < 0 ? n : end);
      i = end < 0 ? n : end + 3;
      continue;
    }
    if (text[lt + 1] === "?" || text[lt + 1] === "!") {      // <?xml …?>, <!DOCTYPE … [ … ]>
      let depth = 0, j = lt + 1;
      for (; j < n; j++) { if (text[j] === "[") depth++; else if (text[j] === "]") depth--; else if (text[j] === ">" && depth <= 0) break; }
      i = j + 1;
      continue;
    }
    const gt = text.indexOf(">", lt);
    if (gt < 0) break;
    const tag = text.slice(lt + 1, gt);
    if (tag[0] === "/") {                                      // </name>
      if (stack.length > 1) stack.pop();
      i = gt + 1;
      continue;
    }
    const selfClosing = tag.endsWith("/");
    const body = selfClosing ? tag.slice(0, -1) : tag;
    const name = body.match(/^[^\s/>]+/)?.[0] ?? "";
    const attrs = {};
    for (const m of body.slice(name.length).matchAll(/([^\s=]+)\s*=\s*("([^"]*)"|'([^']*)')/g)) attrs[m[1]] = decode(m[3] ?? m[4]);
    const el = { name, attrs, children: [], text: "" };
    stack.at(-1).children.push(el);
    if (!selfClosing) stack.push(el);
    i = gt + 1;
  }
  return root.children.find(c => c.name) ?? root;
}

export const child = (el, name) => el?.children.find(c => c.name === name) ?? null;
export const kids = (el, name) => el?.children.filter(c => c.name === name) ?? [];
export const textOf = (el, name) => (name ? child(el, name) : el)?.text.trim() ?? "";
export const numOf = (el, name, fallback = 0) => { const v = Number(textOf(el, name)); return Number.isFinite(v) && textOf(el, name) !== "" ? v : fallback; };
