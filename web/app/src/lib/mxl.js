// Compressed MusicXML (.mxl, #2657): a zip holding the score and META-INF/container.xml naming it. Read with
// the platform's DecompressionStream (browsers and Node 18+), so no zip library is bundled.

import { parseXml, child, kids } from "./xml.js";

const u16 = (b, o) => b[o] | (b[o + 1] << 8);
const u32 = (b, o) => (b[o] | (b[o + 1] << 8) | (b[o + 2] << 16) | (b[o + 3] << 24)) >>> 0;

// bytes → Map name → {method, offset, size} from the zip's central directory.
export function zipEntries(bytes) {
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) if (u32(bytes, i) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error("not a zip file");
  const count = u16(bytes, eocd + 10);
  let p = u32(bytes, eocd + 16);
  const out = new Map();
  for (let k = 0; k < count; k++) {
    if (u32(bytes, p) !== 0x02014b50) throw new Error("bad zip directory");
    const method = u16(bytes, p + 10), size = u32(bytes, p + 20), nameLen = u16(bytes, p + 28);
    const extra = u16(bytes, p + 30), comment = u16(bytes, p + 32), local = u32(bytes, p + 42);
    const name = new TextDecoder().decode(bytes.subarray(p + 46, p + 46 + nameLen));
    out.set(name, { method, size, local });
    p += 46 + nameLen + extra + comment;
  }
  return out;
}

async function entryBytes(bytes, entry) {
  const lp = entry.local, start = lp + 30 + u16(bytes, lp + 26) + u16(bytes, lp + 28);
  const data = bytes.subarray(start, start + entry.size);
  if (entry.method === 0) return data;
  if (entry.method !== 8) throw new Error("unsupported zip compression");
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

// .mxl bytes → the score's MusicXML text.
export async function readMxl(buffer) {
  const bytes = new Uint8Array(buffer), entries = zipEntries(bytes);
  let name = null;
  if (entries.has("META-INF/container.xml")) {
    const container = parseXml(new TextDecoder().decode(await entryBytes(bytes, entries.get("META-INF/container.xml"))));
    name = kids(child(container, "rootfiles"), "rootfile").map(r => r.attrs["full-path"]).find(Boolean) ?? null;
  }
  name ??= [...entries.keys()].find(k => !k.startsWith("META-INF/") && /\.(musicxml|xml)$/i.test(k));
  if (!name || !entries.has(name)) throw new Error("no score inside the .mxl file");
  return new TextDecoder().decode(await entryBytes(bytes, entries.get(name)));
}
