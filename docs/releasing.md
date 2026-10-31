# Maintainer release procedure

This repository currently has an open development PR and no versioned release.
Do not create a release tag from a feature branch. A release is cut from a
reviewed commit on the default branch after the checks below pass.

## 1. Prepare the candidate

- Merge the reviewed pull request only after its full CI matrix is green.
- Start from a clean checkout of the default branch and record the exact commit
  SHA that will be released.
- Review [CHANGELOG.md](../CHANGELOG.md). Move the shipped items from
  **Unreleased** into a dated version section; leave new work under
  **Unreleased**.
- Add the version to [CITATION.cff](../CITATION.cff) and check that its
  `license: MIT` field still agrees with [LICENSE](../LICENSE).
- Confirm that GitHub identifies the repository as MIT-licensed and that the
  issue forms, security instructions, support links, and clone/install
  instructions are still accurate.

Use semantic version tags with a leading `v` (for example, `v0.1.0`). While
interfaces and supported platforms are still evolving, remain in the `0.x`
series. Do not imply cross-platform compatibility just because the Python test
matrix passes on several interpreter versions.

## 2. Required automated checks

The candidate commit must have a successful GitHub Actions run for every
configured Python version. The workflow covers:

- Python compilation and sample configuration validation;
- offline, hardware-independent regression tests;
- clean-home installer smoke tests for standalone CD, Discord-enabled CD,
  all-components, and custom XDG directories;
- shell syntax validation;
- systemd verification of the standalone and Discord-enabled unit profiles.

A local run of the same core checks is:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile \\
  core/bin/roaring-presenced core/bin/roaring-presence-doctor \\
  providers/audio-cd/bin/roaring-cd-presence \\
  providers/audio-cd/bin/roaring-cd-session \\
  providers/audio-cd/bin/roaring-cd-autoplay \\
  providers/audio-cd/bin/roaring-cd-player \\
  providers/audio-cd/bin/cd_paths.py \\
  providers/minecraft/bin/roaring-minecraft-presence \\
  tools/assets/bin/roaring-presence-art.py \\
  tools/assets/bin/roaring-presence-assets tests/test_regressions.py
bash -n install.sh providers/audio-cd/bin/roaring-presence-scan
shellcheck -S warning install.sh providers/audio-cd/bin/roaring-presence-scan
python3 -m json.tool config/config.sample.json >/dev/null
git diff --check
```

## 3. Required manual release checks

CI deliberately does not pretend to test optical drives, audio backends,
Discord clients, or graphical desktops. Record the actual machine, distro,
desktop/session, drive, client and package variants used for manual tests.

### Standalone audio-CD profile

- Install on a clean user account using only documented base dependencies.
- Run `roaring-presence-doctor --component cd-player` and resolve errors.
- Test an inserted disc, manual start, automatic udev start (when advertised),
  playback controls, track changes, MPRIS/media keys, pause/resume and eject.
- Test a disc without CD-Text, no network access, no MusicBrainz match, and
  unavailable optional Qt packages.
- Confirm no Discord core or Application ID is needed and that no idle global
  drive-polling daemon remains.

### Optional Discord integration

- Run `roaring-presence-doctor --component audio-cd` with the client running.
- Verify connection, publish/update/clear behavior, artwork, priority
  arbitration with Minecraft, and reconnection after the client restarts.
- Test each client/package combination independently before calling it
  supported. Record untested Flatpak/Snap/native variants as unverified.
- Confirm the standalone and Discord udev rules are not both installed.

### Updates and preservation

- Check that the updater detects a fast-forward update and reports an up-to-date
  checkout when appropriate.
- Test that a dirty or divergent checkout is refused without losing edits.
- Confirm an update preserves user configuration, uses the selected install
  profile, and restarts only services belonging to that profile.
- Confirm no root escalation, sandbox permission changes, or unrelated service
  modifications occur.

## 4. Tag and publish

After the checks above:

```bash
git status --short                 # must be empty
git switch main
git pull --ff-only
git tag -a v0.1.0 -m "roaring-presence v0.1.0"
git push origin v0.1.0
```

Replace the example version with the version actually recorded in the changelog
and citation metadata. Create a GitHub Release for that tag, paste the matching
changelog section, summarize tested Linux/client combinations, and list known
limitations. Do not attach user configurations, personal logs, generated cache
files, or machine-specific artifacts. GitHub's source archives are sufficient
until the project intentionally establishes a separate binary packaging
pipeline.

## 5. After publication

- Verify the release page points to the intended tag and commit.
- Verify the source archive contains LICENSE, changelog, support and install
  instructions, but no user data or generated caches.
- Update the compatibility/support matrix only for combinations actually
  exercised.
- Leave the next work under **Unreleased**.
