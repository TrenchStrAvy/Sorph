#!/bin/zsh
# Sorph installer — offline, multilingual dictation for macOS.
#
#   git clone https://github.com/TrenchStrAvy/Sorph-Local-Multilingual-Transcription.git sorph
#   cd sorph && ./install.sh
#
# What it does (all local; nothing is sent anywhere):
#   1. checks macOS + Python 3.10+
#   2. creates .venv and installs the Python dependencies
#   3. pre-downloads the speech models (0.6 GB) so the first dictation is
#      instant in every language, and the llama.cpp runtime (30 MB) that
#      translate mode runs on. The Gemma 3 weights (2.5 GB) are downloaded
#      the first time you turn translate mode on. No Ollama, no Homebrew.
#   4. optionally sets up the cleanup pass (downloads Gemma 3 now)
#   5. builds a named "Sorph" runtime app so macOS privacy settings show
#      Sorph (not "Python"), puts a Sorph launcher in /Applications
#      and Launchpad, and installs a LaunchAgent that starts it at login
#
# Flags:
#   --translate        download the 2.5 GB translation model now instead of
#                      the first time translate mode is turned on (and on
#                      an install that was made with --no-translate)
#   --no-translate     never download the 2.5 GB translation model.
#                      Translate mode then uses a smaller, rougher one
#                      (490 MB, fetched when first turned on). Remembered
#                      for updates.
#   --with-cleanup     enable the punctuation/filler cleanup pass. It runs
#                      on the translation model, which is downloaded now.
#   --multilingual     accepted for older commands; the multilingual
#                      speech models are always installed now
#   --no-service       set up the venv and models only; don't install the
#                      runtime, launcher, or login service
#   --model NAME       whisper model to pre-download (default: small.en)
#
# Re-running is safe: the venv, models, and an existing LocalFlow runtime
# (with its permission grants) are reused.

set -euo pipefail

multilingual=false
translate=default      # default | yes (--translate) | no (--no-translate)
with_cleanup=false
no_service=false
model=small.en
label=com.localflow.dictation
support_root="$HOME/Library/Application Support/LocalFlow"
runtime_app="$support_root/Runtime/LocalFlow.app"
visible_app=/Applications/Sorph.app

while (( $# > 0 )); do
  case $1 in
    --multilingual) multilingual=true; shift ;;
    --translate)    translate=yes; shift ;;
    --no-translate) translate=no; shift ;;
    --with-cleanup) with_cleanup=true; shift ;;
    --no-service)   no_service=true; shift ;;
    --model)        model=$2; shift 2 ;;
    -h|--help)      sed -n '2,36p' "$0"; exit 0 ;;
    *) print -u2 "unknown flag: $1 (see --help)"; exit 64 ;;
  esac
done

say()  { print -P "%F{cyan}▸%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
warn() { print -P "%F{yellow}!%f $*"; }
die()  { print -u2 -P "%F{red}✗%f $*"; exit 1; }

root=${0:A:h}
cd "$root"

# 1. platform ----------------------------------------------------------------
[[ $(uname -s) == Darwin ]] || die "Sorph supports macOS only"

python=$(command -v python3 || true)
[[ -n $python ]] || die "python3 not found — install it from python.org or 'brew install python'"
pyver=$("$python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
"$python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Python 3.10+ required (found $pyver)"
ok "macOS, Python $pyver"

# 2. virtualenv + deps -------------------------------------------------------
if [[ ! -x .venv/bin/python ]]; then
  say "creating virtual environment"
  "$python" -m venv .venv
fi
say "installing Python dependencies"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
ok "dependencies installed"

# 3. models ------------------------------------------------------------------
fetch_model() {
  say "downloading speech model '$1' (once; cached in ~/.cache/huggingface)"
  .venv/bin/python - "$1" <<'EOF'
import sys
import speech
from faster_whisper import WhisperModel
WhisperModel(speech.path(sys.argv[1]), device="cpu", compute_type="int8")
EOF
  ok "model '$1' ready"
}
# everything a dictation loads, in any language, so nothing is fetched
# later: the model for English, its multilingual sibling for every other
# language, and the small multilingual one behind the live preview
[[ $translate == default && -e "$support_root/no-translate-model" ]] && translate=no
fetch_model "$model"
[[ $model == *.en ]] && fetch_model "${model%.en}"
fetch_model base

# translate mode: Sorph's own Gemma (see gemma.py). Its runtime is small
# and installed now; the 2.5 GB of weights wait until translate mode is
# first turned on, unless --translate or --with-cleanup wants them now. A
# --no-translate install stays without them on re-runs and updates.
opt_out="$support_root/no-translate-model"
gemma_now=false
{ [[ $translate == yes ]] || $with_cleanup; } && gemma_now=true
service_args=()
if $gemma_now; then
  say "downloading the language model (llama.cpp runtime + Gemma 3, 2.5 GB, once)"
  if .venv/bin/python -c 'import sys, gemma; sys.exit(0 if gemma.install(lambda m: print("  " + m, flush=True)) else 3)'; then
    ok "language model ready"
  else
    gemma_now=false
    warn "language model not installed; translate mode will use the smaller M2M100 model"
  fi
elif [[ $translate == no ]]; then
  [[ -e $opt_out ]] || { mkdir -p "$support_root" && : >"$opt_out"; }
  ok "translation model switched off (turn it on with ./install.sh --translate)"
elif .venv/bin/python -c 'import sys, gemma; sys.exit(0 if gemma.installed() else 3)'; then
  ok "translation model already installed"
elif ! .venv/bin/python -c 'import sys, gemma; sys.exit(0 if gemma.supported() else 3)'; then
  warn "translate mode will use the smaller M2M100 model on this macOS"
else
  .venv/bin/python -c 'import gemma; gemma.install_runtime(lambda m: print("  " + m, flush=True))' \
    || warn "couldn't fetch the llama.cpp runtime now; it will come with the model"
  ok "translate mode ready (its 2.5 GB model downloads the first time you turn it on)"
fi

# 4. optional cleanup pass ---------------------------------------------------
# Runs on the same Gemma as translate mode. Installs from before Sorph ran
# Gemma itself used an Ollama: that still works where Gemma cannot run.
if $with_cleanup; then
  if $gemma_now; then
    service_args=(--cleanup)
    ok "cleanup pass enabled"
    if command -v ollama >/dev/null && ollama list 2>/dev/null | grep -q '^gemma3:4b'; then
      warn "Ollama's gemma3:4b is no longer used by Sorph; 'ollama rm gemma3:4b' frees 3.3 GB"
    fi
  elif command -v ollama >/dev/null; then
    say "pulling gemma3:4b for Ollama (3.3 GB, once)"
    ollama pull gemma3:4b
    service_args=(--ollama)
    ok "cleanup pass enabled (through Ollama)"
  else
    warn "cleanup pass not enabled: it needs macOS 13.3 or later"
  fi
fi

if $no_service; then
  print
  ok "done. Run it with:  .venv/bin/python flow.py ${service_args[*]}"
  exit 0
fi

# 5a. named runtime app ------------------------------------------------------
# A copy of the Python framework's Python.app, renamed to LocalFlow and
# re-signed. macOS then lists "LocalFlow" in Microphone / Accessibility /
# Input Monitoring instead of "Python", and grants survive reinstalls
# because the bundle is kept once created.
bundle_id() { /usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist" 2>/dev/null; }

build_runtime() {
  local base src tmp
  base=$(.venv/bin/python -c 'import sys; print(sys.base_prefix)')
  src="$base/Resources/Python.app"
  [[ -d $src ]] || { warn "no Python.app at $src; using plain python for the service"; return 1; }
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/localflow-runtime.XXXXXX")
  /usr/bin/ditto "$src" "$tmp/LocalFlow.app"
  mv "$tmp/LocalFlow.app/Contents/MacOS/Python" "$tmp/LocalFlow.app/Contents/MacOS/LocalFlow"
  local pb=/usr/libexec/PlistBuddy plist="$tmp/LocalFlow.app/Contents/Info.plist"
  $pb -c 'Set :CFBundleExecutable LocalFlow' "$plist"
  $pb -c 'Set :CFBundleIdentifier com.localflow.app' "$plist"
  $pb -c 'Set :CFBundleName Sorph' "$plist"
  $pb -c 'Set :CFBundleDisplayName Sorph' "$plist" 2>/dev/null \
    || $pb -c 'Add :CFBundleDisplayName string Sorph' "$plist"
  $pb -c 'Set :LSUIElement true' "$plist" 2>/dev/null \
    || $pb -c 'Add :LSUIElement bool true' "$plist"
  $pb -c 'Add :NSMicrophoneUsageDescription string "Sorph transcribes your dictation locally using the microphone."' "$plist" 2>/dev/null \
    || $pb -c 'Set :NSMicrophoneUsageDescription "Sorph transcribes your dictation locally using the microphone."' "$plist"
  install_icon "$tmp/LocalFlow.app"
  /usr/bin/codesign --force --deep --sign - --timestamp=none "$tmp/LocalFlow.app" >/dev/null 2>&1
  # the stub must still find its framework from the new location
  if ! "$tmp/LocalFlow.app/Contents/MacOS/LocalFlow" -c 'import sys' >/dev/null 2>&1; then
    warn "relocated Python.app can't start; using plain python for the service"
    rm -rf "$tmp"; return 1
  fi
  mkdir -p "$support_root/Runtime"
  rm -rf "$runtime_app"
  mv "$tmp/LocalFlow.app" "$runtime_app"
  rm -rf "$tmp"
}

install_icon() {
  # the sphere on a white rounded square, for the permission panes. Only
  # for a freshly built runtime: changing an installed bundle changes its
  # signature and macOS forgets the permissions granted to it.
  local app=$1
  scripts/make-icns.sh "$app/Contents/Resources/LocalFlow.icns" 2>/dev/null || return 0
  /usr/libexec/PlistBuddy -c 'Set :CFBundleIconFile LocalFlow.icns' "$app/Contents/Info.plist" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string LocalFlow.icns' "$app/Contents/Info.plist"
  touch "$app"
}

if [[ -d $runtime_app && $(bundle_id "$runtime_app") == com.localflow.app ]] \
   && "$runtime_app/Contents/MacOS/LocalFlow" -c 'import sys' >/dev/null 2>&1; then
  ok "reusing existing LocalFlow runtime (permissions preserved)"
  runtime_ok=true
  runtime_kept=true
elif build_runtime; then
  ok "built LocalFlow runtime at $runtime_app"
  runtime_ok=true
else
  runtime_ok=false
fi

if $runtime_ok; then
  program="$runtime_app/Contents/MacOS/LocalFlow"
  site=$(.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')
  # the name macOS shows in the privacy panes is the runtime's own display
  # name: Sorph for new runtimes, LocalFlow for ones built before the rename
  perm_name=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleDisplayName' "$runtime_app/Contents/Info.plist" 2>/dev/null || echo Sorph)
else
  program="$root/.venv/bin/python"
  site=""
  perm_name="Python"
fi

# 5b. Launchpad launcher -----------------------------------------------------
# A tiny signed Swift app: clicking it starts the service (or leaves it
# running) and exits. Needs the Xcode Command Line Tools for swiftc.
if command -v swiftc >/dev/null; then
  tmp_launcher=$(mktemp -d "${TMPDIR:-/tmp}/localflow-launcher.XXXXXX")/Sorph.app
  if scripts/build-launcher.sh "$tmp_launcher" >/dev/null 2>&1; then
    if [[ -d $visible_app && $(bundle_id "$visible_app") != com.localflow.launcher ]]; then
      warn "$visible_app exists but isn't the Sorph launcher; leaving it alone"
    elif rm -rf "$visible_app" 2>/dev/null && mv "$tmp_launcher" "$visible_app" 2>/dev/null; then
      ok "installed launcher: $visible_app (also in Launchpad)"
    else
      warn "couldn't write $visible_app; skipping the Launchpad launcher"
    fi
  else
    warn "launcher build failed; skipping the Launchpad launcher"
  fi
  rm -rf "${tmp_launcher:h}"
else
  warn "swiftc not found (xcode-select --install); skipping the Launchpad launcher"
fi

# 5c. login service ----------------------------------------------------------
plist=$HOME/Library/LaunchAgents/$label.plist
if [[ -f $plist ]] && ! grep -q "$root/flow.py" "$plist"; then
  print
  print "A LaunchAgent for $label already exists and points elsewhere:"
  print "  $plist"
  print "Leaving it untouched. Remove it and re-run, or use --no-service."
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
say "writing $plist"
{
  cat <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$program</string>
    <string>$root/flow.py</string>
EOF
  for a in "${service_args[@]}"; do print "    <string>$a</string>"; done
  cat <<EOF
  </array>
  <key>WorkingDirectory</key><string>$root</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key><string>1</string>
EOF
  [[ -n $site ]] && print "    <key>PYTHONPATH</key><string>$site</string>"
  cat <<EOF
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/local-flow.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/local-flow.log</string>
</dict>
</plist>
EOF
} >"$plist"
plutil -lint "$plist" >/dev/null

target=gui/$(id -u)/$label
launchctl bootout "$target" >/dev/null 2>&1 || true
for _ in {1..50}; do   # bootout is asynchronous; wait until it's gone
  launchctl print "$target" >/dev/null 2>&1 || break
  sleep 0.1
done
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl kickstart -k "$target"
ok "service installed and started (log: ~/Library/Logs/local-flow.log)"

if [[ -n ${SORPH_UPDATE:-} && ${runtime_kept:-false} == true ]]; then
  # an update that kept the runtime kept its permissions: nothing to grant
  print
  print "Sorph restarted with the new version. Hold Right-Option, speak, release."
  exit 0
fi

cat <<EOF

Next: grant permissions once, then restart local-flow.
  System Settings → Privacy & Security →
    • Microphone        → allow "$perm_name"
    • Accessibility     → add and enable "$perm_name"
    • Input Monitoring  → add and enable "$perm_name"
  Then click Sorph in Launchpad, or run:
    launchctl kickstart -k gui/\$(id -u)/$label

Hold Right-Option, speak, release. Look for the mic icon in the menu bar.
EOF
