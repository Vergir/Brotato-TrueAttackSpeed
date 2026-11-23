# Run in the shop (`dk exec @true_attack_speed/tests/label_probe.gd`): for every held weapon, the cooldown line
# its card shows, next to the mean cycle timing.gd computes. With Improved Tooltips loaded it also returns
# that mod's [shortest, longest, mean] cycle in ticks and its Attack Speed breakpoints.
var desc = get_tree().current_scene.find_node("ItemDescription", true, false)
if desc == null:
	return "no ItemDescription in this scene"
var Timing = load("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
var bbcode = RegEx.new()
bbcode.compile("\\[[^\\]]*\\]")
var out = []
for weapon in RunData.get_player_weapons(0):
	desc.set_item(weapon, 0)
	var line = ""
	for l in desc.get_weapon_stats().bbcode_text.split("\n"):
		if l.find(tr("COOLDOWN")) >= 0:
			line = bbcode.sub(l, "", true)
	var cur = weapon.get_current_stats(0)
	var nb = RunData.get_player_weapons_ref(0).size()
	var row = {
		"id": weapon.my_id,
		"attack_speed": Utils.get_stat(Keys.stat_attack_speed_hash, 0),
		"game_tooltip_s": cur.get_cooldown_value(0, 1.0),
		"card_line": line,
		"mod_cycle_ticks": Timing.mean_cycle_ticks(weapon, cur, 0, nb) if Timing != null else null,
	}
	if desc.has_method("_wl_get_attack_breakpoints"):
		var args = WeaponServiceInitStatsArgs.new()
		args.sets = weapon.sets
		args.effects = weapon.effects
		row["it_cycle_ticks"] = desc._wl_get_weapon_cds(weapon, weapon.stats, cur, false, 0)
		row["it_breakpoints"] = desc._wl_get_attack_breakpoints(weapon, weapon.stats, args, 0)
	out.append(row)
return out
