"""Do melee attacks still land? Hits per attack against real enemies (auto-aim, wave 3, enemies kept alive).

Run it once with the mod (`dk run true_attack_speed/tests/scenarios/tas_grid --detach --hidden`) and once without (`dk run as_grid ...`) and
compare the lines: enemy positions are random, so expect a few percent of noise.

usage: python hits.py [--weapons a,b] [--as 0,300] [--secs 25]
"""
import argparse, json, pathlib, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
import dkc  # noqa: E402

COUNTER = r'''
var old = dk.get_node_or_null("AsfHits")
if old != null:
	old.free()
var src = "extends Node\nvar hits = 0\nvar seen = {}\nfunc _process(_d):\n\tvar main = get_tree().current_scene\n\tif main == null or not ('_entity_spawner' in main):\n\t\treturn\n\tfor e in main._entity_spawner.enemies:\n\t\tif is_instance_valid(e) and not seen.has(e.get_instance_id()):\n\t\t\tseen[e.get_instance_id()] = true\n\t\t\te.connect('took_damage', self, '_hit')\nfunc _hit(unit, value, kb, is_crit, is_dodge, is_protected, armor, args, hit_type, is_one_shot):\n\tif args.hitbox != null:\n\t\thits += 1\n"
var script = GDScript.new()
script.source_code = src
script.reload()
var node = Node.new()
node.name = "AsfHits"
node.set_script(script)
dk.add_child(node)
return 1
'''


def scenario(weapon):
    return {"character": "character_well_rounded", "weapons": [weapon], "wave": 3, "danger": 0, "invulnerable": True,
            "debug": {"custom_wave_duration": 3000, "nb_enemies_mult": 1.0},
            "setup": ["ProgressData.settings.manual_aim = false"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weapons", default="weapon_knife_1,weapon_hatchet_1,weapon_spear_1,weapon_hammer_2")
    ap.add_argument("--as", dest="speeds", default="0,300")
    ap.add_argument("--secs", type=float, default=25)
    args = ap.parse_args()
    mod_on = bool(dkc.ev("ModLoaderMod.is_mod_loaded('vergir-TrueAttackSpeed')"))
    print("mod loaded:", mod_on)
    print("weapon AS | attacks | hits | hits per attack | ticks the hitbox was on (count x ticks)")
    for weapon in args.weapons.split(","):
        dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(scenario(weapon))))
        time.sleep(1.0)
        dkc.wait_scene("Main")
        time.sleep(4.0)
        dkc.install_recorder()
        dkc.ex("dk.get_node('ASRec').keep_alive = true\nreturn 1")
        for speed in [int(x) for x in args.speeds.split(",")]:
            dkc.ex("RunData.add_stat(Keys.stat_attack_speed_hash, %d - int(RunData.get_player_effect(Keys.stat_attack_speed_hash, 0)), 0)\nreturn 1" % speed)
            time.sleep(1.0)
            dkc.ex(COUNTER)
            dkc.ex("dk.get_node('ASRec').start(dk.player().current_weapons[0])\nreturn 1")
            time.sleep(args.secs)
            r = dkc.ev("dk.get_node('ASRec').report()")
            hits = int(dkc.ev("dk.get_node('AsfHits').hits"))
            attacks = len(r["shots"])
            on = {}
            hb = r.get("hb", [])
            for a, b in zip(hb, hb[1:]):
                if a[1] and not b[1]:
                    on[b[0] - a[0]] = on.get(b[0] - a[0], 0) + 1
            on_text = ", ".join("%dx%d" % (v, k) for k, v in sorted(on.items(), key=lambda kv: -kv[1])[:3])
            print("%s %+d%% | %d | %d | %.2f | %s" % (weapon[len("weapon_"):], speed, attacks, hits, hits / max(1, attacks), on_text), flush=True)
    print("done")


if __name__ == "__main__":
    main()
