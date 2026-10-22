// Transcript cleanup for the Sorph demo: a line-for-line port of the rule
// pass in cleanup.py (rule_cleanup, ends_sentence, join, strip_repeats).
// Python's Unicode \w is spelled [\p{L}\p{N}_] here.

// Filler words Whisper writes out. Per language, so a token that is a real
// word elsewhere ("er" in German, "hum" in English) is only stripped where it
// is noise. English fillers are applied everywhere: they leak into every
// language's speech.
export const FILLERS = {
  en: ['um', 'umm', 'uh', 'uhm', 'uhh', 'erm', 'hmm', 'mm', 'mhm'],
  de: ['äh', 'ähm', 'ähh', 'hm', 'hmm', 'mhm', 'mmh'],
  fr: ['euh', 'euhh', 'hum', 'hem'],
  es: ['em', 'ehm'],
  nl: ['uh', 'uhm', 'ehm'],
};

const W = '\\p{L}\\p{N}_';
const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// a period ends a sentence unless it is part of an ellipsis ("..." marks a
// pause in Whisper output, not a full stop)
const SENTENCE_END = new RegExp(`((?:(?<!\\.)\\.(?!\\.)|[!?])["'”’)\\]]*\\s+)([${W}])`, 'gu');

function fillerPattern(language) {
  const words = new Set([...FILLERS.en, ...(FILLERS[language] || [])]);
  const alts = [...words].sort((a, b) => b.length - a.length).map(escape).join('|');
  // the filler plus any comma/ellipsis glued to it, e.g. "um," or "äh…"
  return new RegExp(`(?<![${W}'’])(?:${alts})(?![${W}'’])[,…]?\\s*`, 'giu');
}

function upperFirst(text) {
  const c = String.fromCodePoint(text.codePointAt(0));
  return c.toUpperCase() + text.slice(c.length);
}

// Filler removal + sentence capitalization + closing punctuation.
// `close: false` leaves the end open (a mid-dictation pause is not a full
// stop); `capitalizeFirst: false` continues a sentence that is already
// under way.
export function ruleCleanup(text, language = 'en', { close = true, capitalizeFirst = true } = {}) {
  text = text.trim();
  if (!text) return text;
  text = text.replace(fillerPattern(language), '');
  text = text.replace(/\s+([,.;:!?])/gu, '$1');        // "word ," → "word,"
  text = text.replace(/\s{2,}/gu, ' ').trim();
  text = text.replace(/^[,;:]\s*/u, '');                // leading orphan comma
  if (!text) return text;
  if (capitalizeFirst) text = upperFirst(text);
  text = text.replace(SENTENCE_END, (_, end, ch) => end + ch.toUpperCase());
  if (close && /[\p{L}\p{N}]$/u.test(text)) text += '.';
  return text;
}

// Does a following utterance start a new sentence?
export function endsSentence(text) {
  return !text || '.!?…'.includes(text.trimEnd().slice(-1));
}

export function join(a, b) {
  return a && b ? (a + ' ' + b).trim() : (a || b);
}

export function norm(token) {
  return token.replace(new RegExp(`[^${W}]`, 'gu'), '').toLowerCase();
}

const words = text => text.split(/\s+/u).filter(Boolean);

// Cut a decoder loop: once a phrase of 1–4 words repeats `minRuns` times
// back to back ("the the the", "a bit of a bit of a bit of"), keep the text
// up to the first occurrence only. Junk with no letters or digits ("//")
// becomes empty.
export function stripRepeats(text, minRuns = 3) {
  if (!new RegExp(`[${W}]`, 'u').test(text)) return '';
  const ws = words(text), n = ws.map(norm);
  const same = (i, j, p) => { for (let k = 0; k < p; k++) if (n[i + k] !== n[j + k]) return false; return true; };
  for (let i = 0; i < n.length; i++) {
    for (let p = 1; p < 5; p++) {
      let runs = 1;
      while (i + (runs + 1) * p <= n.length && same(i + runs * p, i, p)) runs++;
      if (runs >= minRuns) return ws.slice(0, i + p).join(' ');
    }
  }
  return text;
}
