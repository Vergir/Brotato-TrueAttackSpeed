"""A showcase for judging the animations by eye. Drives a VISIBLE game through every kind of attack at several
Attack Speed values; a caption on screen says what is being shown.

    dk run true_attack_speed/tests/scenarios/tas_look.json --detach        (visible: no --hidden)
    python true_attack_speed/tests/showcase.py [--secs 5] [--only whip,turrets] [--speeds 0,100,300,-50]

Parts, in order (names for --only): smg, gatling, knife, hatchet, whip, flail, boomerang (one weapon each, at each
speed), all (six weapons together at +300%), turrets (six turrets at structure attack speed 0, +100%, +300%, -50%).
The player is invulnerable and stands still; enemies come to it and die normally.
"""
import argparse, json, pathlib, sys, time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "research" / "attack_speed"))
import dkc  # noqa: E402

PARTS = [("smg", "SMG I", "weapon_smg_1", "gun"),
         ("gatling", "Gatling Laser IV", "weapon_gatling_laser_4", "gun, the fastest in the game"),
         ("knife", "Knife I", "weapon_knife_1", "melee thrust"),
         ("hatchet", "Hatchet I", "weapon_hatchet_1", "melee sweep"),
         ("whip", "Whip I", "weapon_whip_1", "its animation is compressed at high speed"),
         ("flail", "Flail I", "weapon_flail_1", "its animation is compressed at high speed"),
         ("boomerang", "Boomerang I", "weapon_boomerang_1", "the flight is played faster")]
SIX = ["weapon_gatling_laser_4", "weapon_smg_1", "weapon_knife_1", "weapon_hatchet_1", "weapon_whip_1", "weapon_boomerang_1"]
CAPTION = '''var layer = dk.get_node_or_null("TasCaption")
if layer == null:
	layer = CanvasLayer.new()
	layer.name = "TasCaption"
	layer.layer = 100
	var label = Label.new()
	label.name = "Label"
	label.rect_position = Vector2(520, 150)
	label.rect_scale = Vector2(2.5, 2.5)
	label.add_color_override("font_color_shadow", Color(0, 0, 0))
	label.add_constant_override("shadow_offset_x", 2)
	label.add_constant_override("shadow_offset_y", 2)
	layer.add_child(label)
	dk.add_child(layer)
layer.get_node("Label").text = %s
return 1'''


def caption(text):
    print(text.replace("\n", " | "), flush=True)
    dkc.ex(CAPTION % json.dumps(text))


def load(weapons, items=None, wave=6):
    sc = {"character": "character_well_rounded", "weapons": weapons, "items": items or {}, "wave": wave, "danger": 0,
          "invulnerable": True, "debug": {"custom_wave_duration": 900}}
    dkc.ex("return dk.load_scenario(parse_json(%s))" % json.dumps(json.dumps(sc)))
    time.sleep(1.0)
    dkc.wait_scene("Main")
    time.sleep(1.0)


def set_stat(key, value):
    dkc.ex("RunData.add_stat(Keys.%s, %d - int(RunData.get_player_effect(Keys.%s, 0)), 0)\nreturn 1" % (key, value, key))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=float, default=5.0)
    ap.add_argument("--speeds", default="0,100,300,-50")
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = [x for x in args.only.split(",") if x]
    speeds = [int(x) for x in args.speeds.split(",")]
    for key, name, weapon, note in PARTS:
        if only and key not in only:
            continue
        load([weapon])
        if int(dkc.ev("dk.player().current_weapons.size()")) == 0:
            caption("%s is a DLC weapon and is not in this run" % name)
            time.sleep(2.0)
            continue
        for speed in speeds:
            set_stat("stat_attack_speed_hash", speed)
            caption("%s (%s)\nAttack Speed %+d%%%s" % (name, note, speed, "  = unmodded" if speed == 0 else ""))
            time.sleep(args.secs)
    if not only or "all" in only:
        load(SIX)
        for speed in (0, 300):
            set_stat("stat_attack_speed_hash", speed)
            caption("Six weapons together\nAttack Speed %+d%%%s" % (speed, "  = unmodded" if speed == 0 else ""))
            time.sleep(args.secs * 1.6)
    if not only or "turrets" in only:
        load([], {"item_turret": 4, "item_turret_laser": 1, "item_turret_rocket": 1}, wave=4)
        caption("Turrets\nthey appear in a few seconds")
        time.sleep(12.0)
        for speed in speeds:
            set_stat("structure_attack_speed_hash", speed)
            caption("Turrets\nstructure attack speed %+d%%%s" % (speed, "  = unmodded" if speed == 0 else ""))
            time.sleep(args.secs * 1.6)
    caption("End of the showcase")


if __name__ == "__main__":
    main()
