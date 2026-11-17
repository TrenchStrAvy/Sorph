"""Where Sorph's speech models come from.

faster-whisper's own model files (Systran/faster-whisper-*) store their
weights as 16-bit floats; Sorph runs them as 8-bit integers, so half of
every download was thrown away at load time. The models Sorph installs by
default are therefore published already quantized to 8 bits: the same
OpenAI Whisper weights (MIT), converted with CTranslate2's own converter
(`--quantization int8`), at half the size. Each is pinned to a commit so
the files can never change under an installed Sorph.

path(name) is what flow.py loads. It never touches the network when a
copy is on disk, and an install from before the 8-bit files keeps using
the 16-bit copy it already has instead of downloading again.
"""

FILES = ["config.json", "preprocessor_config.json", "model.bin",
         "tokenizer.json", "vocabulary.*"]

# name → (Hugging Face repo, commit)
MODELS = {
    "small.en": ("trenchstravy/faster-whisper-small.en-int8",
                 "e929a0a9a2a1e26dcf2ecc6b0cd4ad5519a43e4c"),
    "small": ("trenchstravy/faster-whisper-small-int8",
              "172b3af35dbb7f160ebdf63c0287b73b8e7525e1"),
    "base": ("trenchstravy/faster-whisper-base-int8",
             "454e4567783c647564ce6befe61c854e87f0ab7f"),
}


def _snapshot(repo: str, revision, local_only: bool) -> str:
    from huggingface_hub import snapshot_download
    return snapshot_download(repo, revision=revision, allow_patterns=FILES,
                             local_files_only=local_only)


def _original(name: str, local_only: bool) -> str:
    from faster_whisper.utils import download_model
    return download_model(name, local_files_only=local_only)


def cached(name: str):
    """The folder of a copy of `name` that is on disk already (8-bit, else
    an older install's 16-bit one), or None."""
    if name in MODELS:
        try:
            return _snapshot(*MODELS[name], local_only=True)
        except Exception:
            pass
    try:
        return _original(name, local_only=True)
    except Exception:
        return None


def path(name: str) -> str:
    """What to hand to WhisperModel for `name`: a folder on disk,
    downloading the model first when there is none. Names Sorph does not
    publish itself (medium, a path, a repo id) pass through unchanged."""
    found = cached(name)
    if found:
        return found
    if name not in MODELS:
        return name
    try:
        return _snapshot(*MODELS[name], local_only=False)
    except Exception as exc:
        print(f"warning: could not fetch the 8-bit {name} model ({exc}); "
              f"using faster-whisper's own", flush=True)
        return _original(name, local_only=False)
