"""Turrets: does structure attack speed scale the whole cycle? What is checked: docs/tests.md.

usage: python true_attack_speed/tests/turrets.py [speeds] [variants] [--secs 12]
"""
import argparse, json, math, pathlib, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
import dkc  # noqa: E402

MOD_ID = "vergir-TrueAttackSpeed"
INSTALL = '''var old = dk.get_node_or_null("TasTurrets")
if old != null:
	old.free()
var f = File.new()
f.open("%s", File.READ)
var script = GDScript.new()
script.source_code = f.get_as_text()
f.close()
var err = script.reload()
var node = Node.new()
node.name = "TasTurrets"
node.set_script(script)
dk.add_child(node)
return err'''
VARIANTS = ["item_turret", "item_turret_flame", "item_turret_laser", "item_turret_rocket", "item_turret_healing",
            "item_garden", "item_tyler", "item_wandering_bot", "item_bleeding_turret"]
ANIMATION_TICKS = 17   # 0.3 s animation: ceil(18) - 1


def load(items):
    sc = {"character": "character_well_rounded", "weapons": [], "items": items, "wave": 3, "danger": 0,
          "invulnerable": True, "debug": {"custom_wave_duration": 3000, "nb_enemies_mult": 3.0}}
    dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(sc)))
    time.sleep(1.0)
    dkc.wait_scene("Main")
    dkc.ex(INSTALL % str(HERE / "turret_probe.gd").replace("\\", "/"))
    time.sleep(18)   # turrets spawn, enemies arrive


def set_stat(key, value):
    dkc.ex("RunData.add_stat(Keys.%s, %d - int(RunData.get_player_effect(Keys.%s, 0)), 0)\nreturn 1" % (key, value, key))


def record(secs):
    dkc.ex("dk.get_node('TasTurrets').start()\nreturn 1")
    time.sleep(secs)
    return dkc.ev("dk.get_node('TasTurrets').report()")


def factor(s):
    return 1 / (1 + s) if s > 0 else 1 + abs(s)


def unmodded_max_cooldown(cooldown, s):
    """The cooldown stat the game as shipped uses at structure attack speed s (weapon_service.gd:606)."""
    return max(2, int(cooldown / (1 + s))) if s >= 0 else max(2, int(cooldown * (1 + abs(s))))


def unmodded_sped_up(cooldown, s, length_ticks=18.0):
    """True if the unmodded game plays the shoot animation faster at this speed (cooldown shorter than it).
    How many ticks a sped-up animation takes depends on float rounding (measured: 15 at 1.125 times, 8 at
    2.25 times, where the formula below says 7), so such a case gets a tick of tolerance."""
    max_cd = max(2, int(cooldown / (1 + s))) if s >= 0 else max(2, int(cooldown * (1 + abs(s))))
    return length_ticks > max_cd


def unmodded_cycle(cooldown, s, length_ticks=18.0):
    """The game as shipped at 60 FPS: only the cooldown stat is scaled (whole ticks, at least 2)."""
    max_cd = max(2, int(cooldown / (1 + s))) if s >= 0 else max(2, int(cooldown * (1 + abs(s))))
    speed = min(length_ticks / max_cd, 3.0) if length_ticks > max_cd else 1.0
    return max(1.0, math.ceil(length_ticks / speed - 1e-4) - 1) + 0.1 + max_cd + 0.5


def check(turrets, s, mod_on):
    failed = []
    clean = []
    total = 0
    called_off = 0
    for t in turrets:
        cd = t["cooldown"]
        planned = got = 0.0
        exact = True
        for period, anim, wait, drawn, entry in t["cycles"]:
            total += 1
            had_target = wait == math.ceil(drawn - 1e-4)
            if had_target:
                clean.append(period)
                if not mod_on or s == 0:
                    # The game as shipped: the draw is 0.7 to 1.3 times the cooldown stat at this speed.
                    # (The probe may read the cooldown one tick after it was drawn.)
                    max_cd = unmodded_max_cooldown(cd, s)
                    if not (max(1.0, 0.7 * max_cd) - 1.1 <= drawn <= 1.3 * max_cd + 1e-3):
                        failed.append("draw %.1f outside 0.7 to 1.3 times %d" % (drawn, max_cd))
            if not mod_on or s == 0:
                if entry is not None:
                    failed.append("the mod set a cooldown at structure attack speed 0")
                continue
            if entry is None:
                failed.append("log: a cycle without an entry")
                continue
            base_anim, base_cd, logged_s, logged_anim, ticks = entry
            if logged_anim == 0:
                called_off += 1   # no target left when the animation reached the shot; the game does the same
                exact = False
                continue
            if logged_anim != anim or abs(drawn - (ticks - 0.5)) > 1e-3:
                failed.append("log: recorded %d + cooldown %.1f, logged %d + %d" % (anim, drawn, logged_anim, ticks))
            if base_anim != ANIMATION_TICKS or not (math.ceil(0.7 * cd - 1e-4) <= base_cd <= math.ceil(1.3 * cd - 1e-4)):
                failed.append("base: animation %s, cooldown %s of %s" % (base_anim, base_cd, cd))
            if abs(logged_s - s) > 1e-6:
                failed.append("speed: logged %s, the game says %s" % (logged_s, s))
            target = (base_anim + base_cd) * factor(s)
            if ticks > 1 and abs(logged_anim + ticks - target) > 1.001:
                failed.append("rule: %d + %d ticks, wanted %.2f" % (logged_anim, ticks, target))
            exact = exact and ticks > 1 and had_target
            planned += target
            got += logged_anim + ticks
        if mod_on and s != 0 and exact and abs(planned - got) > 1.001:
            failed.append("rule: one turret's cycles add up to %.1f, wanted %.1f" % (got, planned))
    cd = turrets[0]["cooldown"] if turrets else 0
    rule = (ANIMATION_TICKS + cd + 0.5) * factor(s)
    unmodded = unmodded_cycle(cd, s)
    mean = sum(clean) / len(clean) if clean else 0.0
    want = rule if mod_on else unmodded
    if s == 0:
        want = unmodded
    if called_off > 0.1 * max(1, total):
        failed.append("%d of %d shots called off" % (called_off, total))
    if len(clean) < 8:
        failed.append("too few cycles with a target (%d)" % len(clean))
    else:
        # A cooldown is drawn evenly from 0.7 to 1.3 times its stat, so one cycle scatters by 0.173 times that
        # stat and the mean of n cycles by that over sqrt(n); three of those are allowed, plus half a tick.
        spread = 0.1732 * (cd * factor(s) if want == rule else unmodded_max_cooldown(cd, s))
        allowed = 3 * spread / math.sqrt(len(clean)) + 0.5 + (1.0 if want == unmodded and unmodded_sped_up(cd, s) else 0.0)
        if abs(mean - want) > allowed:
            failed.append("mean cycle %.1f, wanted %.1f +- %.1f" % (mean, want, allowed))
    return failed, total, len(clean), mean, rule, unmodded


def speeds(args, mod_on):
    load({"item_turret": 4})
    print("turrets | structure attack speed | cycles (with a target in time) | mean ticks: measured / rule / unmodded 60 FPS | verdict")
    steps = [("no item", []),
             ("Clockwork Wasp", ["dk.give_item('item_clockwork_wasp')"]),
             ("+ Improved Tools, Attack Speed +180", ["dk.give_item('item_improved_tools')", ("stat_attack_speed_hash", 180)]),
             ("same, Attack Speed -120", [("stat_attack_speed_hash", -120)]),
             ("same, Attack Speed 0, stat +290", [("stat_attack_speed_hash", 0), ("structure_attack_speed_hash", 300)])]
    bad = 0
    for label, actions in steps:
        for action in actions:
            if isinstance(action, tuple):
                set_stat(*action)
            else:
                dkc.ex(action + "\nreturn 1")
        time.sleep(1.0)
        s = float(dkc.ev("WeaponService.get_structure_attack_speed(0)")) / 100.0
        # When targets are scarce, the cycles that had one in time are mostly those with a long cooldown
        # draw, and their mean is too high (seen: 50.2 for 46.6 with 29 of 42 cycles). Record again then.
        for _attempt in range(3):
            turrets = record(args.secs)
            failed, total, clean, mean, rule, unmodded = check(turrets, s, mod_on)
            if clean >= 0.85 * total:
                break
        bad += 1 if failed else 0
        print("%s | %+d%% | %d (%d) | %.1f / %.1f / %.1f | %s" % (
            label, round(s * 100), total, clean, mean, rule, unmodded,
            "ok" if not failed else "DIFFERENT: " + "; ".join(sorted(set(failed))[:3])), flush=True)
    return bad


def variants(args, mod_on):
    load({item: 1 for item in VARIANTS})
    set_stat("structure_attack_speed_hash", 100)
    time.sleep(1.0)
    turrets = record(args.secs)
    print("variants at +100%% | %d structures built on the turret script" % len(turrets))
    bad = 0
    for t in turrets:
        failed = []
        if t["base_type"] in ("", "Reference"):
            failed.append("script is empty (base type '%s')" % t["base_type"])
        if mod_on and t["shots"] > 1 and t["mod_cycles"] == 0:
            failed.append("shot %d times, never scaled" % t["shots"])
        bad += 1 if failed else 0
        print("%s | shots %d, scaled cycles %d | %s" % (t["scene"], t["shots"], t["mod_cycles"], "ok" if not failed else "DIFFERENT: " + "; ".join(failed)), flush=True)
    if not turrets:
        print("no turrets found")
        bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="*", default=["speeds", "variants"])
    ap.add_argument("--secs", type=float, default=12.0)
    args = ap.parse_args()
    mod_on = bool(dkc.ev("ModLoaderMod.is_mod_loaded('%s')" % MOD_ID))
    print("mod loaded:", mod_on)
    bad = 0
    for case in args.cases:
        bad += {"speeds": speeds, "variants": variants}[case](args, mod_on)
    print("done, %d case(s) off" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
