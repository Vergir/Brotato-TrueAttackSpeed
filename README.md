# True Attack Speed

A mod for [Brotato](https://store.steampowered.com/app/1942280/Brotato/) that makes Attack Speed do what it
says, for every weapon and at any frame rate:

- **+100% Attack Speed is twice the attacks**, +300% is four times, +50% is one and a half times.
- **-100% Attack Speed is half the attacks.**
- **At +0% nothing changes**: weapons attack exactly as fast as in the unmodded game at 60 FPS.
- **Turrets follow the same rule** with structure attack speed (Clockwork Wasp, Improved Tools, Technomage,
  Builder).

Mod id `vergir-TrueAttackSpeed`, for game version 1.2.0.4 (Mod Loader 6.3.0; 1.2.0.3 works too). Works with and without the DLCs,
in single player and co-op.

## Why

In the unmodded game Attack Speed changes the attack rate by less than it says, in steps, and for fast weapons
not at all. An attack is a short "shooting" state (the recoil or the swing) followed by a cooldown, and Attack
Speed only works properly on the cooldown:

- The shooting state is timed on rendered frames and has a few frames that never get shorter. A fast weapon
  spends most of its time there, and the lower your frame rate, the slower every weapon attacks.
- The cooldown is cut to whole ticks and cannot go under 2 ticks.
- The Whip and Flail play a fixed animation, and the Boomerang waits for its projectile to come back. Neither
  gets faster with Attack Speed.
- Negative Attack Speed only stretches the cooldown, so -100% is not half the attacks.
- A turret's shoot animation ignores structure attack speed in the same way.

Attacks per second with one weapon (unmodded numbers are at 60 FPS):

| Weapon | Attack Speed | Unmodded | True Attack Speed |
|---|---|---|---|
| Gatling Laser IV | -100% | 6.32 | 4.00 |
| | +0% | 8.00 | 8.00 |
| | +100% | 10.91 | 16.00 |
| | +300% | 10.91 | 32.00 |
| SMG I | -100% | 3.43 | 2.22 |
| | +0% | 4.44 | 4.44 |
| | +100% | 8.00 | 8.89 |
| | +300% | 10.91 | 17.78 |
| Pistol I | -100% | 0.44 | 0.40 |
| | +0% | 0.79 | 0.79 |
| | +100% | 1.52 | 1.59 |
| | +300% | 2.93 | 3.18 |
| Hatchet I | -100% | 1.01 | 0.62 |
| | +0% | 1.24 | 1.24 |
| | +100% | 2.35 | 2.47 |
| | +300% | 3.87 | 4.95 |
| Whip I | -100% | 0.76 | 0.56 |
| | +0% | 1.12 | 1.12 |
| | +100% | 1.48 | 2.24 |
| | +300% | 1.74 | 4.49 |
| Boomerang I | -100% | 0.59 | 0.34 |
| | +0% | 0.69 | 0.69 |
| | +100% | 0.75 | 1.37 |
| | +300% | 0.79 | 2.74 |
| Turret (structure attack speed) | -50% | 0.91 | 0.81 |
| | +0% | 1.21 | 1.21 |
| | +100% | 1.90 | 2.42 |
| | +300% | 3.64 | 4.85 |

## What changes for your runs

The mod is a fix. The balance shifts a little as a side effect:

- **Fast weapons keep gaining from Attack Speed.** Unmodded, a Gatling Laser IV gains nothing after about +20%
  and an SMG I nothing between +100% and +200%. Here every point counts, up to one attack per tick (60 per
  second) for a gun.
- **Whip, Flail and Boomerang gain the most**, because unmodded most of their attack ignores Attack Speed. A
  fast Boomerang hits somewhat fewer enemies per throw in a crowd, since each flight is over sooner.
- **Negative Attack Speed costs more** than in the unmodded game: at -50% a fast weapon has about a quarter
  fewer attacks than it would have unmodded.
- **The first points of Attack Speed are worth less.** Unmodded, most weapons get a jump from the very first
  point (an SMG I goes from 4.4 to 5.7 attacks per second at +1%). Here +1% is 1%, so at low Attack Speed some
  weapons are slower than unmodded (an SMG I until about +80%, slow weapons by 2 to 3%).
- **The frame rate no longer matters.** Everything is counted in physics ticks, 60 per second. If you use the
  game's "Limit FPS" option, weapons were a little faster for you at +0% than with vsync; the mod uses the vsync
  numbers for everyone.
- **Ball and Chain** still limits a weapon to one attack per 45 ticks.
- **The weapon card shows the real time between attacks** in its cooldown line.

Not changed: pets, enemies, how often structures and landmines are placed, anything else that is not an attack
of a weapon or a turret.

## Install

Subscribe to [True Attack Speed](https://steamcommunity.com/sharedfiles/filedetails/?id=3844942766) on the Steam
Workshop. The game loads mods only from the Workshop folders of items you are subscribed to; the zip attached to
a release here is the same file the Workshop item contains.

Compatibility:

- [Improved Tooltips](https://steamcommunity.com/sharedfiles/filedetails/?id=3019195689)
  (`_wl-ImprovedTooltips`) is supported: its cooldown line and its Attack Speed breakpoints use this mod's
  numbers. With this mod every point of Attack Speed is a breakpoint, so the list just shows the next two.
- **Attack Timing Fix** (`TioPlato-AttackTimingFix`) changes the same code and is marked as incompatible. Use
  one or the other.
- Mods that add weapons work as long as their weapons use the game's own gun, melee or animated behaviours.

## For other mods

The time between two attacks of a weapon, in physics ticks, with this mod loaded:

```gdscript
if ModLoaderMod.is_mod_loaded("vergir-TrueAttackSpeed"):
	var Timing = load("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
	var ticks: float = Timing.mean_cycle_ticks(weapon_data, weapon_data.get_current_stats(player_index), player_index, nb_weapons)
```

It returns -1 for a weapon the mod does not time (a modded weapon with a shooting behaviour of its own).
`Timing.turret_mean_cycle_ticks(...)` does the same for a turret. With the mod loaded, the game's
`current_stats.cooldown` no longer tells the time between attacks at any Attack Speed other than +0%.

## Development

[docs/architecture.md](docs/architecture.md) has the exact rule, how each kind of weapon is handled, what the
Mod Loader does to compiled scripts (read it before extending another script), and how the tests work.

```
mods-unpacked/vergir-TrueAttackSpeed/   the mod: manifest, timing.gd (the rule), script extensions
tests/                                  checks that drive a hidden game; they need the author's dev kit
docs/architecture.md                    technical documentation
docs/tests.md                           what each test checks and how to run it
docs/workshop.md                        the Steam Workshop item and how it is uploaded
docs/workshop_description.txt           the text of the Workshop page
workshop/                               makes the page's images and uploads the item
```

## License

[MIT](LICENSE). Brotato is made by Blobfish. This repository contains none of the game's assets, and of its
code only the few lines that a function replacing one of the game's has to repeat.
