# Security Policy

Sorph listens to your microphone, watches for its hotkey in every app, and
types into whatever text field you are working in. It needs macOS
**Microphone**, **Accessibility** and **Input Monitoring** permissions to do
that, and it starts at login. We take that trust seriously, and we welcome
reports of anything that could break it.

## Supported versions

Only the latest release receives security fixes.

| Version         | Supported |
| --------------- | --------- |
| 0.9.x (latest)  | ✅        |
| older than 0.9  | ❌        |

To get the latest version, run `./update.sh` in your Sorph folder (or the
one-line updater in the [README](README.md)).

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub:
[**Report a vulnerability**](https://github.com/TrenchStrAvy/Sorph-Local-Multilingual-Transcription/security/advisories/new)
(Security tab → *Report a vulnerability*). Only the maintainer can see the
report.

Please include:

- your macOS version and Mac (Apple silicon or Intel)
- your Sorph version (the top entry of `CHANGELOG.md` in your Sorph folder)
- whether dictation, translate mode, hands-free lock or the cleanup pass
  was in use
- steps to reproduce, and what an attacker gains
- a proof of concept, if you have one

## What to expect

Sorph is maintained by one person, so these are commitments we can keep:

| Step                                   | Within   |
| -------------------------------------- | -------- |
| Acknowledgement of your report         | 7 days   |
| Initial assessment (valid? severity?)  | 14 days  |
| Fix released, or a plan agreed with you | 90 days  |

We will keep you updated, tell you when a fix ships, and publish a GitHub
Security Advisory for confirmed issues. Please give us up to 90 days before
public disclosure; if a fix is ready sooner, we will coordinate an earlier
date with you.

## Sorph's privacy model

Sorph's central promise is that **nothing you say leaves your Mac**. There is
no account, no API key, no server and no telemetry. Speech-to-text,
translation and cleanup all run locally.

Sorph only goes on the network to fetch its own code and models:

| When                                        | Host                       | What                                                     |
| ------------------------------------------- | -------------------------- | -------------------------------------------------------- |
| `install.sh` / `update.sh`                  | `github.com`, `raw.githubusercontent.com` | Sorph's source code                        |
| Install, or first use of a language model   | `huggingface.co`           | Whisper, M2M-100 and Gemma 3 weights, pinned to fixed revisions |
| Install, or first time translate mode is on | `github.com` (ggml-org/llama.cpp releases) | llama.cpp runtime, pinned to a release tag and verified by SHA-256 |

Any other network traffic, and especially any that carries audio,
transcripts or typed text, is a security bug and in scope below.

## Scope

**In scope**

- Audio, transcripts, translations or typed text leaving the Mac, or
  network traffic other than that listed above
- Text typed into the wrong app, window or field, or keystrokes captured
  outside a dictation
- Ways for another process or user to abuse Sorph's Microphone,
  Accessibility or Input Monitoring permissions (for example by injecting
  code into the Sorph runtime, its virtual environment or its launcher)
- `install.sh`, `update.sh` and the login item: unsafe paths, temporary
  files, permissions, the LaunchAgent plist, or running code from a
  location others can write to
- Downloaded models or binaries that could be swapped or tampered with
  without Sorph noticing
- Sensitive data written to logs or settings files with unsafe permissions
- Vulnerabilities on [sorph.me](https://sorph.me) with real impact (such as
  XSS or content injection)

**Out of scope**

- Wrong transcriptions or translations, or anything a language model says
- Attacks that need an attacker who already controls your macOS user
  account, has root, or has physical access to an unlocked Mac
- Bugs in upstream projects (faster-whisper, CTranslate2, llama.cpp,
  Gemma, Hugging Face Hub). Please report those to the project concerned,
  unless Sorph uses it in an unsafe way
- Modified or unofficial copies of Sorph
- Missing security headers, or other best-practice findings on the static
  website, without a demonstrated impact
- Output from automated scanners with no working proof of concept
- Social engineering, spam, or denial of service

## Safe harbor

We will not pursue or support legal action against anyone who researches
and reports a vulnerability in good faith under this policy. That means:
staying in scope, testing only on your own Mac and data, not accessing
other people's data, and giving us reasonable time to fix the issue before
disclosure.

## Credit

With your permission, we will thank you by name (or handle) in the GitHub
Security Advisory and in the release notes of the version that fixes the
issue. Sorph is a free project and does not offer a paid bug bounty.
