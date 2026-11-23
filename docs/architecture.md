# Architecture

Technical documentation of True Attack Speed (`vergir-TrueAttackSpeed`) for whoever maintains it. Written for
Brotato 1.2.0.3 and checked again on 1.2.0.4 (which halved the Boomerang's cooldown; the numbers here are
1.2.0.4's), Godot 3.7 (GDScript 3), Godot Mod Loader 6.3.0. References such as `weapon_service.gd:231` are
to the game's own scripts.

Contents: [the rule](#the-rule) · [files](#files) · [how each kind is handled](#how-each-kind-is-handled) ·
[the Mod Loader and child classes](#the-mod-loader-and-child-classes) · [weapon card](#weapon-card) ·
[for other mods](#for-other-mods) · [tests](#tests) ([tests.md](tests.md)) · [release checklist](#release-checklist) ·
[known limits](#known-limits)

## The rule

Everything is counted in physics ticks: 60 per second at any frame rate.

### What the unmodded game does

One attack cycle of a weapon is a "shooting" state followed by a cooldown.

- **Shooting state, guns and melee.** It ends when a chain of tweens has finished (recoil out and back for guns;
  recoil, strike and return for melee). The tweens advance on rendered frames and each takes
  `floor(duration × FPS) + 2` frames. So the attack rate depends on the frame rate, and the 2 extra frames per
  tween never shrink. With positive Attack Speed the recoil duration is divided by `1 + Attack Speed`.
- **Shooting state, Whip and Flail** (`AnimatedHitboxShootingBehavior`): a "lash" animation of 0.48 s that runs
  on physics ticks, 28 ticks, with the hitbox open for 5 of them. Attack Speed does not change it.
- **Shooting state, Boomerang** (`BoomerangShootingBehavior`): lasts until every projectile of the throw has
  emitted `returned`. Attack Speed does not change it.
- **Cooldown.** The stat is `base / (1 + Attack Speed)` cut to whole ticks and never under 2 for positive Attack
  Speed, `base × (1 + |Attack Speed|)` for negative (`weapon_service.gd`, `apply_attack_speed_mod_to_cooldown`).
  Each attack draws its cooldown uniformly from `[max(1, cd − spread), cd + spread]`, where
  `spread = min(n × cd / 5, n × 5)` and `n` is the number of weapons held (1 to 6), and the weapon fires on the
  first tick where the cooldown has run out (`weapon.gd`, `get_next_cooldown`). The cooldown after the shot that
  triggers a long reload has no random spread.
- **Stats recalculated during a cooldown.** Whenever the player's stats change, the game makes new stats for
  every weapon and then cuts the cooldown that is left to the cooldown stat (`weapon.gd`, `init_stats(false)` →
  `reset_cooldown`). So a draw above the stat loses its extra. That happens far more often than "a stat
  changed" suggests: a player with a stat that follows materials, living enemies, burning enemies, living trees
  or missing health gets it every half second (`linked_stats.gd`, `update_for_player_every_half_sec`), the Rail
  Gun does it to itself every 5 seconds, and a Scythe showed it in the tests too (probably through its health
  drain; the cause was not traced).
- **Turrets** (`entities/structures/turret/turret.gd`): a cycle is the "shoot" animation (0.3 s, on rendered
  frames, 17 ticks at 60 FPS) plus a cooldown drawn from 0.7 to 1.3 times the cooldown stat. Structure attack
  speed (`WeaponService.get_structure_attack_speed`: the `structure_attack_speed` stat plus the
  `structures_cooldown_reduction` effects, such as Improved Tools' half of the player's Attack Speed) divides
  only the cooldown stat. The animation gets faster only once the cooldown is shorter than it, and at most 3
  times. The player's Attack Speed stat itself never reaches a structure or a pet (`weapon_service.gd:231`).

"Attack Speed" below is the player's stat plus the weapon's own modifier, as the game adds them, divided by 100.

### What the mod does

1. **At +0% Attack Speed** a cycle is the unmodded one at 60 FPS with vsync: the same shooting state and the
   cooldown the game draws. (With the game's "Limit FPS" option a tween whose duration is a whole number of
   frames takes one frame less than with vsync, so unmodded weapons are a little faster for players who use that
   option. The mod uses the vsync count for everyone.)
2. **At any other Attack Speed** a cycle is the +0% cycle times a factor, `1 / (1 + Attack Speed)` when positive
   and `1 + |Attack Speed|` when negative (`Timing.cycle_factor`, the game's own convention for the cooldown):

   ```
   cycle = (shooting ticks at +0% + cooldown ticks drawn at +0%) × factor
   shooting ticks at +0% = sum(floor(60 × D0) + 2) − 1      guns and melee; D0: the tween durations at +0%
                         = ceil(60 × animation length) − 1   Whip and Flail (28 ticks)
                         = the ticks the flight takes        Boomerang (about 71 for a Boomerang I)
   cooldown ticks at +0% = ceil of the game's random draw around the +0% cooldown stat
   ```

   The `− 1` for guns and melee: unmodded at 60 FPS the cooldown starts counting one tick before the last frame
   of the tween chain is over.

   A cycle is rarely a whole number of ticks. The fraction is carried to the next attack, so the mean is exact.
   The "+0% cooldown stat" comes from the game's own stat code run with the weapon's Attack Speed set to 0
   (`Timing.zero_speed_stats`), so everything else that changes a cooldown is in it.
3. **Turrets** get the same rule with structure attack speed in place of Attack Speed:
   `cycle = (17 + cooldown ticks drawn at 0) × factor` for the game's turrets. At structure attack speed 0
   nothing is changed.
4. **Stats recalculated during a cooldown.** The planned cooldown stays, with the limit the game means: it may
   not be longer than the cooldown of a cycle whose draw was exactly the +0% cooldown stat, at the Attack Speed
   the weapon has now. So a build whose stats are recalculated all the time loses the same share of its cycle
   as it does unmodded at +0%, and Attack Speed gained in the middle of a cooldown shortens the wait as it does
   unmodded. (Left to the game, the cut would be to the game's own cooldown stat: a Sharp Tooth at -50% attacked
   at the unmodded rate, and with positive Attack Speed cooldowns were cut that are longer than the game's only
   because the swing before them was shorter.)
5. **Limits.** A gun cannot attack more than once per tick (a Gatling Laser IV gets there at about +650%). A
   melee swing needs 1 tick per stage and 2 for the strike, so a thrust cycle is at least 5 ticks and a sweep
   cycle 6. A Whip or Flail cycle is at least 5 ticks (1 before the hitbox opens, 2 open, 1 after, 1 cooldown). A
   Boomerang cannot be thrown before it is back: 2 ticks. A turret keeps 1 tick of animation and 1 of cooldown.
   Ball and Chain's "minimum cooldown" (45 ticks) holds for the whole cycle. The constants are at the top of
   `timing.gd`.

### What that does to balance

Worth knowing before changing the rule:

- The unmodded game's steps are gone, including the one most weapons get from the very first point of Attack
  Speed (their recoil time is a whole number of frames at +0%, and the first point saves a frame per tween: SMG I
  +29%, Hatchet I +11%). Right after such a step the mod is slower than unmodded: SMG I up to 21% (at +1%; slower
  until about +80%), Gatling Laser IV up to 11% (at +21%), slow weapons 2 to 3%.
- The cooldown's 2-tick minimum is gone, so fast weapons keep gaining: Gatling Laser IV +47% over unmodded at
  +100% and +193% at +300%, SMG I +11% and +63%. Slow weapons gain 2 to 9% at +100% to +300%.
- Whip I: +51% over unmodded at +100%, +158% at +300%. Boomerang I: +82% and +245%.
- Negative Attack Speed costs more than unmodded. At -50%: Gatling Laser IV 24% fewer attacks than unmodded,
  SMG I 23%, Hatchet I 28%, Whip I 18%, Boomerang I 28%, Pistol I 7%.
- Turret with cooldown 32: +3.5% over unmodded at +10% structure attack speed, +27% at +100%, +33% at +300%; 12%
  fewer shots at -50%.

`tests/tas_rule.py` computes the comparison for every weapon and writes it to `tests/out/rule_table.txt`.

## Files

```
mods-unpacked/vergir-TrueAttackSpeed/
	manifest.json
	mod_main.gd          installs the script extensions
	timing.gd            the rule as static functions; the only file other mods should call
	cycle_planner.gd     one per weapon: plans each cycle in whole ticks and carries the fraction
	extensions/weapons/shooting_behaviors/ranged_weapon_shooting_behavior.gd     guns, and the Boomerang
	extensions/weapons/shooting_behaviors/melee_weapon_shooting_behavior.gd      melee
	extensions/weapons/shooting_behaviors/animated_hitbox_shooting_behavior.gd   Whip and Flail
	extensions/entities/structures/turret/turret.gd                              turrets
	extensions/ui/menus/shop/item_description.gd                                 weapon card
```

An extension sits at the same relative path as the game script it extends.

## How each kind is handled

**The planner** (`cycle_planner.gd`). For each attack at an Attack Speed other than +0%: `plan(weapon,
base_shooting, atk_spd)` draws the +0% cooldown and works out the cycle in whole ticks, `commit(shooting_ticks)`
says how long the shooting state really takes, `apply(weapon)` puts the cooldown that is left on the weapon.
`guard(weapon, delta)`, called first thing on every physics tick by each behaviour, looks after that cooldown:
it knows what the weapon's `_current_cooldown` must be on this tick (the weapon comes before its behaviour in a
tick and counts down only while it is not shooting), and when `current_stats` is a new object the game has
recalculated the stats and cut the cooldown, so it writes back the expected value, limited as rule 4 says.
A change it cannot explain (another mod, the effects in `main.gd` that make a weapon ready at once) is left
alone. With `log_enabled` the planner keeps `[base shooting, base cooldown, target, given, Attack Speed, ticks
cut by the guard]` per cycle for the tests.

Two details of the planner. A cycle that cannot be as short as wanted (one attack per tick, the shortest melee
swing) does not pile up a debt: the carried fraction never goes under -1 tick. And the +0% stats of a weapon
are cached by the instance id of its `current_stats`, because the game makes a new `current_stats` object
whenever the player's stats change.

**Guns** (`ranged_weapon_shooting_behavior.gd`). The recoil is only an animation; the shooting state is a tick
counter. With positive Attack Speed the shooting state gets the game's own durations plus the extra ticks of +0%
divided by `1 + Attack Speed`, at most the cycle minus 1 tick; the cooldown is the rest. Recoil out and back is
one tween that nothing waits for. At a low frame rate the next shot can come before it is over, so it always
starts again from the rest position.

**Melee** (`melee_weapon_shooting_behavior.gd`). The same 3 or 4 moves as stages of whole ticks. The weapon's
tween runs on physics ticks so the hitbox moves in step with the collision checks. A stage's length is turned
into whole ticks with the fraction carried to the next stage. Every stage lasts at least 1 tick and the one that
ends the strike at least 2, so that the hitbox is checked at its final position before it is switched off. With
Attack Speed other than +0% the swing may take all of the planned cycle but 1 tick, which stays for the
cooldown. Within a stage the move is over one tick before the stage ends, as it is unmodded (a tween finishes
one frame before its completion signal); half a tick is taken off the tween's duration so that rounding cannot
make it late.

**Whip and Flail** (`animated_hitbox_shooting_behavior.gd`). The animation plays as it is while it fits into the
cycle minus 1 tick. When the cycle is shorter, the extension reads from the animation's method track when the
hitbox opens and closes and steps the animation itself: `AnimationPlayer` in manual mode, one `seek(position,
true)` per tick, which applies value tracks but calls no method tracks and emits no `animation_finished`. The
hitbox stays open for its unmodded 5 ticks while there is room (at least 2), so a faster swing reaches the same
enemies; the parts before and after it get shorter in proportion. While the extension steps the animation, the
calls the animation itself makes (`open_hitbox`, `close_hitbox`, `_on_animation_finished`) are ignored.

**Boomerang.** It has no extension of its own (see the next section). Its behaviour script inherits from the gun
behaviour and replaces `shoot()` without calling it, but the engine calls `_physics_process` on every script
level, so the gun extension sees the flight (`"_projectiles_in_flight" in self`). With positive Attack Speed it
calls the projectile's own `_physics_process` for extra steps: `1 + Attack Speed` steps of flight per tick (2.5 =
2 and 3 in turn), each a whole unmodded step, so the flight is the same path played faster. It connects to the
projectile's `returned` signal and plans the cycle when the last projectile is back, so that flight plus cooldown
is the cycle. With negative Attack Speed the flight is unmodded and the cooldown takes all of the extra time.
Signal slots are not called in connection order, so the handler counts the remaining projectiles itself instead
of relying on the game's handler having run.

The order within one tick, measured: the weapon, the behaviour, then the projectile; the throw itself happens
between two ticks. So when the catch comes, the projectile's own step of that tick has been taken, unless the
catch came in one of the extra steps. The number of steps the flight took is the ticks it takes at +0%, which
is the base of the cycle.

For the weapon card the flight is estimated (`Timing.boomerang_flight_ticks`): the game's flight
(`boomerang_projectile.gd`: out, apex, back) stepped tick by tick for a player who stands still and a target at
the weapon's range. The projectile starts about 25 px from the player (`BOOMERANG_START_DISTANCE`; measured 11
px with one weapon, more when the weapons sit further out).

**Where the cooldown is written.** The game draws its own cooldown right after the behaviour's `shoot()`
returns. `shoot()` itself runs from a deferred call, so a call deferred inside it runs in the same flush: after
the game's draw and before the next physics tick. The extensions write the planned cooldown from such a call.
(Extending `weapons/weapon.gd` to override `get_next_cooldown` also works, but the Mod Loader then reloads every
child class of `Weapon`.)

**Turrets** (`extensions/entities/structures/turret/turret.gd`). The engine calls the extension's
`_physics_process` before the game's own of the same tick, which is where the shoot animation starts. Just
before a shot the extension reads the structure attack speed and sets `_shooting_speed` (the animation's
playback speed) to the game's value at 0 times `1 + structure attack speed`; while the animation plays it
counts ticks. In `_on_AnimationPlayer_animation_finished`, after the game has drawn its cooldown, it draws the
cooldown the game would have drawn at 0 and sets `_cooldown` to what is left of the planned cycle. The
animation runs on rendered frames and can take a tick more or less; the cooldown absorbs that, so the cycle is
exact. `_cooldown` is set half a tick short of a whole number because the game counts it down in steps of
`60 × delta`, which is not exactly 1. A shot the game has made instant (`set_instant_shoot`) keeps the game's
animation speed. When a shot is called off halfway (no target left), only the cooldown part is scaled. With a
positive structure attack speed the animation keeps at least one tick; with a negative one it plays as usual
and the cooldown takes the extra time. `tas_log` holds the last 64 cycles for the tests, each as `[base
animation ticks, base cooldown ticks, structure attack speed, animation ticks, cooldown ticks]`.

The extension covers everything built on the turret script: the turret items, garden, Tyler, wandering bot, the
Builder's turret. Structure attack speed also shortens how often landmines and structures are placed
(`apply_structure_attack_speed_effects` on a spawn cooldown); that is a plain cooldown, already proportional, and
not touched.

**Not touched, and why.**

- *Pets*: they have their own timers and neither Attack Speed nor (with one exception) structure attack speed
  reaches them. The exception is Bot-O-Mine's landmine placing, a plain cooldown.
- *Enemies*: nothing in the game changes how fast enemies attack.
- *The player's invincibility and lifesteal timers*: they have nothing to do with Attack Speed. They are listed
  here only because Attack Timing Fix, which this mod replaces, also moved them to physics ticks.

## The Mod Loader and child classes

Real exe only; the editor build does not show it. After it installs an extension of a script, Mod Loader 6.3.0
calls `reload()` on every `class_name` script whose parent is the extended class
(`addons/mod_loader/internal/script_extension.gd`, `_reload_vanilla_child_classes_for`). In the editor build
that re-binds the child to the extended parent. In the exported game the scripts are compiled and have no
source, and `reload()` turns such a script into an empty one that inherits `Reference`. If nothing holds the
script at that moment, the emptied copy is dropped and the next load is fine. If something holds it, it stays
broken for the session, with errors like "Script inherits from native type 'Reference', so it can't be instanced
in object of type 'Node2D'".

Two things hold a child script at that moment: naming its class in a script of the mod (`x is
BoomerangShootingBehavior`, a typed variable, `BoomerangProjectile.SOME_CONST`), and extending it (all extensions
are loaded for sorting before any is applied). An early build named `BoomerangShootingBehavior` in `timing.gd`,
and the Boomerang did not attack in the real game.

Rules that follow:

- Before extending a script, list its child classes (`ProjectSettings.get_setting("_global_script_classes")`,
  entries whose `base` is the class). Do not name them anywhere in the mod and do not extend them. This mod
  extends the gun behaviour (children: `BoomerangShootingBehavior`, `CarbonBowShootingBehavior`) and the turret
  (children: `BuilderTurret`, `FlameTurret`, `Garden`, `WanderingBot`).
- Reach a child's behaviour through the parent extension (the engine calls `_physics_process` and the like on
  every script level, most derived first) or by duck typing (`"_projectiles_in_flight" in self`).
- `timing.gd` also avoids `BoomerangProjectile`, `RangedWeaponStats` and `MeleeWeaponStats`, children of classes
  another mod may extend. It reads the Boomerang's flight constants with `load()` at call time.
- Test every kind of weapon and structure in the real exe, not only in the editor build.

The same would happen with another mod that names or extends one of those child classes while this mod is
installed; that cannot be prevented from here.

**Three errors in the log at every start.** The game's class list names test doubles that the game does not
ship (`res://tests/partial_doubles/pd_turret.gd`, `pd_weapon.gd`, `pd_player.gd`, `pd_enemy.gd`, `pd_main.gd`
and others). They are child classes of `Turret`, `Weapon` and so on, so when any mod extends one of those
scripts the Mod Loader tries to reload the double and the engine logs "Cannot load source code from file
'res://tests/partial_doubles/pd_turret.gd'" with two more lines (four in the editor build). This mod extends
`turret.gd`, so those lines are in the log of every start, in the real game too. They do no harm: the game's
crash reporter disables mods only after an error that mentions `mods-unpacked` or a mod zip, and these do not.
`tests/run.py` ignores them. The weapon extensions avoid the same lines by extending the shooting behaviours and
not `weapons/weapon.gd`.

## Weapon card

The cooldown line of a weapon card shows the mean cycle under the rule instead of the game's nominal cooldown
(`extensions/ui/menus/shop/item_description.gd`).

Improved Tooltips (`_wl-ImprovedTooltips`) rewrites the same line with its own figure for the unmodded game at
60 FPS and derives its Attack Speed breakpoints from it. It is an optional dependency, so its extension of
`item_description.gd` is installed first and this mod's extension sits on top of it and replaces two of its
functions:

- `_wl_get_weapon_cds`, which returns `[shortest, longest, mean]` cycle in ticks. It returns the rule's numbers;
  for a weapon this mod does not time it repeats what Improved Tooltips does (a function of the script below
  cannot be called from an extension, so that part is a copy).
- `_wl_get_breakpoint_text`, a copy of its three formats that never asks for a negative number of "!". In the
  "SHOW" mode Improved Tooltips writes `"!".repeat(round(change) - 1)`; for a change under half a tick that is
  `repeat(-1)`, which logs an engine error each time the card is drawn.

If Improved Tooltips changes either function, the copies have to follow. Its breakpoint search is not changed:
it lists every Attack Speed value at which the mean cycle changes, and with this mod that is every point, so a
held weapon shows the next two points (at +100%: `+99% >> +101%, +102%`). That search asks for the same weapon
up to 400 times in one frame, and the +0% stats do not depend on Attack Speed, so the extension keeps them for
the frame.

A turret item's text is not changed. It shows the game's cooldown stat divided by `1 + structure attack speed`,
which with this mod is still the cooldown part of the cycle.

## For other mods

`timing.gd` is the interface:

- `Timing.mean_cycle_ticks(weapon_data, current_stats, player_index, nb_weapons)`: mean ticks from one attack to
  the next. `current_stats` must be the weapon's stats under the player's stats as they are at the call. -1 for a
  weapon the mod does not time. For the Boomerang the flight is an estimate (player standing still, target
  within range).
- `Timing.cycle_figures(weapon_data, base_stats, current_stats, player_index, nb_weapons, big_reload,
  zero_stats)`: `[shortest, longest, mean]` of the same, or `[]`. `base_stats` are the stats `current_stats`
  were made from, `big_reload` asks for the cycle after the shot that triggers the long reload, and `zero_stats`
  takes `Timing.zero_speed_stats(...)` if the caller has them already.
- `Timing.weapon_info(weapon_data).kind`: `"ranged"`, `"melee"`, `"animated"` (Whip, Flail), `"boomerang"` or
  `""` for a shooting behaviour the mod does not time. Finding it needs an instance of the weapon's scene, so
  the answer is kept on the weapon's data as the meta value `tas_info`.
- `Timing.turret_mean_cycle_ticks(animation_length, data_speed, cooldown, structure_attack_speed)`: the same for
  a turret that always has a target. `animation_length` is the length of its "shoot" animation in seconds (0.3
  for the game's turrets), `data_speed` the turret item's `shooting_animation_speed`, `cooldown` the cooldown of
  its stats and `structure_attack_speed` is `WeaponService.get_structure_attack_speed(player_index) / 100`. At 0
  the result is the unmodded game at 60 FPS; the cooldown is drawn from 0.7 to 1.3 times the stat and counted in
  whole ticks, which adds half a tick to the mean.
- `Timing.cycle_factor(attack_speed)`.

## Tests

The tests drive a real, hidden game through the author's dev kit (`dk`, a console into the running game) and
read the unmodded numbers from a decompiled copy of the game. Neither is in this repository, so the tests run
only in the author's workspace; they are here as documentation of what is checked and how.
[tests.md](tests.md) says what each script checks and how to run it.

| File | What it is |
|---|---|
| `tests/run.py` | Runs everything below: `core` (about 6 minutes per mode) or `exhaustive` (about an hour). One line per step, the cases in `tests/out/`. |
| `tests/tas_rule.py` | The rule in Python (`exact()`), built on a model of the unmodded cycle. Also writes the comparison with the unmodded game for every weapon. |
| `tests/cadence.py` | Per weapon, Attack Speed and frame rate: every attack cycle against the rule, exactly (the planner's log gives what was drawn and planned; a recorder gives the ticks between shots). At +0% the cycle is compared with the unmodded model. |
| `tests/turrets.py`, `turret_probe.gd` | Turrets: structure attack speed from the real items, every cycle against the extension's log; one of every structure built on the turret script. |
| `tests/extra.py` | Ball and Chain (no cycle under 45 ticks) and co-op (each player's weapon follows that player's Attack Speed). |
| `tests/card.py`, `label_probe.gd`, `breakpoint_text_probe.gd` | What the weapon card shows in the shop, with and without Improved Tooltips. |
| `tests/hits.py` | Hits per attack against real enemies, with and without the mod. Information, no verdict. |
| `tests/showcase.py` | A visible game that walks through every kind of attack at several speeds, for judging the animations by eye. |
| `tests/scenarios/` | Launch scenarios for `dk run`. |

Two sets:

- **Core**: what is most likely to break. Two fast weapons, two slow ones, the Whip and the Boomerang at a few
  Attack Speed values; two weapons with Crystal (Attack Speed that rises every second, so it changes in the
  middle of cycles and the stats are recalculated all the time); Ball and Chain; turrets; the weapon card;
  script errors. In three modes: the editor
  build, the real exe with all DLC, the real exe without DLC. Run it after every change.
- **Exhaustive**: every weapon of the game at its lowest tier, other frame rates (30 and 144 FPS), the limits,
  the core weapons with Padding (stats recalculated every half second without changing),
  co-op, Improved Tooltips, more cases in the real exe. Run it in the background before a release; it only has
  to end with "PASS".

A case takes 6 to 40 seconds because the game runs in real time and a case needs about nine attack cycles.
`Engine.time_scale` cannot shorten it: in Godot 3 it scales `delta`, not the number of ticks, and the game's
timing changes with it.

Things that cost time to find out:

- A test that indexes an empty array in code sent to the real exe kills the process (the exported game does not
  check bounds). DLC weapons do not exist in a no-DLC run, so check `current_weapons.size()` first.
- An invulnerable player that stands still draws a crowd; hit counts from such a run are higher than in play.
- Some weapons do things to themselves that a cadence test has to know about: the Scythe drains 3 HP per second
  past the dev kit's invulnerability (the test player gets 2000 Max HP), the Drill changes its own Attack Speed,
  the Rail Gun and Sharp Tooth have their stats recalculated on a timer (`RECALCULATED` in `cadence.py`), and
  the long reload of the Combat Shotgun and others is rounded to whole ticks before Attack Speed is applied.
  `weapon_knuckles` exists in the game's files but no run can get it.
- After a run whose log has an error mentioning `mods-unpacked`, the game starts the next time with all mods
  disabled.

## Release checklist

1. `python true_attack_speed/tests/run.py core` ends with "PASS" in all three modes.
2. `python true_attack_speed/tests/run.py exhaustive` ends with "PASS".
3. Version in `manifest.json`; `compatible_game_version` and `compatible_mod_loader_version` still right.
4. Build the zip (`dk build vergir-TrueAttackSpeed`): it must contain `mods-unpacked/vergir-TrueAttackSpeed/`
   and nothing else.
5. GitHub: tag, attach the zip to the release. Workshop: `workshop/upload.py` ([workshop.md](workshop.md)).

## Known limits

- A Boomerang at high Attack Speed hits fewer enemies per throw in a crowd (about a quarter fewer at +300% in
  one measurement). Two possible causes that were not separated: the flight is over sooner, so fewer enemies
  walk into its path; and the projectile takes several steps between two collision checks, so it can pass an
  enemy it would only have grazed.
- The Boomerang estimate in `mean_cycle_ticks` assumes a target within range and a player standing still.
- `mean_cycle_ticks` and the weapon card do not know whether the build's stats are recalculated during
  cooldowns. Where they are every half second, cooldown draws above the stat are cut (unmodded too), and the
  real mean cycle is 1 to 2% shorter than shown.
- The Drill gains Attack Speed by itself during a wave (+10% every 5 seconds); the card shows the cycle at the
  Attack Speed of the moment.
- A modded weapon with a shooting behaviour of its own is left as it is.
- Checked for game 1.2.0.3 and 1.2.0.4 only. A game update that changes the shooting behaviours, `turret.gd` or the Mod
  Loader needs a new look at the extensions.
