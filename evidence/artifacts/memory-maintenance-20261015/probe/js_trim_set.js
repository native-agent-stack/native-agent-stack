// Prints, as JSON, every code point that String.prototype.trim() removes from a one-character string,
// the engine that ran it, and the UTF-16 length of an astral character.
const removed = [];
for (let cp = 0; cp <= 0x10ffff; cp++) {
  if (cp >= 0xd800 && cp <= 0xdfff) continue; // lone surrogates are not characters
  const s = String.fromCodePoint(cp);
  if (s.trim() === "") removed.push(cp);
}
const engine = typeof Bun !== "undefined" ? `bun ${Bun.version}` : `node ${process.version}`;
console.log(JSON.stringify({ engine, removed, astral_length: String.fromCodePoint(0x1f600).length }));
