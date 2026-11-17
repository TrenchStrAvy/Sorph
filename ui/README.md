# Sorph's dashboard page

`dashboard.py` shows `index.html` in a web view. The script it loads,
`dist/dashboard.js`, is built from `src/` and committed, so installing
Sorph needs no Node.

```sh
cd ui && npm install && npm run build     # after changing anything in src/
```

| File | What it is |
|---|---|
| `src/app.tsx` | the page: startup screen, preset gallery, pickers, settings |
| `src/warp-carousel.tsx` | Warp Carousel by Louis Studios (studios.lou15.com), via 21st.dev. Changed in four places (marked `Sorph:` in the source): three string literals the copy had broken; a card turned by hand comes to rest dead centre (the creep past rest is kept for autoplay); when the cards themselves change, the ring goes straight to the new front card instead of keeping a position that counted the old cards; and a `recompose` prop that lays the ring and its lens flare over the real width of a wide viewport instead of running the outermost flare column on to the edge. Its licence is not stated in the source: check it before selling Sorph. |
| `src/liquid-glass-logo-reveal.tsx` | Glass Reveal from 21st.dev; shader and timeline ported from zanwei/glass-icon-reveal (MIT). Changed in three places (marked `Sorph:`): `GlassIconReveal` is exported, a `source` prop draws a live canvas into the logo's shape on every frame, and the engine itself (`startEngine`, `loadLogo`, `LOOKS`, `BOX`) is exported for the website's intro. |
| `src/sphere.js` | Sorph's orb, the shader of the dictation sphere: a copy of the website's sphere shader (the former `docs/demo/sphere.js`) that can draw off the page and be stopped. At startup it is the `source` of the glass reveal, stirred once and settling to its calm flow. |
| `src/site-intro.ts` | the website's intro (`docs/intro.js`, built with `npm run build:site`, no React): the startup reveal played over the hero on the hero's own sphere, handing over to it as the glass lets go |
| `dist/orb.png` | the orb at 512 px, from `launcher/orb.png` |

The bar at the bottom and the settings tabs take their look (a near-black capsule, a light pill that slides under the chosen option, small index numbers) from 21st.dev's Segmented Mode Toggle. Only the look: it is drawn with the page's own CSS, the component itself is not in the build.

React (MIT) is bundled into `dist/dashboard.js`.
