# Tests

What each test script checks and how to run it. The overview (the two sets, how long they take, what cost time
to find out) is in [architecture.md](architecture.md#tests).

The tests drive a real, hidden game through the author's dev kit (`dk`) and read the unmodded numbers from a
decompiled copy of the game. Neither is in this repository, so they run only in the author's workspace. Paths
below are from the workspace folder.

## run.py

Runs the checks in hidden games. One line per step on stdout, the cases in `tests/out/<set>/`.

```
python true_attack_speed/tests/run.py core [editor] [exe] [nodlc]      # default: all three
python true_attack_speed/tests/run.py exhaustive
```

**core**: what is most likely to break, in about 6 minutes per mode.

| Step | What it runs |
|---|---|
| cadence | Two fast weapons (Gatling Laser IV, SMG I), two slow ones (Pistol I, Hatchet I) and the two with a shooting state of their own (Whip I, Boomerang I) at a few Attack Speed values. |
| chain | Ball and Chain's minimum of 45 ticks. |
| crystal | Two weapons with Crystal (+1% Attack Speed every second until the player is hit), so Attack Speed changes in the middle of cycles and the game recalculates the stats every second, which cuts cooldowns. Not in `nodlc`: the item is from the first DLC. |
| turrets | Structure attack speed from no item, Clockwork Wasp, Improved Tools and the stat, and one of every structure built on the turret script. |
| card | The cooldown line on the weapon card. |
| errors | Script errors in the game's log. |

Modes: `editor` (the decompiled project, what changes are tried in), `exe` (the real game with the zipped mod
and all DLC) and `nodlc` (the real game as if no DLC were owned). The real exe needs Steam running.

**exhaustive**: everything else, about an hour and a half. Every weapon of the game at its lowest tier, other
frame rates, the limits, recalculated stats, co-op, hits per attack, Improved Tooltips, and more cases in the
real exe. Meant to run in the background; it only has to say "PASS" at the end.

## cadence.py

Attack cadence with the mod, measured against the rule in `timing.gd`.

```
python cadence.py [--weapons a,b] [--as=-50,0,100,300] [--fps 30,60v,144] [--secs N] [--items a,b] [--out FILE]
```

Needs a hidden game started on `tests/scenarios/tas_grid.json`. One weapon, manual aim, no enemies, so the
weapon attacks whenever its cooldown allows. A recorder gives the tick of every shot and the cooldown the weapon
holds after it. One line per case on stdout, raw JSON lines to `--out` (default `tests/out/cadence.jsonl`).

At +0% Attack Speed the mod must equal the unmodded game at 60 FPS, exactly, per cycle:
`shooting ticks = period - ceil(drawn cooldown)`.

At any other Attack Speed every cycle is `(shooting ticks at +0% + cooldown ticks drawn at +0%) × factor`. The
mod's planner logs those two numbers, the cycle it wanted and the whole ticks it gave, per attack, so each of
these is checked exactly, per cycle:

| Check | What must hold |
|---|---|
| base | The shooting ticks at +0% are the unmodded game's (`model.py` and `tas_rule.py`, from the `.tres` files). For the Boomerang the flight is only known within a few ticks, so 3 ticks are allowed. |
| draw | The cooldown ticks are inside the range the game draws from at +0%. |
| rule | Cycle wanted = (base + draw) × factor. |
| ticks | The ticks between two shots = the whole ticks the planner gave. |
| carry | Sum of ticks given minus sum of cycles wanted stays within 1 tick, or the weapon is at its limit (one attack per tick for a gun, 5 or 6 ticks for melee, 5 for Whip and Flail, the flight for a Boomerang). |
| card | `Timing.mean_cycle_ticks` (what the weapon card and other mods read) = unmodded mean at +0% × factor. |

Weapons whose stats are recalculated during a cooldown (see rule 4 in the architecture document): the Rail Gun
does it to itself every 5 seconds, the Sharp Tooth's missing-health bonus makes it happen every half second. The
planner keeps its cooldown through that and logs the ticks it took off; those cycles are checked with that
number. At +0% the game does the cutting itself, so for such a weapon a cycle may be shorter by what its draw
was above the cooldown stat.

The Drill gains Attack Speed by itself during a wave. Its cycles are checked at the Attack Speed the planner
used, which must lie between the one asked for and the one the weapon has at the end.

`--items` gives the player items. With `item_crystal` the Attack Speed changes during the case, as it does for
the Drill. With `item_padding` (Max HP for materials) the game recalculates the stats every half second without
changing them.

## turrets.py

Does structure attack speed scale a turret's whole cycle?

```
python true_attack_speed/tests/turrets.py [speeds] [variants] [--secs 12]
```

Needs a hidden game: on `tests/scenarios/tas_grid.json` with the mod, or on the workspace's `as_grid` scenario
without it, to see the unmodded numbers.

**speeds**: four turrets (`item_turret`) with enemies kept alive. Structure attack speed is changed the way a
player gets it: no item (0), Clockwork Wasp (+10), Improved Tools with Attack Speed +180 (+100) and -120 (-50),
then the stat itself for +300. With the mod, every cycle is checked against the mod's log:

| Check | What must hold |
|---|---|
| log | The cycle recorded from outside is the animation ticks plus the cooldown ticks the mod set. |
| base | The animation at structure attack speed 0 is 17 ticks and the cooldown it drew is within 0.7 to 1.3 times the cooldown stat. |
| rule | Animation + cooldown is within one tick of (base animation + base cooldown) × factor, and over all cycles of one turret the sum is within one tick (the fraction is carried). |

The mean of the cycles that had a target in time is also compared with the rule, within three standard errors of
the random cooldown draws. At 0, and without the mod, only that mean and the range of the draws are compared,
with the unmodded game's.

**variants**: one of each structure built on the turret script (garden, flame, laser, rocket, healing, Tyler,
wandering bot and so on). The script must be intact (this matters in the real exe, see "The Mod Loader and child
classes" in the architecture document) and those that shot must have been scaled.

## extra.py

Two situations `cadence.py` does not cover.

```
python extra.py [chain] [coop] [--weapons a,b] [--as 100,300] [--secs N]
```

Needs a hidden game on `tests/scenarios/tas_grid.json` (with the mod) or `as_grid` (without, to see the unmodded
numbers; the planner checks are skipped then). One line per case.

- **chain**: one weapon, the item Ball and Chain ("weapons have a minimum cooldown of 0.75s" = 45 ticks), manual
  aim, no enemies. With the mod and Attack Speed other than +0%: every cycle the planner gave is what was
  measured, and no cycle is under 45 ticks.
- **coop**: two players with the same weapon, player 1 at +0% and player 2 at another Attack Speed, real enemies
  kept alive (a co-op player without a gamepad cannot aim manually). Per player: the shortest cycle and the most
  common one against the rule for that player's Attack Speed, and the planner's cycles against the measured ones
  (a cycle may be longer than planned when the weapon has no target, never shorter).

## tas_rule.py

The mod's rule in Python, and the comparison with the unmodded game at 60 FPS. Not a live run: it is computed
from the weapons' `.tres` stats with the unmodded cycle model of the workspace's `research/attack_speed/model.py`.

```
python true_attack_speed/tests/tas_rule.py     # tests/out/rule_table.txt (all weapons, all tiers) and a short table
```

- `exact(w, atk)` is the mod's mean attack cycle in ticks for one held weapon: the unmodded cycle at +0% Attack
  Speed, divided by `1 + Attack Speed` above it, times `1 + |Attack Speed|` below it, never under the `LEAST`
  ticks of its kind. `cadence.py` and `extra.py` check the running game against it.
- `cycles()` gives the unmodded cycle (`"vanilla"`) and the rules that were considered before: `"fix"` (the
  shooting state at its nominal length, the Attack Timing Fix approach), `"P"` (the extra ticks a weapon has at
  +0% shrink with Attack Speed; version 0.2.0, never released), `"Pcap"` (the same, but never longer than
  unmodded; version 0.1.0) and `"D"` (only tweens shorter than one frame lose their extra frames).

## The other scripts

| File | What it does |
|---|---|
| `card.py`, `label_probe.gd`, `breakpoint_text_probe.gd` | What the weapon card shows in the shop, with and without Improved Tooltips. |
| `hits.py` | Hits per attack against real enemies, with and without the mod. Information, no verdict. |
| `showcase.py` | A visible game that walks through every kind of attack at several speeds, for judging the animations by eye. |
| `show_labels.py` | Prints one line per weapon from the outputs of `label_probe.gd` and `breakpoint_text_probe.gd`. |
| `turret_probe.gd` | The recorder `turrets.py` installs in the game. |
