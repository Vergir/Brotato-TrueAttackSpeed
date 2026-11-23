"""Attack cadence with vergir-TrueAttackSpeed, measured in a running game against the rule in timing.gd.
What is checked and what the options do: docs/tests.md.

usage: python cadence.py [--weapons a,b] [--as=-50,0,100,300] [--fps 30,60v,144] [--secs N] [--items a,b] [--out FILE]
"""
import argparse, json, math, pathlib, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
import dkc, tas_rule, model  # noqa: E402

WEAPONS = ["weapon_gatling_laser_4", "weapon_smg_1", "weapon_pistol_1", "weapon_carbon_bow_1",
           "weapon_hatchet_1", "weapon_knife_1", "weapon_fist_1", "weapon_sword_2",
           "weapon_whip_1", "weapon_flail_1", "weapon_boomerang_1"]
MOD_ID = "vergir-TrueAttackSpeed"
# Weapons whose stats the game recalculates during a wave even when nothing else happens.
RECALCULATED = {"sharp_tooth", "rail_gun", "scythe", "drill"}


PLANNER = "behavior.tas_planner"
START = """
var behavior = dk.player().current_weapons[0]._shooting_behavior
var planner = %s
planner.log_entries = []
planner.log_enabled = true
dk.get_node('ASRec').start(dk.player().current_weapons[0])
return 1
""" % PLANNER
STOP = """
var behavior = dk.player().current_weapons[0]._shooting_behavior
var planner = %s
planner.log_enabled = false
var data = RunData.get_player_weapons(0)[0]
var timing = load("res://mods-unpacked/%s/timing.gd")
return {"rec": dk.get_node('ASRec').report(), "log": planner.log_entries,
	"card": timing.mean_cycle_ticks(data, data.get_current_stats(0), 0, 1)}
""" % (PLANNER, MOD_ID)


def scenario(weapon, items=()):
    return {"items": {i: 1 for i in items}, "character": "character_well_rounded", "weapons": [weapon], "wave": 1, "danger": 0, "invulnerable": True,
            "debug": {"custom_wave_duration": 3000, "no_enemies": True},
            # The Scythe takes 3 HP per second, which the dev kit's invulnerability does not stop.
            "setup": ["ProgressData.settings.manual_aim = true", "RunData.add_stat(Keys.stat_max_hp_hash, 2000, 0)"]}


def find(weapon_id):
    for w in tas_rule.load_weapons():
        if w["id"] == weapon_id:
            return w
    raise SystemExit("no stats for " + weapon_id)


def base(w):
    """The unmodded game at +0%: mean shooting ticks, mean cycle ticks, mean cycle without the long reload,
    and the cooldown ticks a draw can give (the long reload of a weapon that has one is allowed too)."""
    cd = model.cooldown_ticks(w["cooldown"], 0.0)
    cycle = tas_rule.cycles(w, 0.0)["vanilla"]
    shooting = cycle - tas_rule.mean_cooldown(w, cd, True)
    lo, hi = model.jitter_range(cd, 1)
    draws = set(range(math.ceil(lo - 1e-6), math.ceil(hi - 1e-6) + 1))
    if w["reload_every"] > 0:
        draws.add(tas_rule.big_reload(w))
    return shooting, cycle, shooting + model.mean_ceil_uniform(lo, hi), draws


def factor(atk):
    return 1 / (1 + atk) if atk > 0 else 1 - atk


def check_unscaled(w, atk, shots, recalculated=False):
    """+0%: the shooting state per cycle against the unmodded frame count."""
    s = [(b[0] - a[0]) - math.ceil(a[1] - 1e-6) for a, b in zip(shots, shots[1:])]
    cd = model.cooldown_ticks(w["cooldown"], atk)
    cycle = tas_rule.cycles(w, atk)["vanilla"]
    want = cycle - tas_rule.mean_cooldown(w, cd, True, atk)
    if recalculated or w["name"] in RECALCULATED:
        # The game may have cut the part of a draw that is above the cooldown stat.
        cut = [max(0, math.ceil(a[1] - 1e-6) - cd) for a in shots[:-1]]
        slack = 3.02 if w["kind"] == "boomerang" or w["alternate"] else 0.02   # as below, but per cycle
        off = sum(1 for x, c in zip(s, cut) if not (want - c - slack <= x <= want + slack))
        failed = [] if not off else ["shooting: %d of %d cycles outside unmodded %.2f minus the cut" % (off, len(s), want)]
        return failed, 60 / cycle
    mean_s = sum(s) / len(s)
    tol = (3.0 if w["alternate"] else 0.0) / len(s) + 0.02 + (3.0 if w["kind"] == "boomerang" else 0.0)
    failed = [] if abs(mean_s - want) <= tol else ["shooting %.2f, unmodded %.2f" % (mean_s, want)]
    return failed, 60 / cycle


def check_scaled(w, atk, shots, log, card, final_atk):
    """atk: the Attack Speed asked for; final_atk: what the weapon has at the end of the case (the same,
    except for a weapon that changes its own Attack Speed)."""
    base_shooting, base_cycle, plain_cycle, allowed = base(w)
    f = factor(final_atk)
    want_rate = 60 / (base_cycle * f)
    periods = [b[0] - a[0] for a, b in zip(shots, shots[1:])]
    # The log has one entry per attack; the recorder may have started a few attacks later and may not
    # have seen the last one yet. Line the two up on the ticks.
    best = None
    for skip_end in (0, 1, 2):
        part = log[len(log) - skip_end - len(periods):len(log) - skip_end]
        if len(part) != len(periods):
            continue
        wrong = sum(1 for e, p in zip(part, periods) if e[3] != p)
        if best is None or wrong < best[0]:
            best = (wrong, part)
    if best is None:
        return ["planner log has %d entries for %d cycles" % (len(log), len(periods))], want_rate
    wrong, part = best
    failed = []
    if wrong:
        failed.append("ticks: %d of %d cycles differ from the plan" % (wrong, len(periods)))
    mean_base = sum(e[0] for e in part) / len(part)
    slack = 3.0 if w["kind"] == "boomerang" else (3.0 / len(part) + 0.02) if w["alternate"] else 1e-6
    if abs(mean_base - base_shooting) > slack:
        failed.append("base %.2f, unmodded %.2f" % (mean_base, base_shooting))
    draws = [e[1] for e in part]
    if any(d not in allowed for d in draws):
        failed.append("draw %s-%s outside %s" % (min(draws), max(draws), sorted(allowed)))
    lo, hi = min(atk, final_atk) - 1e-6, max(atk, final_atk) + 1e-6
    if any(not lo <= e[4] <= hi for e in part):
        failed.append("attack speed in the plan: %s, asked %+.2f" % (sorted(set(round(e[4], 2) for e in part)), atk))
    if any(abs(e[2] - (e[0] + e[1]) * factor(e[4])) > 1e-3 for e in part):
        failed.append("rule: a wanted cycle is not (base + draw) * factor")
    if final_atk != atk:
        want_rate = 60.0 * len(part) / sum(e[2] for e in part)
    # e[5]: ticks taken off afterwards because the weapon's stats were recalculated.
    drift = sum(e[3] + e[5] for e in part) - sum(e[2] for e in part)
    if abs(drift) > 1.001:
        limit = min(tas_rule.LEAST[k] for k in (["thrust", "sweep"] if w["alternate"] else [w["kind"]]))
        at_limit = w["kind"] == "boomerang" or all(e[3] <= max(limit, math.ceil(e[2])) + (1 if w["alternate"] else 0) for e in part)
        if not at_limit or drift < 0:
            failed.append("carry: given - wanted = %+.2f ticks over %d cycles" % (drift, len(part)))
        else:
            want_rate = 60.0 * len(part) / sum(e[3] for e in part)   # at the limit: what the plan gives
    # The card takes the shortest possible cycle into account draw by draw; where only some draws reach it
    # (Whip I at +900%: wanted cycles from 4.8 ticks, shortest 5) its mean is a little above the plain rule.
    least = min(tas_rule.LEAST[k] for k in (["thrust", "sweep"] if w["alternate"] else [w["kind"]]))
    slack = 3.0 * f if w["kind"] == "boomerang" else 0.02 * plain_cycle * f if min(e[2] for e in part) < least else 1e-3
    if abs(card - plain_cycle * f) > slack and abs(drift) <= 1.001:
        failed.append("card %.3f, expected %.3f" % (card, plain_cycle * f))
    return failed, want_rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weapons", default=",".join(WEAPONS))
    ap.add_argument("--as", dest="speeds", default="0,100,300")
    ap.add_argument("--fps", default="30,60v,144")
    ap.add_argument("--secs", type=float, default=0)
    ap.add_argument("--items", default="")
    ap.add_argument("--out", default=str(HERE / "out" / "cadence.jsonl"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.parent.mkdir(exist_ok=True)
    mod_on = bool(dkc.ev("ModLoaderMod.is_mod_loaded('%s')" % MOD_ID))
    print("mod loaded:", mod_on)
    print("weapon AS fps | cycles | attacks/s: measured / rule / unmodded 60 FPS | verdict")
    bad = 0
    with open(out, "w", encoding="utf-8") as fh:
        weapons = args.weapons.split(",")
        if args.weapons == "all":   # every weapon of the game at its lowest tier
            lowest = {}
            for w in tas_rule.load_weapons():
                if w["id"] and (w["name"] not in lowest or w["tier"] < lowest[w["name"]]["tier"]):
                    lowest[w["name"]] = w
            weapons = [w["id"] for w in sorted(lowest.values(), key=lambda w: w["id"])]
        items = [i for i in args.items.split(",") if i]
        for weapon in weapons:
            w = find(weapon)
            dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(scenario(weapon, items))))
            time.sleep(1.0)
            dkc.wait_scene("Main")
            time.sleep(1.5)
            dkc.install_recorder()
            # A DLC weapon in a run without that DLC is not given to the player. (Do not index the empty
            # weapon list: the real exe does not check array bounds and dies.)
            if int(dkc.ev("dk.player().current_weapons.size()")) == 0:
                print("%s | not available in this run (DLC weapon?), skipped" % weapon[len("weapon_"):], flush=True)
                continue
            for speed in [int(x) for x in args.speeds.split(",")]:
                dkc.ex("RunData.add_stat(Keys.stat_attack_speed_hash, %d - int(RunData.get_player_effect(Keys.stat_attack_speed_hash, 0)), 0)\nreturn 1" % speed)
                for fps in args.fps.split(","):
                    dkc.set_fps(0, True) if fps.endswith("v") else dkc.set_fps(int(fps), False)
                    time.sleep(0.8)
                    secs = args.secs or min(40.0, max(6.0, 9 * tas_rule.exact(w, speed / 100.0) / 60.0))
                    dkc.ex(START)
                    time.sleep(secs)
                    r = dkc.ex(STOP)
                    rec = r["rec"]
                    rec.update({"fps_setting": fps, "as_wanted": speed, "mod_on": mod_on, "log": r["log"], "card": r["card"]})
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    shots = rec["shots"]
                    label = "%s %+d%% %s (%.0f)" % (weapon[len("weapon_"):], speed, fps, rec["fps"])
                    if len(shots) < 4:
                        print("%s | too few attacks (%d)" % (label, len(shots)))
                        bad += 1
                        continue
                    atk = speed / 100.0
                    final_atk = rec["attack_speed"] / 100.0
                    if atk != 0 or final_atk != 0:
                        failed, want_rate = check_scaled(w, atk, shots, r["log"], r["card"], final_atk)
                    else:
                        failed, want_rate = check_unscaled(w, atk, shots, bool(items))
                    bad += 1 if failed else 0
                    aps = 60.0 * (len(shots) - 1) / (shots[-1][0] - shots[0][0])
                    print("%s | %d | %.2f / %.2f / %.2f | %s" % (
                        label, len(shots) - 1, aps, want_rate, 60 / tas_rule.cycles(w, atk)["vanilla"],
                        "ok" if not failed else "DIFFERENT: " + "; ".join(failed)), flush=True)
    dkc.set_fps(0, True)
    print("done, %d case(s) off" % bad)


if __name__ == "__main__":
    main()
