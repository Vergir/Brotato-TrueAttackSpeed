extends Reference

# The mod's rule as static functions: how long one attack cycle lasts, in physics ticks (60 per second).
# The rule and its reasons are in docs/architecture.md.

# Must not name the child classes listed in docs/architecture.md ("The Mod Loader and child classes").

const EPS := 0.0001

# Shortest cycles in ticks (docs/architecture.md, rule 5).
const MELEE_MIN_THRUST := 5.0
const MELEE_MIN_SWEEP := 6.0
const RANGED_MIN := 1.0
const ANIMATED_MIN_SHOOTING := 4.0
const ANIMATED_MIN := 5.0
const BOOMERANG_MIN := 2.0
# Distance from the player to where a Boomerang starts its flight, for the flight estimate.
const BOOMERANG_START_DISTANCE := 25.0


# Rendered frames one chained tween of `duration` seconds takes in the unmodded game at 60 FPS.
static func tween_frames(duration: float) -> int:
	return int(floor(duration * 60.0 + EPS)) + 2


# Attack Speed as the game applies it to this weapon's cooldown (weapon_service.gd, init_base_stats).
static func attack_speed(current_stats: Resource, player_index: int) -> float:
	return (Utils.get_stat(Keys.stat_attack_speed_hash, player_index) + current_stats.attack_speed_mod) / 100.0


# The game divides recoil_duration by (1 + Attack Speed) when Attack Speed is positive; undo that.
static func base_recoil_duration(current_stats: Resource, atk_spd: float) -> float:
	if atk_spd > 0.0:
		return current_stats.recoil_duration * (1.0 + atk_spd)
	return current_stats.recoil_duration


# ---------------------------------------------------------------------------------------------
# The shooting state

# Ticks each stage of one attack lasts. `durations`: the stage durations in seconds now;
# `base_durations`: the same stages at +0% Attack Speed.
static func stage_ticks(durations: Array, base_durations: Array, atk_spd: float) -> Array:
	var ticks := []
	var total := -1.0
	var nominal := 0.0
	for duration in durations:
		var frames := tween_frames(duration)
		ticks.append(float(frames))
		total += frames
		nominal += duration * 60.0
	# Unmodded at 60 FPS the cooldown starts counting one tick before the last frame of the chain is over.
	ticks[ticks.size() - 1] -= 1.0

	if atk_spd <= 0.0:
		return ticks

	var base_extra := -1.0
	for duration in base_durations:
		base_extra += tween_frames(duration) - duration * 60.0
	var scale := (nominal + base_extra / (1.0 + atk_spd)) / total
	for i in ticks.size():
		ticks[i] *= scale
	return ticks


# Ticks of a gun's two recoil stages.
static func ranged_stage_ticks(current_stats: Resource, player_index: int) -> Array:
	var atk_spd := attack_speed(current_stats, player_index)
	var recoil: float = current_stats.recoil_duration
	var base_recoil := base_recoil_duration(current_stats, atk_spd)
	return stage_ticks([recoil, recoil], [base_recoil, base_recoil], atk_spd)


# The same stages at +0% Attack Speed: whole numbers, the unmodded frame counts.
static func ranged_base_stage_ticks(current_stats: Resource, player_index: int) -> Array:
	var base_recoil := base_recoil_duration(current_stats, attack_speed(current_stats, player_index))
	return stage_ticks([base_recoil, base_recoil], [base_recoil, base_recoil], 0.0)


# `distance`: the sweep distance of this attack; negative = the weapon's max range (what a tooltip assumes).
# Ticks of a melee swing's three (thrust) or four (sweep) stages.
static func melee_stage_ticks(current_stats: Resource, player_index: int, thrust: bool, distance: float = -1.0) -> Array:
	var now := MeleeShootingData.new(current_stats, player_index)
	if distance >= 0.0:
		now.update_atk_duration(distance)
	return stage_ticks(_melee_durations(now, current_stats.recoil_duration, thrust),
			_melee_base_durations(current_stats, player_index, thrust, distance), now.atk_spd)


static func melee_base_stage_ticks(current_stats: Resource, player_index: int, thrust: bool, distance: float = -1.0) -> Array:
	var durations := _melee_base_durations(current_stats, player_index, thrust, distance)
	return stage_ticks(durations, durations, 0.0)


static func _melee_base_durations(current_stats: Resource, player_index: int, thrust: bool, distance: float) -> Array:
	var base := MeleeShootingData.new(current_stats, player_index, false)
	if distance >= 0.0:
		base.update_atk_duration(distance)
	return _melee_durations(base, base_recoil_duration(current_stats, attack_speed(current_stats, player_index)), thrust)


static func _melee_durations(data: MeleeShootingData, recoil: float, thrust: bool) -> Array:
	if thrust:
		return [recoil, data.atk_duration / 2.0, data.back_duration]
	return [recoil, data.atk_duration / 4.0, data.atk_duration / 4.0, data.back_duration]


static func sum(values: Array) -> float:
	var total := 0.0
	for value in values:
		total += value
	return total


# ---------------------------------------------------------------------------------------------
# The cooldown

# The whole ticks a cooldown can take and how likely each is: [[ticks, probability], ...].
static func cooldown_distribution(cooldown: float, nb_weapons: int) -> Array:
	var n: float = clamp(nb_weapons, 1, 6)
	var spread: float = min(n * cooldown / 5.0, n * 5.0)
	var low: float = max(1.0, cooldown - spread)
	var high: float = cooldown + spread
	if high - low < EPS:
		return [[max(1.0, ceil(low - EPS)), 1.0]]

	var out := []
	var x := low
	while x < high - EPS:
		var next: float = min(high, floor(x) + 1.0)
		out.append([floor(x) + 1.0, (next - x) / (high - low)])
		x = next
	return out


# The cooldown after the shot that triggers a weapon's long reload: no random spread.
static func big_reload_ticks(stats: Resource) -> float:
	return max(1.0, ceil(stats.cooldown * stats.additional_cooldown_multiplier - EPS))


# One draw of the cooldown in whole ticks. `spread` comes from the weapon (get_max_rand_cooldown).
static func draw_cooldown_ticks(cooldown: float, spread: float) -> float:
	return max(1.0, ceil(rand_range(max(1.0, cooldown - spread), cooldown + spread) - EPS))


# The weapon's stats as the game computes them with its Attack Speed at exactly +0%.
# `current_stats` must come from `base_stats` as they are now.
static func zero_speed_stats(base_stats: Resource, current_stats: Resource, player_index: int, sets: Array, effects: Array) -> Resource:
	var args := WeaponServiceInitStatsArgs.new()
	args.sets = sets
	args.effects = effects

	var kept: float = base_stats.attack_speed_mod
	base_stats.attack_speed_mod = kept - (Utils.get_stat(Keys.stat_attack_speed_hash, player_index) + current_stats.attack_speed_mod)
	var zero: Resource
	if "projectile_speed" in base_stats:   # ranged weapon stats
		zero = WeaponService.init_ranged_stats(base_stats, player_index, false, args)
	else:
		zero = WeaponService.init_melee_stats(base_stats, player_index, args)
	base_stats.attack_speed_mod = kept
	return zero


# Ball and Chain's "weapons have a minimum cooldown", in ticks; 0 without it.
static func min_cycle_effect(player_index: int) -> float:
	var values = RunData.get_player_effect(Keys.minimum_weapon_cooldowns_hash, player_index)
	if values is Array and not values.empty():
		return float(values.back())
	return 0.0


# ---------------------------------------------------------------------------------------------
# The cycle

# What Attack Speed does to the length of a cycle: 1 / (1 + a) when positive, 1 + |a| when negative.
static func cycle_factor(atk_spd: float) -> float:
	if atk_spd > 0.0:
		return 1.0 / (1.0 + atk_spd)
	return 1.0 + abs(atk_spd)


# One attack cycle with Attack Speed other than +0%, in ticks (not whole; the caller carries the fraction).
static func scaled_cycle_ticks(base_shooting: float, base_cooldown: float, atk_spd: float, floor_ticks: float) -> float:
	return max((base_shooting + base_cooldown) * cycle_factor(atk_spd), floor_ticks)


# [shortest, longest, mean] ticks from one attack to the next, or [] for a weapon this mod does not time.
# `big_reload`: the cycle after the shot that triggers the long reload.
static func cycle_figures(weapon_data: Resource, base_stats: Resource, current_stats: Resource, player_index: int, nb_weapons: int, big_reload: bool = false, zero_stats: Resource = null) -> Array:
	var info := weapon_info(weapon_data)
	var kind: String = info.kind
	if kind == "":
		return []

	# Each variant: [shooting ticks now, shooting ticks at +0%, shortest possible cycle].
	var variants := []
	if kind == "ranged":
		variants.append([sum(ranged_stage_ticks(current_stats, player_index)),
				sum(ranged_base_stage_ticks(current_stats, player_index)), RANGED_MIN])
	elif kind == "animated":
		variants.append([info.animation_ticks, info.animation_ticks, ANIMATED_MIN])
	elif kind == "boomerang":
		var flight := boomerang_flight_ticks(current_stats.max_range, current_stats.projectile_speed)
		variants.append([flight, flight, BOOMERANG_MIN])
	else:
		var thrust: bool = base_stats.attack_type == base_stats.AttackType.THRUST
		for is_thrust in ([true, false] if base_stats.alternate_attack_type else [thrust]):
			variants.append([sum(melee_stage_ticks(current_stats, player_index, is_thrust)),
					sum(melee_base_stage_ticks(current_stats, player_index, is_thrust)),
					MELEE_MIN_THRUST if is_thrust else MELEE_MIN_SWEEP])

	var atk_spd := attack_speed(current_stats, player_index)
	var scaled := atk_spd != 0.0
	var cooldown_stats := current_stats
	var floor_effect := 0.0
	if scaled:
		cooldown_stats = zero_stats if zero_stats != null else zero_speed_stats(base_stats, current_stats, player_index, weapon_data.sets, weapon_data.effects)
		floor_effect = min_cycle_effect(player_index)
	var cooldowns := [[big_reload_ticks(cooldown_stats), 1.0]] if big_reload else cooldown_distribution(cooldown_stats.cooldown, nb_weapons)

	var shortest := INF
	var longest := 0.0
	var mean := 0.0
	for variant in variants:
		for entry in cooldowns:
			var cycle: float = variant[0] + entry[0]
			if scaled:
				cycle = scaled_cycle_ticks(variant[1], entry[0], atk_spd, max(variant[2], floor_effect))
			shortest = min(shortest, cycle)
			longest = max(longest, cycle)
			mean += cycle * entry[1] / variants.size()
	return [shortest, longest, mean]


# Mean ticks from one attack to the next, or -1 for a weapon this mod does not time.
# `current_stats`: the weapon's stats under the player's stats as they are now.
static func mean_cycle_ticks(weapon_data: Resource, current_stats: Resource, player_index: int, nb_weapons: int, big_reload: bool = false) -> float:
	var figures := cycle_figures(weapon_data, weapon_data.stats, current_stats, player_index, nb_weapons, big_reload)
	return figures[2] if figures.size() > 0 else -1.0


# ---------------------------------------------------------------------------------------------
# Kinds of weapon

# { kind, animation_ticks }; kind: "ranged", "melee", "animated" (Whip, Flail), "boomerang" or "" (not timed).
# Kept on the weapon's data, because finding it needs an instance of the weapon's scene.
static func weapon_info(weapon_data: Resource) -> Dictionary:
	if weapon_data.has_meta("tas_info"):
		return weapon_data.get_meta("tas_info")

	var info := {"kind": "", "animation_ticks": 0.0}
	if weapon_data.scene != null:
		var weapon: Node = weapon_data.scene.instance()
		for child in weapon.get_children():
			if child is RangedWeaponShootingBehavior:
				# The Boomerang's behaviour keeps the projectiles that are out.
				info.kind = "boomerang" if "_projectiles_in_flight" in child else "ranged"
			elif child is MeleeWeaponShootingBehavior:
				info.kind = "melee"
			elif child is AnimatedHitboxShootingBehavior:
				var player: AnimationPlayer = weapon.get_node_or_null("AnimationPlayer")
				if player != null and player.has_animation(child.animation_name):
					info.kind = "animated"
					info.animation_ticks = animation_ticks(player.get_animation(child.animation_name).length)
			else:
				continue
			break
		weapon.free()
	weapon_data.set_meta("tas_info", info)
	return info


static func behavior_kind(weapon_data: Resource) -> String:
	return weapon_info(weapon_data).kind


# Ticks the shooting state of a Whip or Flail lasts unmodded: its animation runs on physics ticks.
static func animation_ticks(length: float) -> float:
	return max(1.0, ceil(length * 60.0 - EPS) - 1.0)


# The Boomerang's flight numbers in game 1.2.0.3; boomerang_flight_constants() reads the current ones.
const BOOMERANG_FLIGHT := {
	"OUT_DURATION_FACTOR": 1.6, "APEX_DURATION": 0.15, "APEX_SPEED_FACTOR": 0.25, "BACK_MAX_SPEED_FACTOR": 1.2,
	"BACK_ACCELERATION_FACTOR": 2.0, "CATCH_DISTANCE": 30.0, "MAX_FLIGHT_TIME": 4.0,
}

static func boomerang_flight_constants() -> Dictionary:
	var values := BOOMERANG_FLIGHT.duplicate()
	var script: Script = load("res://projectiles/boomerang/boomerang_projectile.gd")
	while script != null:
		var constants: Dictionary = script.get_script_constant_map()
		for key in values:
			if constants.has(key):
				values[key] = constants[key]
		script = script.get_base_script()
	return values


# Ticks from a Boomerang's throw to its catch, unmodded: player standing still, target at `reach`.
static func boomerang_flight_ticks(reach: float, projectile_speed: float) -> float:
	var c := boomerang_flight_constants()
	var speed: float = max(1.0, projectile_speed)
	var dt := 1.0 / 60.0
	var out_duration: float = reach / speed * c.OUT_DURATION_FACTOR
	var limit: float = c.MAX_FLIGHT_TIME * 60.0
	var ticks := 0.0
	var time := 0.0
	var x := 0.0

	# Out.
	while ticks < limit:
		ticks += 1.0
		time += dt
		var u: float = min(1.0, time / out_duration)
		x = reach * (1.0 - (1.0 - u) * (1.0 - u))
		if u >= 1.0:
			break
	# Apex.
	time = 0.0
	while ticks < limit:
		ticks += 1.0
		time += dt
		x += speed * c.APEX_SPEED_FACTOR * dt
		if time >= c.APEX_DURATION:
			break
	# Back.
	time = 0.0
	while ticks < limit:
		ticks += 1.0
		time += dt
		var left := x + BOOMERANG_START_DISTANCE
		if left <= c.CATCH_DISTANCE:
			break
		var back_speed: float = min(speed * c.BACK_MAX_SPEED_FACTOR,
				speed * (c.APEX_SPEED_FACTOR + c.BACK_ACCELERATION_FACTOR * time))
		x -= min(back_speed * dt, left)
	return ticks


# ---- Turrets and other structures that shoot (extensions/entities/structures/turret/turret.gd) ----

# The least cooldown the mod leaves between a turret's shoot animation and the next one.
const TURRET_MIN_COOLDOWN := 1.0
# The game's own least cooldown (weapon_service.gd, MIN_COOLDOWN).
const TURRET_GAME_MIN_COOLDOWN := 2.0


# Speed of a turret's shoot animation at structure attack speed 0 (the game's set_shooting_speed).
static func turret_base_animation_speed(animation_length_ticks: float, data_speed: float, cooldown: float, max_speed: float) -> float:
	var base_cooldown: float = max(TURRET_GAME_MIN_COOLDOWN, cooldown)
	if data_speed > 0.0 and animation_length_ticks / data_speed > base_cooldown:
		return min(animation_length_ticks / base_cooldown, max_speed)
	return data_speed


# Mean ticks from one shot of a turret to the next, with a target in range all the time.
# The parameters are described in docs/architecture.md, "For other mods".
static func turret_mean_cycle_ticks(animation_length: float, data_speed: float, cooldown: float, structure_attack_speed: float, max_speed: float = 3.0) -> float:
	var speed: float = turret_base_animation_speed(animation_length * 60.0, data_speed, cooldown, max_speed)
	var base: float = animation_ticks(animation_length / speed) + max(TURRET_GAME_MIN_COOLDOWN, cooldown) + 0.5
	return base * cycle_factor(structure_attack_speed)
