// Inline typing for the Sorph demo: a port of typer.py. plan() is the same
// word-by-word diff the Mac app uses to fix only the words that changed,
// in place; LiveTyper keeps what has been "typed" and the page animates it.

import { norm } from './cleanup.js';

const WORD = /\S+/gu;
const spans = text => [...text.matchAll(WORD)].map(m => ({ text: m[0], start: m.index, end: m.index + m[0].length }));

// Python's difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
export function opcodes(a, b) {
  const b2j = new Map();
  b.forEach((x, j) => { if (!b2j.has(x)) b2j.set(x, []); b2j.get(x).push(j); });
  function longest(alo, ahi, blo, bhi) {
    let bi = alo, bj = blo, size = 0, j2len = new Map();
    for (let i = alo; i < ahi; i++) {
      const next = new Map();
      for (const j of b2j.get(a[i]) || []) {
        if (j < blo) continue;
        if (j >= bhi) break;
        const k = (j2len.get(j - 1) || 0) + 1;
        next.set(j, k);
        if (k > size) { bi = i - k + 1; bj = j - k + 1; size = k; }
      }
      j2len = next;
    }
    while (bi > alo && bj > blo && a[bi - 1] === b[bj - 1]) { bi--; bj--; size++; }
    while (bi + size < ahi && bj + size < bhi && a[bi + size] === b[bj + size]) size++;
    return [bi, bj, size];
  }
  const queue = [[0, a.length, 0, b.length]], blocks = [];
  while (queue.length) {
    const [alo, ahi, blo, bhi] = queue.pop();
    const [i, j, k] = longest(alo, ahi, blo, bhi);
    if (k) {
      blocks.push([i, j, k]);
      if (alo < i && blo < j) queue.push([alo, i, blo, j]);
      if (i + k < ahi && j + k < bhi) queue.push([i + k, ahi, j + k, bhi]);
    }
  }
  blocks.sort((x, y) => x[0] - y[0] || x[1] - y[1] || x[2] - y[2]);
  const merged = [];
  let [i1, j1, k1] = [0, 0, 0];
  for (const [i2, j2, k2] of blocks) {
    if (i1 + k1 === i2 && j1 + k1 === j2) k1 += k2;
    else { if (k1) merged.push([i1, j1, k1]); [i1, j1, k1] = [i2, j2, k2]; }
  }
  if (k1) merged.push([i1, j1, k1]);
  merged.push([a.length, b.length, 0]);
  const ops = [];
  let i = 0, j = 0;
  for (const [ai, bj, size] of merged) {
    const tag = i < ai && j < bj ? 'replace' : i < ai ? 'delete' : j < bj ? 'insert' : '';
    if (tag) ops.push([tag, i, ai, j, bj]);
    i = ai + size; j = bj + size;
    if (size) ops.push(['equal', ai, i, bj, j]);
  }
  return ops;
}

// [[start, end, replacement]] in `typed` coordinates, ascending and
// non-overlapping, that turn `typed` into `next` word by word.
//
// Words are diffed as a sequence, so a changed word early on is one small
// edit and the words after it stay where they are. Exact mode compares
// words as written. Soft mode (live preview) compares them ignoring case
// and punctuation and keeps the typed spelling: the preview model's comma
// or capital may differ from the final model's, and rewriting for a comma
// is flicker for nothing. The final pass runs exact and settles it.
// Characters before `floor` are committed and never touched.
export function plan(typed, next, floor = 0, soft = false) {
  const f = Math.min(floor, typed.length);
  let baseT = 0, baseN = 0;
  if (f) {
    // committed text stays; resume after the same *word* in `next`, since
    // its spelling of those words ("coast." vs "coast") may differ
    const j = spans(typed.slice(0, f)).length, nw = spans(next);
    baseT = f;
    baseN = j > 0 && j <= nw.length ? nw[j - 1].end : (j === 0 ? 0 : next.length);
  }
  const t = typed.slice(baseT), n = next.slice(baseN);
  const tw = spans(t), nw = spans(n);
  const key = soft ? norm : w => w;
  const tk = tw.map(m => key(m.text)), nk = nw.map(m => key(m.text));
  // the last typed word is re-synced when the text continues past it:
  // a preview ends "test." but the sentence goes on "test how it"
  if (soft && tw.length && nw.length > tw.length) {
    tk[tk.length - 1] = tw[tw.length - 1].text;
    nk[tw.length - 1] = nw[tw.length - 1].text;
  }
  // the gap before word i1 through the end of word i2-1, so spacing travels
  // with the words it separates; at the very start, word i1 through the gap
  // after word i2-1 instead
  function span(words, i1, i2) {
    if (i1) return [words[i1 - 1].end, i2 > i1 ? words[i2 - 1].end : words[i1 - 1].end];
    if (i2 < words.length) return [0, words[i2].start];
    return [0, words.length ? words[words.length - 1].end : 0];
  }
  const edits = [];
  for (const [tag, i1, i2, j1, j2] of opcodes(tk, nk)) {
    if (tag === 'equal') continue;
    const [a, b] = span(tw, i1, i2), [c, d] = span(nw, j1, j2);
    edits.push([baseT + a, baseT + b, n.slice(c, d)]);
  }
  // text after the last word (rare: trailing whitespace) follows `next`
  const tailT = tw.length ? tw[tw.length - 1].end : 0, tailN = nw.length ? nw[nw.length - 1].end : 0;
  if (t.slice(tailT) !== n.slice(tailN)) {
    if (edits.length && edits[edits.length - 1][1] === baseT + tailT) {
      const [a, , r] = edits.pop();
      edits.push([a, typed.length, r + n.slice(tailN)]);
    } else edits.push([baseT + tailT, typed.length, n.slice(tailN)]);
  }
  return edits.map(([a, b, r]) => trim(typed, a, b, r));
}

// Shrink an edit by the characters it would delete and retype unchanged:
// "work" -> "works and" only types "s and".
function trim(typed, a, b, r) {
  const old = typed.slice(a, b);
  let p = 0;
  while (p < Math.min(old.length, r.length) && old[p] === r[p]) p++;
  let q = 0;
  while (q < Math.min(old.length, r.length) - p && old[old.length - 1 - q] === r[r.length - 1 - q]) q++;
  return [a + p, b - q, r.slice(p, r.length - q)];
}

// What the line reads after `edits`.
export function apply(typed, edits) {
  for (let k = edits.length - 1; k >= 0; k--) {
    const [a, b, r] = edits[k];
    typed = typed.slice(0, a) + r + typed.slice(b);
  }
  return typed;
}

export class LiveTyper {
  constructor() { this.typed = ''; this.floor = 0; }
  commit() { this.floor = this.typed.length; }
  // Make the line read `next` (or, in soft mode, the same words), touching
  // only the words that changed.
  update(next, soft = false) {
    const edits = plan(this.typed, next, this.floor, soft);
    this.typed = apply(this.typed, edits);
    return edits;
  }
}
