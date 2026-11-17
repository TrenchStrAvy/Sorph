from __future__ import annotations

import unittest
from unittest import mock

import speech


class SpeechModelTests(unittest.TestCase):
    def test_every_default_model_is_pinned_to_a_commit(self) -> None:
        for name in ("small.en", "small", "base"):
            repo, revision = speech.MODELS[name]
            self.assertIn("/", repo)
            self.assertRegex(revision or "", r"^[0-9a-f]{40}$", name)

    def test_a_copy_on_disk_is_used_without_the_network(self) -> None:
        calls = []

        def snapshot(repo, revision, local_only):
            calls.append(local_only)
            return "/cache/8bit"
        with mock.patch.object(speech, "_snapshot", side_effect=snapshot), \
                mock.patch.object(speech, "_original") as original:
            self.assertEqual(speech.path("small"), "/cache/8bit")
        self.assertEqual(calls, [True])
        original.assert_not_called()

    def test_an_older_install_keeps_its_16_bit_copy(self) -> None:
        def snapshot(repo, revision, local_only):
            if local_only:
                raise OSError("not cached")
            raise AssertionError("must not download")
        with mock.patch.object(speech, "_snapshot", side_effect=snapshot), \
                mock.patch.object(speech, "_original",
                                  return_value="/cache/16bit") as original:
            self.assertEqual(speech.path("small.en"), "/cache/16bit")
        original.assert_called_once_with("small.en", local_only=True)

    def test_nothing_on_disk_downloads_the_8_bit_model(self) -> None:
        def snapshot(repo, revision, local_only):
            if local_only:
                raise OSError("not cached")
            return "/cache/new"
        with mock.patch.object(speech, "_snapshot", side_effect=snapshot), \
                mock.patch.object(speech, "_original",
                                  side_effect=OSError("not cached")):
            self.assertEqual(speech.path("base"), "/cache/new")

    def test_falls_back_to_the_original_when_ours_is_unreachable(self) -> None:
        def original(name, local_only):
            if local_only:
                raise OSError("not cached")
            return "/cache/systran"
        with mock.patch.object(speech, "_snapshot",
                               side_effect=OSError("gone")), \
                mock.patch.object(speech, "_original", side_effect=original):
            self.assertEqual(speech.path("base"), "/cache/systran")

    def test_other_models_pass_through(self) -> None:
        with mock.patch.object(speech, "_original",
                               side_effect=OSError("not cached")):
            self.assertEqual(speech.path("medium.en"), "medium.en")
            self.assertEqual(speech.path("/some/folder"), "/some/folder")


if __name__ == "__main__":
    unittest.main()
