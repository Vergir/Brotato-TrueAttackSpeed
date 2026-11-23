# Run in the shop with Improved Tooltips loaded (`dk exec @true_attack_speed/tests/breakpoint_text_probe.gd`):
# the breakpoint texts Improved Tooltips builds for every held weapon, in each of its three
# "attack_speed_breakpoints" display modes (the setting is put back afterwards).
var desc = get_tree().current_scene.find_node("ItemDescription", true, false)
if desc == null or not desc.has_method("_wl_get_attack_breakpoints"):
	return "no ItemDescription with Improved Tooltips in this scene"
var bbcode = RegEx.new()
bbcode.compile("\\[[^\\]]*\\]")
var attack_speed = Utils.get_stat(Keys.stat_attack_speed_hash, 0)
var setting = Text._wl_settings.get("attack_speed_breakpoints", "")
var out = {"setting": setting, "attack_speed": attack_speed}
for weapon in RunData.get_player_weapons(0):
	var args = WeaponServiceInitStatsArgs.new()
	args.sets = weapon.sets
	args.effects = weapon.effects
	var breakpoints = desc._wl_get_attack_breakpoints(weapon, weapon.stats, args, 0)
	var modes = {}
	for mode in ["SHOW", "SHOW_FRAMES", "SHOW_DPS"]:
		Text._wl_settings["attack_speed_breakpoints"] = mode
		var texts = []
		for side in breakpoints:
			var part = []
			for bp in side:
				part.append(bbcode.sub(desc._wl_get_breakpoint_text(attack_speed + bp[0], bp[1], bp[2]), "", true))
			texts.append(PoolStringArray(part).join(", "))
		modes[mode] = PoolStringArray(texts).join(" >> ")
	out[weapon.my_id] = modes
Text._wl_settings["attack_speed_breakpoints"] = setting
return out
