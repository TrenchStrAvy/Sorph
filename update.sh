#!/bin/zsh
# Sorph updater — brings an existing install up to the latest version.
#
#   curl -fsSL https://raw.githubusercontent.com/TrenchStrAvy/Sorph/main/update.sh | zsh
#
# from anywhere (also for installs older than this script), or, in your
# Sorph folder:
#
#   ./update.sh
#
# It finds the Sorph folder the login service runs from, pulls the latest
# code into it (a folder unpacked from a ZIP becomes a git checkout the
# first time), and re-runs install.sh with the options you installed with.
# Your permissions, settings, models and virtual environment are kept, and
# the running Sorph is replaced, never doubled.
#
# Flags:
#   --dry-run   show what would happen; change nothing

set -euo pipefail

repo=${SORPH_REPO:-https://github.com/TrenchStrAvy/Sorph.git}
label=com.localflow.dictation
plist=$HOME/Library/LaunchAgents/$label.plist
dry_run=false

while (( $# > 0 )); do
  case $1 in
    --dry-run) dry_run=true; shift ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) print -u2 "unknown flag: $1 (see --help)"; exit 64 ;;
  esac
done

say()  { print -P "%F{cyan}▸%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
die()  { print -u2 -P "%F{red}✗%f $*"; exit 1; }

# 1. find the install ----------------------------------------------------------
# the folder the login service runs is the one that matters; a script run
# from its own folder (no service, --no-service install) updates that one
root=
installer_args=()
if [[ -f $plist ]]; then
  root=$(/usr/libexec/PlistBuddy -c 'Print :WorkingDirectory' "$plist" 2>/dev/null || true)
  # the service was installed with --with-cleanup iff it runs with --ollama
  /usr/libexec/PlistBuddy -c 'Print :ProgramArguments' "$plist" 2>/dev/null \
    | grep -q -- '--ollama' && installer_args+=(--with-cleanup)
else
  installer_args+=(--no-service)
fi
here=${0:A:h}
if [[ -z $root && -f $here/flow.py ]]; then
  root=$here
fi
[[ -n $root && -f $root/flow.py ]] || die "couldn't find your Sorph folder.
  Install fresh:  git clone $repo && cd Sorph && ./install.sh"
if [[ -f $here/flow.py && $here != $root ]]; then
  say "Sorph runs from $root; updating that copy, not $here"
fi
command -v git >/dev/null || die "git not found; install it with:  xcode-select --install"
ok "found Sorph in $root"

version() { git -C "$root" describe --tags --always 2>/dev/null || print "unknown"; }

# 2. pull the latest code ------------------------------------------------------
if [[ -d $root/.git ]]; then
  before=$(version)
  if [[ -n $(git -C "$root" status --porcelain --untracked-files=no) ]]; then
    die "you have local changes in $root; commit or stash them, then re-run"
  fi
  if $dry_run; then
    say "would pull the latest Sorph into $root (now $before)"
  else
    say "downloading the latest Sorph"
    git -C "$root" fetch --quiet --tags origin
    # the branch this folder follows; a folder that follows none (a ZIP
    # conversion that was cut short, a checked-out tag) gets the released main
    target=$(git -C "$root" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null) || target=origin/main
    git -C "$root" merge --quiet --ff-only "$target" \
      || die "couldn't fast-forward $root to $target; run 'git -C \"$root\" status' to see why"
  fi
else
  # unpacked from a ZIP: make it a checkout of the repo; files you don't
  # track (.venv, models) stay, Sorph's own files become the latest ones
  before="unknown (ZIP download)"
  if $dry_run; then
    say "would turn $root into a git checkout of $repo"
  else
    say "switching your ZIP copy to a git checkout so updates are one command"
    git -C "$root" init --quiet -b main
    git -C "$root" remote add origin "$repo"
    git -C "$root" fetch --quiet --tags origin
    git -C "$root" reset --quiet --hard origin/main
    git -C "$root" branch --quiet --set-upstream-to=origin/main
  fi
fi

# 3. reinstall in place --------------------------------------------------------
if $dry_run; then
  say "would run: ./install.sh ${installer_args[*]}"
  exit 0
fi
after=$(version)
(cd "$root" && SORPH_UPDATE=1 ./install.sh "${installer_args[@]}")

print
if [[ $before == $after ]]; then
  ok "Sorph is up to date ($after)"
else
  ok "Sorph updated: $before → $after"
fi
if [[ " ${installer_args[*]} " == *" --no-service "* ]]; then
  print "  Quit Sorph if it is running and start it again to use the new version."
fi
