# The Steam Workshop item

The mod's Workshop item is `3844942766`:
https://steamcommunity.com/sharedfiles/filedetails/?id=3844942766

| Part of the page | Where it comes from |
|---|---|
| Title, tags | `TITLE` and `TAGS` in `workshop/upload.py` |
| Description | `docs/workshop_description.txt` (Steam's BBCode) |
| Mod files | The zip of `mods-unpacked/vergir-TrueAttackSpeed/`, alone in a folder, named `vergir-TrueAttackSpeed-<version>.zip` |
| Thumbnail and the three graphs | `workshop/make_images.py` writes them to `workshop/out/` (not in git: they contain the game's icons and screenshots) |

## Uploading

The game's official way is the uploader tool of its `modding` beta branch, started from Steam. `workshop/upload.py`
does the same through the Steam interface that the game itself contains (GodotSteam's Workshop functions), so no
branch switch and no window is needed. It runs inside a hidden game started with the author's dev kit under the
logged-in Steam client, and Steam treats the calls as coming from the game.

```
dk run true_attack_speed/tests/scenarios/tas_grid.json --exe --detach --hidden
python true_attack_speed/workshop/upload.py --id 3844942766 --note "1.0.1: what changed"
python true_attack_speed/workshop/upload.py --id 3844942766 --visibility public
dk stop
```

- `--new` creates an item instead of updating one. A new item is private.
- Without other options an update sends the title, description, tags, the zip of the version in `manifest.json`
  (built before with `dk build vergir-TrueAttackSpeed`) and the thumbnail. `--no-text` and `--no-zip` leave those
  parts as they are on the page.
- `--gallery` adds the three graphs. It adds and never replaces, so use it once; replace a graph on the item's
  page.
- `--visibility` alone changes only who can see the item.
- `--note` is the change note shown on the item's "Change Notes" tab.

Steam answers each call with a result code; 1 is success. If it says the legal agreement still has to be
accepted, open the item's page while logged in and accept the Workshop terms there.

## Images

```
python true_attack_speed/workshop/make_images.py [double] [curve] [fps] [thumbnail]
```

It needs headless Edge, the workspace's decompiled game (font, icons) and two screenshots in `workshop/out/`:
`_wave.png` (a wave, blurred as the graphs' background) and `_potato_3.png` (a zoomed shot for the thumbnail).
The rates come from `tests/tas_rule.py`. Set `TAS_GAME_SRC` to read the weapons from another decompiled copy of
the game.
