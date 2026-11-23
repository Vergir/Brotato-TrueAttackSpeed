extends "res://ui/menus/shop/item_description.gd"

# Weapon card: the cooldown line shows the real mean attack cycle. With Improved Tooltips loaded, the
# _wl_* functions below replace two of its own. See docs/architecture.md, "Weapon card".

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")

const IMPROVED_TOOLTIPS_ID := "_wl-ImprovedTooltips"


# After the game has filled the card, rewrites its cooldown figures (unless Improved Tooltips does).
func set_item(item_data: ItemParentData, player_index: int, item_count: = 1) -> void :
	.set_item(item_data, player_index, item_count)

	if ModLoaderMod.is_mod_loaded(IMPROVED_TOOLTIPS_ID):
		return
	if not (item_data is WeaponData) or not get_weapon_stats().visible:
		return

	var current_stats: WeaponStats = item_data.get_current_stats(player_index)
	var text: String = get_weapon_stats().bbcode_text
	text = _tas_replace_cooldown(text, item_data, current_stats, player_index, false)
	if current_stats.additional_cooldown_every_x_shots != -1:
		text = _tas_replace_cooldown(text, item_data, current_stats, player_index, true)
	get_weapon_stats().bbcode_text = text


# Replaces the first occurrence of the game's cooldown number with the real mean cycle.
func _tas_replace_cooldown(text: String, weapon_data: WeaponData, current_stats: WeaponStats, player_index: int, big_reload: bool) -> String:
	var nb_weapons: int = RunData.get_player_weapons_ref(player_index).size()
	var ticks := Timing.mean_cycle_ticks(weapon_data, current_stats, player_index, nb_weapons, big_reload)
	if ticks < 0.0:
		return text

	var shown: float = current_stats.get_cooldown_value(player_index, current_stats.additional_cooldown_multiplier if big_reload else 1.0)
	var old_text := _tas_seconds_text(shown)
	var at := text.find(old_text)
	if at < 0:
		return text
	return text.substr(0, at) + _tas_seconds_text(ticks / 60.0) + text.substr(at + old_text.length())


# The way the game writes a cooldown (weapon_stats.gd, get_cooldown_text).
func _tas_seconds_text(seconds: float) -> String:
	return str(stepify(seconds, 0.001 if seconds < 0.2 else 0.01)) + "s"


# ---------------------------------------------------------------------------------------------
# Improved Tooltips

# [shortest, longest, mean] attack cycle in ticks. Replaces Improved Tooltips' function of the same name.
func _wl_get_weapon_cds(weapon_data: WeaponData, base_stats: WeaponStats, current_stats: WeaponStats, big_reload: bool, player_index: int):
	var nb_weapons: int = RunData.get_player_weapons_ref(player_index).size()
	var zero_stats: Resource = null
	if Timing.attack_speed(current_stats, player_index) != 0.0:
		zero_stats = _tas_zero_speed_stats(weapon_data, base_stats, current_stats, player_index)
	var figures := Timing.cycle_figures(weapon_data, base_stats, current_stats, player_index, nb_weapons, big_reload, zero_stats)
	if figures.size() > 0:
		return [int(floor(figures[0] + Timing.EPS)), int(ceil(figures[1] - Timing.EPS)), figures[2]]
	return _tas_wl_untimed_cds(weapon_data, base_stats, current_stats, big_reload, player_index)


# The +0% stats, kept for the frame: the breakpoint search asks for the same weapon up to 400 times.
var _tas_zero_cache := {}

func _tas_zero_speed_stats(weapon_data: WeaponData, base_stats: WeaponStats, current_stats: WeaponStats, player_index: int) -> Resource:
	var frame := Engine.get_idle_frames()
	var key := [base_stats.get_instance_id(), player_index]
	var entry = _tas_zero_cache.get(key)
	if entry == null or entry[0] != frame:
		if _tas_zero_cache.size() >= 32:
			_tas_zero_cache.clear()
		entry = [frame, Timing.zero_speed_stats(base_stats, current_stats, player_index, weapon_data.sets, weapon_data.effects)]
		_tas_zero_cache[key] = entry
	return entry[1]


# What Improved Tooltips' own _wl_get_weapon_cds does, for a weapon this mod does not time.
func _tas_wl_untimed_cds(weapon_data: WeaponData, base_stats: WeaponStats, current_stats: WeaponStats, big_reload: bool, player_index: int):
	if weapon_data.scene == null:
		return null
	var weapon: Node = weapon_data.scene.instance()
	var behavior = call("find_shooting_behaviors", weapon)
	var cds = null
	if behavior is AnimatedHitboxShootingBehavior:
		var animation_player = weapon.get_node_or_null("AnimationPlayer")
		if animation_player != null:
			var animation_length := int(ceil(60 * animation_player.get_animation(behavior.animation_name).length))
			cds = call("_wl_get_animated_hitbox_shooting_behavior_duration", current_stats, animation_length, big_reload, player_index)
	elif behavior is RangedWeaponShootingBehavior:
		cds = call("_wl_get_ranged_weapon_shooting_behavior_duration", current_stats, big_reload, player_index)
	elif behavior is MeleeWeaponShootingBehavior:
		cds = call("_wl_get_melee_weapon_shooting_behavior_duration", base_stats, current_stats, big_reload, player_index)
	weapon.free()
	return cds


# The text of one breakpoint: Improved Tooltips' three formats, without its "!".repeat(-1) for a
# step under half a tick.
func _wl_get_breakpoint_text(bp: float, frame_change: float, frames: float) -> String:
	var value: String = Text.get_value(str(bp), true, true)
	match Text.call("_wl_get_setting_string", "attack_speed_breakpoints"):
		"SHOW":
			return value + "!".repeat(int(max(0.0, round(abs(frame_change)) - 1.0)))
		"SHOW_FRAMES":
			return "%s: %s" % [value, Text.get_value(str(stepify(frame_change, 0.1)), true, false)]
		"SHOW_DPS":
			var dps_change := -100.0 * frame_change / frames
			return "%s: %s" % [value, Text.get_value(Text.call("_wl_get_str_float", dps_change), true, true)]
	return ""
