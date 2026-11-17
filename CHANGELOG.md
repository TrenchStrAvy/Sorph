# Changelog

## v0.9.0 — 2026-11-17: Sorph light

Thank you for using Sorph. This release adds translation and a window
of its own, and still makes Sorph a smaller download than before: 0.8 GB
for dictation in every language.

### The light build

- **0.8 GB for all 99 languages.** The installer downloads what
  dictation needs and nothing else: the speech models (0.6 GB), a 13 MB
  runtime and the Python packages. In v0.7.0 the same took 1.4 GB, and
  part of it arrived mid-use, the first time you switched language. Now
  a language switch never downloads anything.
- **Speech models at half the size.** Sorph always ran its Whisper
  models at 8-bit precision but downloaded them at 16-bit. They are now
  published as 8-bit files. On 60 recordings each of English, German,
  French and Japanese they transcribe as accurately as before.
- **The translation model arrives when you want it.** Gemma 3 (2.5 GB)
  is downloaded the first time you turn translate mode on, with the
  progress shown in the menu bar and in Sorph's window. If you never
  translate, you never download it. `./install.sh --translate` fetches
  it during the install instead, for a Mac that will be offline.
- **One model for translating and cleaning up.** The optional cleanup
  pass (`--with-cleanup`) now runs on the same Gemma 3, so there is one
  copy of the model instead of two, and no Ollama or Homebrew to
  install.
- **Still offline.** Once a model is on your Mac, Sorph reads it from
  disk. Nothing you say leaves your computer.

| | v0.7.0 | v0.9.0 |
|---|---|---|
| Dictation, English only | 0.8 GB | 0.8 GB |
| Dictation, all 99 languages | 1.4 GB, part of it on first switch | 0.8 GB, all at install |
| Translate mode | not available | 2.5 GB, once, on first use |
| Cleanup pass | 3.3 GB through Ollama and Homebrew | shares the translation model |

### Translate mode

- **Speak one language, write another.** Menu bar → **Translate** →
  pick the language to write; **Language** stays the one you speak.
  Your words are typed as you speak, in your language, and replaced by
  the translation when you finish.
- **Any language to any language.** All 99 spoken languages translate
  into each other, plus 16 more that can only be written. Small
  languages come out rougher than large ones.
- **Sorph runs the model itself.** Gemma 3 on a small llama.cpp runtime:
  nothing to start, and its memory is given back when you turn
  translate mode off. Needs macOS 13.3 or later; on an older macOS, or
  with `./install.sh --no-translate`, a smaller model (490 MB) does the
  job more roughly.

### A window of its own

- **A dashboard.** Sorph now opens a small window: the orb revealed out
  of glass while the models load, then a gallery of cards, each a pair
  of languages to speak and to write. Turn to a card and Sorph switches
  to it; save your own pairs as cards.
- **Settings behind one button.** Microphone, music ducking, the
  dictionary and the rest, in one place.
- **Light and dark**, following macOS or set with the ◐ button. Menu
  bar → **Open Sorph**, or a click on Sorph in the Dock, brings the
  window back.

### Also new since v0.7.0

These were prepared as v0.8.0, which was never published on its own.

- **No more invented text.** A TV, music or a voice in the next room
  could make Sorph write sentences nobody dictated. Sorph now learns
  how loud your voice is on each microphone and drops what is not you.
- **A personal dictionary.** Add a word Sorph should know (`Ollama`),
  or a fix for one it mishears (`terror form = Terraform`).
- **Correct yourself out loud.** Say "Tuesday, actually no, Wednesday"
  and Sorph writes "Wednesday". "Scratch that" works too. English only
  for now.
- **Per-app tone.** A one-line dictation gets no final period in chat
  apps, terminals and code editors.
- **No more typing into Finder.** Live typing only goes into a real
  text field; anywhere else the words show in the card.
- **One-command updates.** See Upgrading below.
- **Ready for Muxpane** (coming soon): answer an agent by voice, in
  translate mode too.

### Fixes

- With the cleanup pass on, Sorph could freeze after you released
  Right-Option.
- On a new install, `flow.py --transcribe` failed with the newest
  version of an audio library. The installer now stays on one that
  works.

### Upgrading

One command, from anywhere, for any earlier version:

```bash
curl -fsSL https://raw.githubusercontent.com/TrenchStrAvy/Sorph/main/update.sh | zsh
```

It finds your Sorph, pulls v0.9.0 and reinstalls it in place. Your
permissions, settings and dictionary are kept, and you do not grant
anything again.

- **Your speech models are kept.** Sorph goes on using the ones you
  have. The update only fetches the ones you are missing, at their new
  size (0.3 GB at most).
- **If you used the cleanup pass with Ollama**, the update moves it to
  Sorph's own Gemma 3, a one-time 2.5 GB download. Afterwards
  `ollama rm gemma3:4b` frees 3.3 GB, if nothing else of yours uses it.
- **Translate mode** asks for its 2.5 GB model the first time you turn
  it on.

## v0.8.0 — 2026-11-14: only what you said

Thank you for using Sorph. This release writes what you said and nothing
else, learns your own words, and gets ready for Muxpane.

### What changed

- **No more invented text.** A TV, music or a voice in the next room
  could make Sorph write sentences nobody dictated. Sorph now learns how
  loud your voice is on each microphone, keeps quiet passages only when
  it is sure they are speech, and drops repeated loops and impossibly
  long outputs, in the live preview and in the final text.
- **A personal dictionary.** Menu bar → **Dictionary** → "Add word or
  name…". Add a word Sorph should know (`Ollama`), or a fix for one it
  mishears (`terror form = Terraform`). Click an entry to remove it.
- **Correct yourself out loud.** Say "Tuesday, actually no, Wednesday"
  and Sorph writes "Wednesday". "Scratch that" works too. English only
  for now; on by default, with a switch in the menu bar.
- **Per-app tone.** A one-line dictation gets no final period in chat
  apps, terminals and code editors, where it would end up in a message
  or a command. Documents and mail are closed with a period as before.
  On by default, with a switch in the menu bar.
- **No more typing into Finder.** Live typing now only goes into a real
  text field. Dictating with Finder or the Desktop in front no longer
  selects files and opens them in Quick Look; the words show in the card
  and land in the field you click into, or on the clipboard if there is
  none.
- **No hang with the cleanup pass.** With Ollama cleanup on, Sorph could
  freeze after you released Right-Option. Fixed.
- **One-command updates.** A single command brings any install up to
  date and keeps your permissions, settings, models and options. See
  Upgrading below.

### Works with Muxpane (coming soon)

Muxpane is a small floating terminal for tmux and Claude Code: it shows
every agent running in your panes, takes you to any of them with one
key, and reads their replies aloud. It is not released yet. Sorph is its
voice in the other direction, and this release is ready for it:

- **Answer an agent by voice.** While Muxpane reads a reply, or just
  after, hold Right-Option and speak. Your words are typed into
  Muxpane's reply field and sent to the session you just heard.
- **Dictate to any agent.** Mark an agent in Muxpane's agents tab, hold
  Right-Option, and what you say goes to that agent, without leaving
  the app you are in.
- **It listens when you speak.** While you dictate, Muxpane pauses its
  reading and holds its pings, and carries on when you are done.
- **Your typing stays yours.** Sorph marks the keys it types, so
  Muxpane can tell dictation from your own typing and gives the
  keyboard back the moment you type yourself.
- **Replies arrive as prompts.** New in this release: a reply dictated
  into Muxpane gets no final period, like a line typed into a terminal,
  and live typing lands only in a real text field such as Muxpane's.

Nothing to set up on the Sorph side: with both running, it works.

### Upgrading

One command, from anywhere:

```bash
curl -fsSL https://raw.githubusercontent.com/TrenchStrAvy/Sorph/main/update.sh | zsh
```

It finds your Sorph, pulls the latest version and reinstalls it in
place. Next time, `./update.sh` in your Sorph folder does the same.

## v0.7.0 — 2026-10-22: quiet, please

Thank you for using Sorph. This release lets the music step aside while
you speak.

### What changed

- **Music ducking.** When something is playing, whether Music, Spotify,
  a browser or a call, Sorph turns it down as you press Right-Option,
  before the mic opens, and glides it back after you release. It lowers
  the system volume, so it works with every app, and it only acts when
  something is actually playing.
- **A slider for how quiet.** Menu bar → **Music ducking** has a slider
  from silent to 100% of your current volume (default 20%) and a switch
  to turn ducking off. The slider remembers its spot while ducking is
  off.
- **Your volume wins.** If you change the volume yourself mid-dictation,
  Sorph keeps your change. If Sorph is stopped while the music is down,
  the next launch puts the volume back.
- **Smoother live typing.** When the live preview changes its mind about
  an earlier word, Sorph now fixes just that word, in place, instead of
  wiping the sentence and typing it all again. The cursor stays at the
  end while earlier words are corrected, and the cleanup pass after you
  release fixes capitals and commas the same way. In apps that don't
  allow in-place edits, such as terminals, Sorph steps back to the word
  with the arrow keys instead.
- **Pick your microphone.** Menu bar → **Microphone** lists every
  connected input next to the system default. The list is fresh each time
  you open it, the choice survives restarts, and if the chosen mic is
  unplugged Sorph records from the system default instead.

### Upgrading

```bash
cd sorph && git pull && ./install.sh
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```


## v0.6.0 — 2026-10-19: Sorph, verified

Thank you for using Sorph. This release gives it its name, its face, and
a way to know your copy is really ours.

### What changed

- **Verified releases.** From this release on, every Sorph release is
  cryptographically signed. GitHub shows it as **Verified**, and you can
  check it yourself with `git verify-tag v0.6.0`: proof that the code you
  install came from us and was not changed on the way.
- **Sorph has a name and a look.** A new logo and app icon: the orb in
  glass. The menu bar shows the sphere in colour, a white splash card
  greets you at launch, and the Dock shows the running dot while Sorph
  runs.
- **A livelier, steadier sphere.** It follows every syllable, glides back
  to rest in pauses, and no longer grows more agitated the longer it runs.
- **sorph.me.** A new website where the sphere moves with the words.

### Upgrading

```bash
cd sorph && git pull && ./install.sh
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```


## v0.5.0 — 2026-09-29: the sphere

Thank you for trying Sorph and for the feedback. This release is the
one you asked for most: something worth looking at while you speak.

### What changed

- **A liquid-glass sphere replaces the waveform.** A small ball of glass
  with three ribbons of light flowing inside, rendered on the GPU by a
  single Metal shader: refraction, dispersion, a studio reflection, a rim
  that catches the light, and a surface that breathes. Your voice bends
  the ribbons, speeds the flow, stirs the glass, and each syllable sends a
  pulse along the ribbons and the rim. It is translucent, so the desktop
  shows through, and reads on a light desktop as smoked glass.
- **It adapts to your voice.** The sphere tracks how loud you actually
  speak over the last few seconds and maps that to its normal response,
  so a quiet voice moves it as much as a loud one. Its response eases in
  over a quarter second and out over a second, never twitching.
- **Locked mode is visible.** The rim turns amber while dictation is
  locked on.
- **Put it where you want.** Menu bar → Sphere position: five presets, or
  Move freely to drag it anywhere on screen; Return or Done moving keeps
  the spot. `--position` on the command line. The choice persists.
- The particle sphere remains as a fallback when SceneKit is unavailable.

### Upgrading

```bash
cd sorph && git pull && ./install.sh
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```

The installer adds one dependency, the SceneKit binding (`pyobjc-framework-
SceneKit`), which the sphere needs.


## v0.4.0 — 2026-09-29: hands-free lock

Thank you for the feedback that shaped this release. Every fix below came
from a real dictation someone reported.

### What changed

- **Option+A locks dictation on.** Hold Right-Option, tap A, let go; tap
  Option+A again to finish. Speech is split into sentences on ~0.7 s pauses;
  each is cleaned up and committed, and committed text is never corrected
  again, so anything you type yourself stays intact.
- **Focus-aware delivery.** Switch apps while locked and dictation keeps
  listening; the words are typed the moment the original field has focus
  again, or at the end.
- **A fast model for the preview, the accurate one for the text.** The
  live preview now runs `base.en` (about 0.4 s per update, so words appear
  every half second); every committed or final sentence is decoded by
  `small.en`. Preview corrections are word-based: a comma the preview
  chose differently is left alone rather than retyping the line.
- **No more decoder stalls or loops.** Whisper's temperature-fallback
  ladder (up to six re-decodes on a chunk cut mid-word, 7 s stalls) is
  off; repeated phrases ("the the the") are cut at the first repeat; the
  preview decoder cannot repeat a trigram; an empty preview never deletes
  anything.
- **The app ignores its own keystrokes.** Typed words are tagged so the
  hotkey listener no longer mistakes them for Option+A or a language key.
- **No double paste.** Each dictation owns its typing state and its
  preview loop, and all keystrokes go through one lock, so a quick second
  press while a long dictation is still finalizing can no longer make it
  type the whole section again or interleave stale preview text.
- **Long dictations split at a pause.** Past the 24 s window the buffer is
  cut at the last short pause instead of mid-word, so no sentence gets a
  spurious full stop in the middle.

### Upgrading

```bash
cd sorph && git pull && ./install.sh
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```

The preview model (`base.en`, about 75 MB) downloads on first use.


## v0.3.0 — 2026-09-27: words as you speak

Thank you to everyone using Sorph and sending feedback. This release
comes directly from it.

### What changed

- **Live dictation.** While you hold Right-Option, recognized words are
  typed into your text field about 1.5 s behind your voice and corrected
  in place as more audio arrives. No more waiting for release to see
  anything. `--preview card` shows them in the overlay instead; `--preview
  off` restores the previous wait-then-paste behaviour.
- **Cleanup is now rule-based by default.** Filler words are removed and
  capitalization and end punctuation fixed, instantly and deterministically,
  right in your text. The v0.2.0 default (gemma3:1b) could echo its own
  instructions, so a dictation sometimes came out as "Keep it in English."
  It also occasionally rewrote sentences. Both are gone.
- **LLM cleanup is opt-in and guarded.** `--ollama` uses gemma3:4b again,
  streams its edits into your text as they are produced, and any answer that
  drops or invents content is discarded in favour of the transcript.
  `--ollama-model NAME` picks a different model.
- **Ellipses are pauses.** "keep the same... aesthetics" no longer gets a
  capital after the dots.

### Upgrading

```bash
cd sorph && git pull && ./install.sh
```

If your service was installed with `--with-cleanup`, re-run with that flag
to keep the LLM pass (it now needs gemma3:4b), or without it to use the
rule-based cleanup. Then restart:

```bash
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```

### Known limits

Live typing sends keystrokes to the focused field, so it pauses if you
click elsewhere while speaking and the final text goes back to the original
field on release. A hands-free locked mode is next.


## v0.2.0 — 2026-09-27: faster dictation

The time from releasing the key to text appearing in your document drops
from roughly 5–8 seconds to roughly 2–2.5 seconds on an Intel i9. Nothing
about privacy changed: everything still runs on your Mac.

### What was slow

Per-dictation timings from real use showed where the time went:

| Stage                          | Before          |
|--------------------------------|-----------------|
| faster-whisper (speech-to-text)| 1.3–2 s         |
| Ollama cleanup (gemma3:4b)     | 2.5–8 s         |

The optional cleanup pass cost more than the transcription itself, and
about a third of dictations hit its 8-second timeout, so you waited the
full 8 seconds and then got the raw transcript anyway.

### What changed

- **Cleanup model: gemma3:4b → gemma3:1b.** The 1B model fixes
  punctuation, capitalization and filler words just as well for this job
  and runs in about 1.3 s on CPU instead of 2.5–8 s. It is also a
  ~800 MB download instead of ~3 GB.
- **Cleanup timeout: 8 s → 4 s.** With the smaller model the ceiling on a
  bad day is half what it was.
- **Whisper uses all physical cores.** CTranslate2 defaulted to 4 threads;
  local-flow now passes the machine's physical core count.
- **Leaner decoding.** Segments no longer condition on previous text and
  silence trimming is slightly more aggressive. Together with the thread
  change this shaves roughly 10 % off the speech-to-text pass.

### Upgrading

```bash
cd local-flow
git pull
./install.sh --with-cleanup   # re-running is safe; pulls gemma3:1b
```

If you skip the installer, pull the new model yourself, otherwise the
cleanup pass silently falls back to raw transcripts:

```bash
ollama pull gemma3:1b
ollama rm gemma3:4b            # optional: reclaim 3 GB
```

Then restart the service:

```bash
launchctl kickstart -k gui/$(id -u)/com.localflow.dictation
```

### Known limits

Whisper `small.en` has a fixed cost of about 1.3 s per dictation on Intel,
regardless of clip length. `base.en` runs in about 0.5 s but is noticeably
less accurate, especially outside English. A live word-by-word preview
while you speak is under consideration for a future release.

## v0.1.0 — 2026-09-16: initial release

Offline multilingual dictation for macOS: hold Right-Option, speak,
release. faster-whisper on CPU, optional local Ollama cleanup, 99
languages with fast keys to switch mid-sentence, focus restore, menu bar
icon, floating waveform, login service and Launchpad launcher.
