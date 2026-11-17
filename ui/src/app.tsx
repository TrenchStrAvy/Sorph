// Sorph's dashboard: a fixed 830 × 420 page shown by dashboard.py in a web
// view. While Sorph loads it is the startup screen (the orb revealed out of
// glass); then it is a gallery of preset cards, each a pair of languages
// (speak → write), with the two pickers under it and the settings behind
// the gear.
//
// Python pushes the whole state with window.sorph.push(state); the page
// answers with window.webkit.messageHandlers.sorph.postMessage({type, …}).

import * as React from "react";
import { createRoot } from "react-dom/client";

import { GlassIconReveal } from "./liquid-glass-logo-reveal";
// @ts-ignore: plain JavaScript, the website's sphere shader
import { mountSphere } from "./sphere.js";
import { WarpCarousel, WARP_CAROUSEL_CARDS, type WarpCard } from "./warp-carousel";

interface Lang {
  code: string;
  name: string; // in English: what the lists are sorted by
  native: string;
}

interface Preset {
  speak: string;
  write: string; // "" = plain dictation
  speakName: string;
  writeName: string;
  speakNative: string;
  writeNative: string;
}

interface Settings {
  mics: string[];
  mic: string;
  micDefault: string;
  ducking: boolean;
  duck: number;
  corrections: boolean;
  tone: boolean;
  position: string;
  positions: string[];
  moving: boolean;
  dictionary: string[];
  slots: string[];
  quickKeys: Record<string, string>;
}

interface State {
  phase: "loading" | "ready";
  caption: string;
  progress: number;
  error: string;
  dark: boolean;
  theme: string;
  logo: string;
  version: string;
  language: string;
  translateTo: string;
  speakQuick: Lang[];
  speakAll: Lang[];
  writeQuick: Lang[];
  writeAll: Lang[];
  presets: Preset[];
  status: string;
  settings: Settings | null;
  openSettings?: number; // changes each time the menu bar asks for the settings
}

declare global {
  interface Window {
    sorph: { push: (state: Partial<State>) => void; state: Partial<State> };
    webkit?: { messageHandlers: { sorph: { postMessage: (m: unknown) => void } } };
  }
}

const send = (message: Record<string, unknown>) => window.webkit?.messageHandlers.sorph.postMessage(message);

const EMPTY: State = {
  phase: "loading", caption: "starting…", progress: 0.05, error: "", dark: false, theme: "auto", logo: "", version: "",
  language: "en", translateTo: "", speakQuick: [], speakAll: [], writeQuick: [], writeAll: [], presets: [],
  status: "ready", settings: null,
};

function useSorph(): State {
  const [state, setState] = React.useState<State>({ ...EMPTY, ...window.sorph.state });
  React.useEffect(() => {
    window.sorph.push = (next) => {
      window.sorph.state = { ...window.sorph.state, ...next };
      setState((old) => ({ ...old, ...next }));
    };
    send({ type: "ready" });
  }, []);
  return state;
}

// The light a card casts above and below it, taken from the card itself:
// the mean of its most vivid mesh colours. (The carousel's own glow colours
// were picked for its demo and do not always match the card.)
const glows = new Map<string[], string>();
function glowOf(mesh: string[] | undefined): string {
  if (!mesh || !mesh.length) return "#7fd0f0";
  let glow = glows.get(mesh);
  if (!glow) {
    const scored = mesh.map((hex) => {
      const n = parseInt(hex.slice(1), 16);
      const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
      const max = Math.max(...rgb);
      return { rgb, score: max ? ((max - Math.min(...rgb)) / max) * max : 0 };
    }).sort((a, b) => b.score - a.score).slice(0, 8);
    const mean = [0, 1, 2].map((i) => Math.round(scored.reduce((sum, c) => sum + c.rgb[i], 0) / scored.length));
    glow = "#" + mean.map((v) => v.toString(16).padStart(2, "0")).join("");
    glows.set(mesh, glow);
  }
  return glow;
}

// The four hand-tuned palettes of the Warp Carousel, one per card in turn.
function cardFor(preset: Preset & { unsaved?: boolean }, i: number): WarpCard {
  const look = WARP_CAROUSEL_CARDS[i % WARP_CAROUSEL_CARDS.length];
  const translating = preset.write !== "";
  return {
    mesh: look.mesh,
    numeral: look.numeral,
    accent: look.accent,
    glow: glowOf(look.mesh),
    title: translating ? `${preset.speakName}\nto ${preset.writeName}` : `${preset.speakName}\ndictation`,
    value: preset.speak.toUpperCase(),
    unit: translating ? `→ ${preset.write.toUpperCase()}` : undefined,
    footer: (translating ? `${preset.speakNative} → ${preset.writeNative}` : preset.speakNative) + (preset.unsaved ? "  ·  not saved" : ""),
    detail: translating ? "ring" : "wave",
  };
}

const fold = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// A language field: click or type. Typing narrows the list by English name,
// native name or code; the list is alphabetical by English name, with the
// languages from the menu bar first while nothing is typed.
function Combo({ label, value, quick, all, first, onChange }: {
  label: string; value: string; quick: Lang[]; all: Lang[]; first?: Lang; onChange: (code: string) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [at, setAt] = React.useState(0);
  const input = React.useRef<HTMLInputElement>(null);
  const list = React.useRef<HTMLDivElement>(null);
  const chosen = (first && first.code === value ? first : all.find((l) => l.code === value) || quick.find((l) => l.code === value)) || first;

  const rows = React.useMemo(() => {
    const q = fold(query.trim());
    if (!q) {
      const rest = all.filter((l) => !quick.some((y) => y.code === l.code));
      return [...(first ? [first] : []), ...quick, ...rest];
    }
    const hit = (l: Lang) => {
      const name = fold(l.name), native = fold(l.native);
      if (name.startsWith(q) || native.startsWith(q) || l.code === q) return 0;
      return name.includes(q) || native.includes(q) ? 1 : -1;
    };
    const pool = first ? [first, ...all] : all;
    return pool.map((l) => ({ l, rank: hit(l) })).filter((r) => r.rank >= 0)
      .sort((a, b) => a.rank - b.rank).map((r) => r.l);
  }, [query, quick, all, first]);
  const yours = !query.trim() ? quick.length : 0;
  const lead = first && !query.trim() ? 1 : 0;

  React.useEffect(() => setAt(0), [query, open]);
  React.useEffect(() => {
    list.current?.querySelector(".on")?.scrollIntoView({ block: "nearest" });
  }, [at, open]);

  const pick = (l: Lang) => {
    onChange(l.code);
    setOpen(false);
    setQuery("");
    input.current?.blur();
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setAt(Math.min(rows.length - 1, at + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAt(Math.max(0, at - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); if (rows[at]) pick(rows[at]); }
    else if (e.key === "Escape") { setOpen(false); setQuery(""); input.current?.blur(); }
    e.stopPropagation(); // the arrows are for the list, not the gallery
  };
  const shown = chosen ? (chosen.native && chosen.native !== chosen.name ? `${chosen.name} · ${chosen.native}` : chosen.name) : "";
  return (
    <label className={"picker" + (open ? " active" : "")}>
      <input ref={input} aria-label={label} title={label} value={open ? query : shown} placeholder={shown} spellCheck={false} autoComplete="off"
        onFocus={() => setOpen(true)} onBlur={() => { setOpen(false); setQuery(""); }}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }} onKeyDown={key} />
      {open && (
        <div className="menu" ref={list} onMouseDown={(e) => e.preventDefault()}>
          {rows.length === 0 && <p>no language like that</p>}
          {rows.map((l, i) => (
            <React.Fragment key={l.code || "same"}>
              {yours > 0 && i === lead && <p>yours</p>}
              {yours > 0 && i === lead + yours && <p>all · a to z</p>}
              <button className={(i === at ? "on" : "") + (l.code === value ? " chosen" : "")}
                onMouseEnter={() => setAt(i)} onClick={() => pick(l)}>
                <b>{l.name}</b>{l.native && l.native !== l.name && <i>{l.native}</i>}
              </button>
            </React.Fragment>
          ))}
        </div>
      )}
    </label>
  );
}

function Toggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return <button className={"toggle" + (on ? " on" : "")} role="switch" aria-checked={on} onClick={() => onChange(!on)}><i /></button>;
}

// A dark capsule with a light pill that slides under the chosen option
// (the look of 21st.dev's Segmented Mode Toggle, drawn with Sorph's own CSS).
function Segments<T extends string>({ options, value, onChange, label, small }: {
  options: { value: T; label: string }[]; value: T; onChange: (value: T) => void; label: string; small?: boolean;
}) {
  const at = Math.max(0, options.findIndex((o) => o.value === value));
  return (
    <div className={"seg" + (small ? " small" : "")} role="radiogroup" aria-label={label}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}>
      <div className="thumb" aria-hidden="true"><i style={{ width: `${100 / options.length}%`, transform: `translateX(${at * 100}%)` }} /></div>
      {options.map((o, i) => (
        <button key={o.value} role="radio" aria-checked={o.value === value} className={o.value === value ? "on" : ""}
          style={{ gridColumnStart: i + 1, gridRowStart: 1 }} onClick={() => o.value !== value && onChange(o.value)}>
          <span>{o.label}<sup>{String(i + 1).padStart(2, "0")}</sup></span>
        </button>
      ))}
    </div>
  );
}

type Tab = "general" | "keys" | "words";

function SettingsPanel({ s, languages, onClose }: { s: Settings; languages: Lang[]; onClose: () => void }) {
  const [tab, setTab] = React.useState<Tab>("general");
  const [word, setWord] = React.useState("");
  const set = (key: string, value: unknown) => send({ type: "set", key, value });
  const add = () => {
    if (word.trim()) send({ type: "word", entry: word.trim() });
    setWord("");
  };
  return (
    <aside className="panel">
      <header>
        <b>Settings</b>
        <button className="ghost" onClick={onClose}>Done</button>
      </header>
      <Segments small label="Settings" value={tab} onChange={setTab}
        options={[{ value: "general", label: "General" }, { value: "keys", label: "Keys" }, { value: "words", label: "Words" }]} />
      {tab === "general" && (
        <div className="rows">
          <div className="row">
            <span>Microphone</span>
            <select value={s.mic} onChange={(e) => set("mic", e.target.value)}>
              <option value="">System default{s.micDefault ? ` (${s.micDefault})` : ""}</option>
              {s.mics.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="row">
            <span>Music ducking</span>
            <div className="inline">
              <input type="range" min={0} max={100} value={s.duck} disabled={!s.ducking}
                onChange={(e) => set("duck", Number(e.target.value))} />
              <em>{s.duck}%</em>
              <Toggle on={s.ducking} onChange={(on) => set("ducking", on)} />
            </div>
          </div>
          <div className="row"><span>Self-corrections</span><Toggle on={s.corrections} onChange={(on) => set("corrections", on)} /></div>
          <div className="row"><span>Per-app tone</span><Toggle on={s.tone} onChange={(on) => set("tone", on)} /></div>
          <div className="row">
            <span>Sphere</span>
            <div className="inline">
              <button className="ghost" onClick={() => send({ type: "move" })}>{s.moving ? "Done moving" : "Move…"}</button>
              <select className="caps short" value={s.position} onChange={(e) => set("position", e.target.value)}>
                {s.positions.map((p) => <option key={p} value={p}>{p.replace("-", " ")}</option>)}
              </select>
            </div>
          </div>
        </div>
      )}
      {tab === "keys" && (
        <div className="rows">
          <p className="how">
            Hold <kbd>right ⌥</kbd> and speak; let go to finish. While holding it, tap <kbd>A</kbd> to keep
            dictating hands-free (again to stop), or one of these keys to change the language you speak:
          </p>
          {s.slots.map((slot) => (
            <div className="row" key={slot}>
              <span><kbd>⌥</kbd> <kbd>{slot.toUpperCase()}</kbd></span>
              <select value={s.quickKeys[slot] || ""} onChange={(e) => send({ type: "quick", slot, speak: e.target.value })}>
                <option value="">None</option>
                {languages.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
            </div>
          ))}
        </div>
      )}
      {tab === "words" && (
        <div className="rows">
          <p className="how">Names and words Sorph should know, and fixes for what it mishears (terror form = Terraform).</p>
          <div className="words">
            <input value={word} placeholder="Add a word or name" onChange={(e) => setWord(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && add()} />
            <div className="chips">
              {s.dictionary.map((w) => (
                <button key={w} title="Remove" onClick={() => send({ type: "unword", entry: w })}>{w} ×</button>
              ))}
            </div>
          </div>
          <p className="how second">Your languages: first in every list, and what the quick keys offer.</p>
          <div className="chips">
            {languages.map((l) => (
              <button key={l.code} title="Remove from your languages" disabled={languages.length < 2}
                onClick={() => send({ type: "unlang", speak: l.code })}>{l.name} ×</button>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}

// The orb at startup: stirred once, then settling. It starts with its
// ribbons swollen and flowing fast and eases down to the calm idle flow
// (Ribbon Glass: pulse 1 decaying by 0.18 per second, speed 0.9 + 2.2 × pulse).
function settling() {
  let pulse = 1;
  return (dt: number) => {
    pulse *= Math.pow(0.18, dt / 1.6);
    return { level: 0.05 + 0.5 * pulse, pulse: 0.6 * pulse, speed: 0.9 + 2.2 * pulse };
  };
}

const ORB_PX = 640; // the live orb's canvas; the sphere spans 0.549 of it (sphere.js: R 0.62 seen from 3.2)

function Splash({ state }: { state: State }) {
  // the live orb, drawn off the page and fed into the reveal as its logo
  const [orb, setOrb] = React.useState<HTMLCanvasElement | null>(null);
  React.useEffect(() => {
    const canvas = document.createElement("canvas");
    const stop = mountSphere(canvas, settling(), ORB_PX);
    if (!stop) return;
    setOrb(canvas);
    return stop;
  }, []);
  return (
    <div className="splash">
      {state.logo && (
        <GlassIconReveal
          logo={state.logo}
          label="Sorph"
          look={state.dark ? "dark" : "light"}
          background={state.dark ? "#0b0b0f" : "#efeff1"}
          plateColor={state.dark ? "#06070d" : "#ffffff"}
          originalColors
          source={orb}
          sourceScale={0.549}
          loop={false}
          tileSize={190}
          logoScale={0.62}
          finalScale={1}
          tuning={{ startZoom: 2.2 }}
          className="reveal"
        />
      )}
      <div className="loading">
        <b>Sorph</b>
        <span>{state.error || state.caption}</span>
        <div className="bar"><i style={{ width: `${Math.round(state.progress * 100)}%` }} /></div>
      </div>
    </div>
  );
}

function App() {
  const state = useSorph();
  React.useEffect(() => {
    document.documentElement.dataset.theme = state.dark ? "dark" : "light";
  }, [state.dark]);
  return state.phase === "ready" ? <Gallery state={state} /> : <Splash state={state} />;
}

function Gallery({ state }: { state: State }) {
  const [open, setOpen] = React.useState(false);
  const asked = React.useRef(state.openSettings);
  React.useEffect(() => {
    if (state.openSettings !== asked.current) setOpen(true);
    asked.current = state.openSettings;
  }, [state.openSettings]);
  const speak = state.language;
  const write = state.translateTo;
  const translating = write !== "";
  const name = (code: string, native = false) => {
    const l = state.speakAll.find((x) => x.code === code) || state.writeAll.find((x) => x.code === code);
    return l ? (native ? l.native : l.name) : code;
  };

  // The gallery shows one kind of card at a time.
  // Dictate: one card per language of the user's (the list under Settings →
  // Words; speaking a new language adds it), so there is always something
  // to thumb through.
  // Translate: the saved pairs. The pair in use always has a card: its
  // preset, or a card of its own (last, marked "not saved") that stays
  // until + keeps it or another unsaved pair takes its place. Staying
  // matters: turning from it to a preset must not change the cards under a
  // ring that is still turning.
  const isPreset = (s: string, w: string) => state.presets.some((p) => p.speak === s && p.write === w);
  const loose = React.useRef<{ dictate: Preset | null; translate: Preset | null }>({ dictate: null, translate: null });
  const kindOf = translating ? "translate" : "dictate";
  if (translating && !isPreset(speak, write)) {
    const was = loose.current[kindOf];
    if (!was || was.speak !== speak || was.write !== write) {
      loose.current[kindOf] = {
        speak, write, unsaved: true,
        speakName: name(speak), writeName: write ? name(write) : "",
        speakNative: name(speak, true), writeNative: write ? name(write, true) : "",
      } as Preset;
    }
  }
  const held = loose.current[kindOf];
  const extra = translating && held && !isPreset(held.speak, held.write) ? held : null;
  const cards = React.useMemo(() => {
    if (!translating) {
      return state.speakQuick.map((l) => ({
        speak: l.code, write: "", speakName: l.name, writeName: "", speakNative: l.native, writeNative: "",
      }) as Preset);
    }
    const pairs = state.presets.filter((p) => p.write !== "");
    return extra ? [...pairs, extra] : pairs;
  }, [state.presets, state.speakQuick, translating, extra]);
  const active = cards.findIndex((p) => p.speak === speak && p.write === write);
  const saved = !(cards[active] as Preset & { unsaved?: boolean }).unsaved;
  // The ring is given new cards only when they really are other cards.
  // Every update from Sorph (a status line is enough) carries the presets
  // as a new list of the same cards, and a ring handed "new" cards sets
  // itself up again and turns the front card in afresh.
  const which = cards.map((c) => `${c.speak}>${c.write}${(c as Preset & { unsaved?: boolean }).unsaved ? "*" : ""}`).join(" ");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const faces = React.useMemo(() => cards.map(cardFor), [which]);

  // The card in front is the pair in use, except for the moment after the
  // gallery was turned by hand and before Sorph has switched to that card.
  // Worked out while rendering, not in an effect: the ring must get its new
  // cards and the index among them together.
  const stamp = `${kindOf}/${cards.length}/${active}`;
  const [turned, setTurned] = React.useState<{ to: number; stamp: string } | null>(null);
  const front = turned && turned.stamp === stamp ? turned.to : active;
  const setFront = (to: number) => setTurned({ to, stamp });
  const timer = React.useRef<number>(0);
  const use = (next: { speak: string; write: string }) => send({ type: "pair", ...next });
  const turn = (i: number) => {
    setFront(i);
    window.clearTimeout(timer.current);
    // wait for the ring to settle on a card before switching models
    const card = cards[i];
    if (card) timer.current = window.setTimeout(() => use({ speak: card.speak, write: card.write }), 450);
  };

  // New cards (Dictate ↔ Translate, a preset added or removed) are shown
  // at once, on the right card, and faded in so the change reads as one.
  const stage = React.useRef<HTMLElement>(null);
  const first = React.useRef(true);
  React.useEffect(() => {
    if (first.current) { first.current = false; return; }
    stage.current?.animate([{ opacity: 0.15 }, { opacity: 1 }], { duration: 320, easing: "cubic-bezier(0.22, 1, 0.36, 1)" });
  }, [which]);

  // ← and → turn the gallery from anywhere in the window: after a click on
  // Dictate or Translate, on a button, on nothing. Only a text field or a
  // list keeps its arrows (the gallery itself already handles its own).
  const turnBy = React.useRef((step: number) => {});
  turnBy.current = (step) => cards.length > 1 && turn((front + step + cards.length) % cards.length);
  React.useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el && el.closest && el.closest("input, select, textarea, [role=region]")) return;
      e.preventDefault();
      turnBy.current(e.key === "ArrowRight" ? 1 : -1);
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  // what Translate goes to when it is switched on: the last language
  // written to, else the first of the user's that this one reaches
  const last = React.useRef("");
  if (write) last.current = write;
  const target = () => {
    const reach = (code: string) => code !== speak && state.writeAll.some((l) => l.code === code);
    if (reach(last.current)) return last.current;
    return (state.writeQuick.find((l) => reach(l.code)) || state.writeAll.find((l) => reach(l.code)) || { code: "" }).code;
  };
  // the second field may spill its list out of the bar only once it has
  // finished sliding open (while it moves it is clipped to the bar)
  const [settled, setSettled] = React.useState(translating);
  React.useEffect(() => {
    setSettled(false);
    if (!translating) return;
    const t = window.setTimeout(() => setSettled(true), 340);
    return () => window.clearTimeout(t);
  }, [translating]);
  // speaking the language that was being written to: the two trade places
  const speakIn = (code: string) => use({ speak: code, write: !translating ? "" : code === write ? speak : write });

  return (
    <div className={"app" + (open ? " open" : "")}>
      <header className="bar-top">
        <b>Sorph</b>
        {state.version && <span className="version">{state.version}</span>}
        <span className="status">{state.status}</span>
        <button className="icon" title={`Look: ${state.theme}`} onClick={() => send({ type: "theme" })}>
          <svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.2" /><path d="M8 1.8a6.2 6.2 0 0 1 0 12.4z" fill="currentColor" /></svg>
        </button>
        <button className="icon" title="Settings" onClick={() => setOpen(!open)}>
          <svg viewBox="0 0 16 16"><path d="M2 4.5h12M2 8h12M2 11.5h12" stroke="currentColor" strokeWidth="1.2" fill="none" strokeLinecap="round" /><circle cx="10.5" cy="4.5" r="1.6" fill="var(--bg)" stroke="currentColor" strokeWidth="1.2" /><circle cx="5" cy="8" r="1.6" fill="var(--bg)" stroke="currentColor" strokeWidth="1.2" /><circle cx="9" cy="11.5" r="1.6" fill="var(--bg)" stroke="currentColor" strokeWidth="1.2" /></svg>
        </button>
      </header>

      <main className="gallery" ref={stage}>
        <WarpCarousel
          key={state.dark ? "dark" : "light"}
          cards={faces}
          index={front}
          onIndexChange={turn}
          autoplay={false}
          background={state.dark ? "#0b0b0f" : "#efeff1"}
          ariaLabel={translating ? "Translation presets" : "Dictation presets"}
          recompose
          style={{ minHeight: 0, aspectRatio: "auto" }}
        />
      </main>

      <footer className="bar-bottom">
        <div className="dock">
          <Segments label="Dictate or translate" value={translating ? "translate" : "dictate"}
            options={[{ value: "dictate", label: "Dictate" }, { value: "translate", label: "Translate" }]}
            onChange={(mode) => use({ speak, write: mode === "translate" ? target() : "" })} />
          <Combo label="Language you speak" value={speak} quick={state.speakQuick} all={state.speakAll} onChange={speakIn} />
          {/* the second language slides out of the bar and back into it */}
          <div className={"more" + (translating ? " on" : "") + (settled ? " settled" : "")}>
            <span className="arrow">→</span>
            <Combo label="Language to write" value={write || last.current} quick={state.writeQuick} all={state.writeAll}
              onChange={(code) => use({ speak, write: code })} />
          </div>
          <i className="rule" />
          <button className="tool" title="Keep this as a preset" disabled={saved}
            onClick={() => send({ type: "save", speak, write })}>
            <svg viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" /></svg>
          </button>
          <button className="tool" title={translating ? "Remove this preset" : "Remove this language from yours"}
            disabled={translating ? !saved || state.presets.length < 2 : cards.length < 2}
            onClick={() => send(translating ? { type: "remove", speak, write } : { type: "unlang", speak })}>
            <svg viewBox="0 0 16 16"><path d="M3 8h10" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" /></svg>
          </button>
        </div>
      </footer>

      {open && state.settings && <SettingsPanel s={state.settings} languages={state.speakQuick} onClose={() => setOpen(false)} />}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
