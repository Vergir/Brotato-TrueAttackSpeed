"""Weapon card: does the cooldown line show the mod's attack cycle?

Needs a hidden game with the mod. Opens the shop with six weapons (DLC weapons are left out by the game when
the DLC is not owned), sets Attack Speed and reads every held weapon's card the way the shop draws it
(label_probe.gd). With Improved Tooltips loaded its own cycle figure is compared as well.

usage: python true_attack_speed/tests/card.py [--as=0,100,-50]
"""
import argparse, json, pathlib, re, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
import dkc  # noqa: E402

WEAPONS = ["weapon_gatling_laser_4", "weapon_smg_1", "weapon_boomerang_1", "weapon_hatchet_1", "weapon_knife_1", "weapon_whip_1"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--as", dest="speeds", default="0,100,-50")
    args = ap.parse_args()
    sc = {"character": "character_well_rounded", "weapons": WEAPONS, "wave": 1, "danger": 0, "start": "shop"}
    dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(sc)))
    time.sleep(1.0)
    dkc.wait_scene("Shop")
    time.sleep(1.0)
    probe = (HERE / "label_probe.gd").read_text(encoding="utf-8")
    print("weapon AS | card line | mod's cycle in seconds | verdict")
    bad = 0
    for speed in [int(x) for x in args.speeds.split(",")]:
        dkc.ex("RunData.add_stat(Keys.stat_attack_speed_hash, %d - int(RunData.get_player_effect(Keys.stat_attack_speed_hash, 0)), 0)\nreturn 1" % speed)
        time.sleep(0.3)
        rows = dkc.ex(probe)
        if not isinstance(rows, list) or not rows:
            print("AS %+d | no card read: %s" % (speed, str(rows)[:80]))
            bad += 1
            continue
        for r in rows:
            failed = []
            want = r["mod_cycle_ticks"] / 60.0
            shown = re.search(r"([0-9.]+)s", r["card_line"])
            if shown is None:
                failed.append("no seconds on the card")
            elif abs(float(shown.group(1)) - want) > 0.0055:   # the card rounds to two or three decimals
                failed.append("card shows %s, cycle is %.3f" % (shown.group(1), want))
            it = r.get("it_cycle_ticks")
            if it is not None and abs(it[2] - r["mod_cycle_ticks"]) > 0.01 * r["mod_cycle_ticks"]:
                failed.append("Improved Tooltips has %.2f ticks, the mod %.2f" % (it[2], r["mod_cycle_ticks"]))
            bad += 1 if failed else 0
            print("%s %+d%% | %s | %.3f%s | %s" % (r["id"][len("weapon_"):], speed, r["card_line"].strip(), want,
                                                    " (Improved Tooltips loaded)" if it is not None else "",
                                                    "ok" if not failed else "DIFFERENT: " + "; ".join(failed)), flush=True)
    print("done, %d case(s) off" % bad)


if __name__ == "__main__":
    main()
