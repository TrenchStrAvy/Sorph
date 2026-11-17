// The website's intro: Sorph's startup reveal (the orb coming out of glass)
// played over the hero, on the hero's own sphere. The reveal draws the
// hero's canvas as its logo, at the hero orb's place and size, so the same
// ribbons turn in both: the white sheet over the page fades while the
// glass lets go, onto the hero's orb, and the transcription display
// starts around it.
//
// Built into docs/intro.js by `npm run build:site`. No React: the glass
// engine is driven directly.

import { startEngine, loadLogo, LOOKS, BOX, type Settings } from "./liquid-glass-logo-reveal";

const root = document.documentElement;
const sheet = document.getElementById("intro");
const orbCanvas = document.getElementById("orb") as HTMLCanvasElement | null;

function finish(fast = false) {
  if (!root.classList.contains("intro")) return;
  window.dispatchEvent(new Event("sorph:intro-done"));
  root.classList.remove("intro");
  root.classList.add("intro-out");
  if (sheet) {
    sheet.style.transition = `opacity ${fast ? 0.2 : 0.7}s ease`;
    sheet.style.opacity = "0";
    setTimeout(() => { sheet.remove(); root.classList.remove("intro-out"); }, 1000);
  }
}
(window as any).sorphIntroFinish = finish;

function play() {
  if (!sheet || !orbCanvas) return finish(true);
  const orb = orbCanvas.getBoundingClientRect();
  if (!orb.width) return finish(true);
  // the hero draws its sphere across 0.549 of its canvas (sphere.js: R 0.62 seen from 3.2)
  const SPHERE = 0.549;
  const P: Settings = {
    ...LOOKS.light,
    background: "#ffffff", plateColor: "#ffffff", originalColors: true,
    logoScale: 0.62, finalScale: 1, startZoom: 2.2,
    tileSize: 0,
  };
  // size the tile so the bare logo lands exactly on the hero's sphere
  // (FIT: the orb's picture, cropped to its visible pixels, fills the logo box a little
  // more than the sphere alone; measured against the hero at 1440 and 390 px wide)
  const FIT = 0.774;
  P.tileSize = (FIT * SPHERE * orb.width) / (P.logoScale * P.finalScale * BOX);
  const side = Math.ceil(P.tileSize * 1.75) + 2;      // the engine fits the tile into min(w, h) / 1.75
  const wrap = document.createElement("div");
  const cx = orb.left + orb.width / 2, cy = orb.top + orb.height / 2;
  wrap.style.cssText = `position:absolute;left:${cx - side / 2}px;top:${cy - side / 2}px;width:${side}px;height:${side}px;background:#fff;overflow:hidden`;
  sheet.appendChild(wrap);
  const live = { current: { settings: P, loop: false, speed: 1, time: undefined, source: orbCanvas, sourceScale: SPHERE } };
  const engine = startEngine(wrap, live as any);
  if (!engine) return finish(true);
  loadLogo(new URL("app/orb.png", document.baseURI).href).then((data) => {
    engine.setLogo(data);
    // hand over while the glass lets go (from just before `present`): the
    // sheet fades as the glass dissolves, onto the hero's orb underneath
    setTimeout(() => finish(), (P.present - 0.1) * 1000);
  }, () => finish(true));
}

if (root.classList.contains("intro")) {
  // let the hero draw its first frames before they are borrowed
  requestAnimationFrame(() => requestAnimationFrame(play));
  const skip = () => finish(true);
  for (const type of ["wheel", "touchmove", "keydown", "pointerdown"]) addEventListener(type, skip, { once: true, passive: true });
}
