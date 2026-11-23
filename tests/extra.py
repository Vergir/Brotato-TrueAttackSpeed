"""Two situations cadence.py does not cover: Ball and Chain (minimum cooldown) and a co-op run.
What is checked: docs/tests.md.

usage: python extra.py [chain] [coop] [--weapons a,b] [--as 100,300] [--secs N]
"""
import argparse, collections, json, pathlib, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
sys.path.insert(0, str(HERE))
import cadence, dkc, tas_rule  # noqa: E402

MOD_ID = "vergir-TrueAttackSpeed"
WEAPON = "dk.player(%d).current_weapons[0]"
START = """
var weapon = %s
var behavior = weapon._shooting_behavior
if 'tas_planner' in behavior:
	var planner = %s
	planner.log_entries = []
	planner.log_enabled = true
dk.get_node('ASRec').start(weapon)
return 1
"""
STOP = """
var weapon = %s
var behavior = weapon._shooting_behavior
var entries = []
if 'tas_planner' in behavior:
	var planner = %s
	planner.log_enabled = false
	entries = planner.log_entries
return {"rec": dk.get_node('ASRec').report(), "log": entries, "player": weapon.player_index,
	"cooldown": weapon.current_stats.cooldown}
"""


def record(player, secs):
    weapon = WEAPON % player
    dkc.ex(START % (weapon, cadence.PLANNER))
    time.sleep(secs)
    r = dkc.ex(STOP % (weapon, cadence.PLANNER))
    shots = r["rec"]["shots"]
    return [b[0] - a[0] for a, b in zip(shots, shots[1:])], r["log"], r


def set_speed(speed, player):
    dkc.ex("RunData.add_stat(Keys.stat_attack_speed_hash, %d - int(RunData.get_player_effect(Keys.stat_attack_speed_hash, %d)), %d)\nreturn 1"
           % (speed, player, player))
    time.sleep(1.0)


def top(values, n=3):
    return ", ".join("%dx%s" % (c, v) for v, c in collections.Counter(values).most_common(n))


def plan_matches(periods, log):
    """How many measured cycles equal the planned ones, and how many are shorter (lined up at the end)."""
    best = None
    for skip_end in (0, 1, 2):
        part = log[len(log) - skip_end - len(periods):len(log) - skip_end]
        if len(part) != len(periods):
            continue
        same = sum(1 for e, p in zip(part, periods) if e[3] == p)
        shorter = sum(1 for e, p in zip(part, periods) if p < e[3])
        if best is None or same > best[0]:
            best = (same, shorter)
    return best


def chain(args, mod_on):
    for weapon in args.weapons.split(","):
        scenario = cadence.scenario(weapon)
        scenario["items"] = {"item_ball_and_chain": 1}
        dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(scenario)))
        time.sleep(1.0)
        dkc.wait_scene("Main")
        time.sleep(1.5)
        dkc.install_recorder()
        for speed in [0] + [int(x) for x in args.speeds.split(",")]:
            set_speed(speed, 0)
            periods, log, r = record(0, args.secs or 10)
            verdict = "-"
            if mod_on and speed != 0:
                same, shorter = plan_matches(periods, log) or (0, 0)
                ok = same == len(periods) and min(periods) >= 45
                verdict = "ok" if ok else "DIFFERENT: %d of %d cycles as planned, shortest %d" % (same, len(periods), min(periods))
            print("chain %s %+d%% | cooldown stat %s | %d cycles, mean %.2f ticks, shortest %d (%s) | %s" % (
                weapon[len("weapon_"):], speed, r["cooldown"], len(periods), sum(periods) / len(periods), min(periods),
                top(periods), verdict), flush=True)


def coop(args, mod_on):
    for weapon in args.weapons.split(","):
        w = cadence.find(weapon)
        scenario = {"character": "character_well_rounded", "weapons": [weapon], "wave": 3, "danger": 0, "invulnerable": True,
                    "debug": {"custom_wave_duration": 3000, "nb_enemies_mult": 1.0},
                    "setup": ["ProgressData.settings.manual_aim = false",
                              "RunData.set_coop_run(true)", "RunData.play_mode = RunData.PlayMode.COOP", "RunData.set_player_count(2)",
                              "CoopService._add_player(0, 0)", "CoopService._add_player(1, 1)",
                              "RunData.add_character(dk.find_data(ItemService.characters, 'character_well_rounded'), 1)",
                              "RunData.add_weapon(dk.find_data(ItemService.weapons, '%s'), 1, true)" % weapon]}
        dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(scenario)))
        time.sleep(1.0)
        dkc.wait_scene("Main")
        time.sleep(4.0)
        dkc.install_recorder()
        dkc.ex("dk.get_node('ASRec').keep_alive = true\nreturn 1")
        base_cycle = tas_rule.cycles(w, 0.0)["vanilla"]
        for speed in [int(x) for x in args.speeds.split(",")]:
            set_speed(0, 0)
            set_speed(speed, 1)
            for player, player_speed in ((0, 0), (1, speed)):
                periods, log, r = record(player, args.secs or 15)
                rule = tas_rule.exact(w, player_speed / 100.0)
                common = collections.Counter(periods).most_common(1)[0][0]
                failed = []
                if r["player"] != player:
                    failed.append("recorded player %s" % r["player"])
                if mod_on and abs(common - rule) > max(2.0, 0.2 * rule):
                    failed.append("most common cycle %d, rule %.1f" % (common, rule))
                if mod_on and player_speed != 0:
                    same, shorter = plan_matches(periods, log) or (0, len(periods))
                    if shorter or same < 0.6 * len(periods):
                        failed.append("%d of %d cycles as planned, %d shorter" % (same, len(periods), shorter))
                print("coop %s player %d at %+d%% | %d cycles, shortest %d, most common %d (%s) | rule %.1f, unmodded %.1f | %s" % (
                    weapon[len("weapon_"):], player + 1, player_speed, len(periods), min(periods), common, top(periods),
                    rule, tas_rule.cycles(w, player_speed / 100.0)["vanilla"],
                    ("ok" if not failed else "DIFFERENT: " + "; ".join(failed)) if mod_on else "-"), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", default=["chain", "coop"])
    ap.add_argument("--weapons", default="weapon_smg_1,weapon_knife_1,weapon_whip_1")
    ap.add_argument("--as", dest="speeds", default="100,300")
    ap.add_argument("--secs", type=float, default=0)
    args = ap.parse_args()
    mod_on = bool(dkc.ev("ModLoaderMod.is_mod_loaded('%s')" % MOD_ID))
    print("mod loaded:", mod_on)
    if "chain" in args.cases:
        chain(args, mod_on)
    if "coop" in args.cases:
        coop(args, mod_on)
    print("done")


if __name__ == "__main__":
    main()
