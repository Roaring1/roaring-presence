# Presence asset tools

These are local, one-shot commands. They do not run as services, store Discord
credentials, or upload anything automatically.

## Generic image packer

`roaring-presence-assets` accepts common image formats supported by Pillow.
Each input is prepared as a square PNG. Give an explicit key using
`KEY=IMAGE`, or let the source filename become the key:

```bash
roaring-presence-assets --output-dir ./presence-assets --fit contain \
  "profile=~/Pictures/profile.webp" \
  "game-cover=~/Pictures/game-cover.jpg" \
  ~/Pictures/wordmark.png
```

The output contains `profile.png`, `game-cover.png`, `wordmark.png`, and
`manifest.json`. Asset keys are normalized to lowercase ASCII, punctuation
becomes hyphens, and duplicate keys are rejected.

- `--fit contain` (default) preserves the full source and centers it on a
  transparent canvas.
- `--fit cover` crops to fill the square.
- `--background '#14151b'` chooses a solid canvas for `contain`.
- `--size 1024` sets the square edge; values up to 4096 are accepted.
- `--overwrite` explicitly replaces existing pack files.

The manifest gives the exact filename/key pairs and upload steps.

## Built-in artwork

`roaring-presence-art.py` generates a sample CD/Minecraft asset set plus an
application icon and contact sheet:

```bash
roaring-presence-art.py --output-dir ~/Pictures/presence-art --size 1024
roaring-presence-art.py --output-dir ~/Pictures/presence-art --key-prefix my-app --size 1024
```

It writes `manifest.json` with the Rich Presence asset keys and the matching
`config.assets` object. The application icon is separate from Rich Presence
asset entries.

## Uploading

Open the Discord Developer Portal and select your application:
**Rich Presence → Art Assets**. Upload the generated PNG files, using the
manifest's exact key for each uploaded item. Discord asset keys are selected by
the activity payload; the config must use the same names.

This workflow is generic: the tools do not assume a particular Application ID
or a set of fixed keys. Upload remains a manual Developer Portal action; the
project does not ask for an account token or claim to invoke a private upload
API.

Pillow is required. On Fedora/Nobara, install the system package with
`sudo dnf install python3-pillow`.
