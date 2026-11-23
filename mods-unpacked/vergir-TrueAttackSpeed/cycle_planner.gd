extends Reference

# Plans one attack cycle in whole ticks when Attack Speed is not +0%; a shooting behaviour owns one.
# How it is used: docs/architecture.md, "The planner".

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")

var carry := 0.0
# The cooldown planned for the attack that was just started, in ticks; -1 = let the game draw it.
var planned_cooldown := -1.0

# For the tests: one entry per planned attack (the fields are listed in docs/architecture.md).
var log_enabled := false
var log_entries := []

var _cycle := 0
var _base_shooting := 0.0
var _base_cooldown := 0.0
var _target := 0.0
var _atk_spd := 0.0
var _carry_before := 0.0
var _shooting_ticks := 0
var _zero_stats := {}
# The cooldown this planner has put on the weapon, as it should be found on the next tick; -1 = none.
var _guarded := -1.0
var _guarded_stats := 0


# Draws the +0% cooldown and returns the whole ticks this cycle may take.
func plan(weapon: Node, base_shooting: float, atk_spd: float) -> int:
	var zero: Resource = _zero_speed_stats(weapon)
	if weapon.is_big_reload_active():
		_base_cooldown = Timing.big_reload_ticks(zero)
	else:
		_base_cooldown = Timing.draw_cooldown_ticks(zero.cooldown, weapon.get_max_rand_cooldown(zero.cooldown))
	_base_shooting = base_shooting
	_atk_spd = atk_spd
	_target = Timing.scaled_cycle_ticks(base_shooting, _base_cooldown, atk_spd, Timing.min_cycle_effect(weapon.player_index))

	_carry_before = carry
	carry += _target
	_cycle = int(max(1.0, floor(carry + Timing.EPS)))
	return _cycle


# Takes the real length of the shooting state; the cooldown fills the rest of the cycle.
func commit(shooting_ticks: int) -> void :
	var cooldown := int(max(1, _cycle - shooting_ticks))
	_shooting_ticks = shooting_ticks
	planned_cooldown = float(cooldown)
	# A cycle that cannot be as short as wanted does not pile up a debt.
	carry = max(carry - shooting_ticks - cooldown, -1.0)
	if log_enabled:
		log_entries.append([_base_shooting, _base_cooldown, _target, shooting_ticks + cooldown, _atk_spd, 0])


# +0% Attack Speed: the game draws the cooldown itself.
func skip() -> void :
	planned_cooldown = -1.0
	_guarded = -1.0


# Puts the planned cooldown on the weapon, once the weapon has drawn its own.
func apply(weapon: Node) -> void :
	var planned := take_cooldown()
	if planned < 0.0 or not is_instance_valid(weapon):
		return
	weapon._current_cooldown = planned
	_guarded = planned
	_guarded_stats = weapon.current_stats.get_instance_id()


# Puts the planned cooldown back after the game has recalculated the weapon's stats and cut it.
# Call on every physics tick, before the behaviour changes the weapon's shooting state.
func guard(weapon: Node, delta: float) -> void :
	if _guarded < 0.0:
		return
	var found: float = weapon._current_cooldown
	if found <= 0.0:
		_guarded = -1.0     # over, or something has made the weapon ready (main.gd does for some effects)
		return

	# The weapon comes before its behaviour in a tick and counts down only while it is not shooting.
	var expected: float = _guarded if weapon._is_shooting else max(_guarded - 60.0 * delta, 0.0)
	var stats_id: int = weapon.current_stats.get_instance_id()
	if stats_id != _guarded_stats:
		_guarded_stats = stats_id
		var limit := _cooldown_limit(weapon)
		# +0% now: the game's own limit stands.
		var kept: float = found if limit < 0.0 else min(expected, limit)
		if kept < expected - Timing.EPS and log_enabled and not log_entries.empty():
			var cut := int(round(expected - kept))
			var entry: Array = log_entries.back()
			entry[3] -= cut
			entry[5] += cut
		weapon._current_cooldown = kept
		found = kept
	# Any other change is somebody else's and is left alone.
	_guarded = found


# The longest cooldown the cycle in progress may have after a recalculation of the weapon's stats.
func _cooldown_limit(weapon: Node) -> float:
	var atk_spd := Timing.attack_speed(weapon.current_stats, weapon.player_index)
	if atk_spd == 0.0:
		return -1.0
	var zero: Resource = _zero_speed_stats(weapon)
	var base_cooldown: float = Timing.big_reload_ticks(zero) if weapon.is_big_reload_active() else max(1.0, ceil(zero.cooldown - Timing.EPS))
	var cycle := Timing.scaled_cycle_ticks(_base_shooting, base_cooldown, atk_spd, Timing.min_cycle_effect(weapon.player_index))
	return max(1.0, floor(_carry_before + cycle + Timing.EPS) - _shooting_ticks)


# Returns the planned cooldown once and forgets it.
func take_cooldown() -> float:
	var value := planned_cooldown
	planned_cooldown = -1.0
	return value


# The game makes new `current_stats` whenever the player's stats change, so they are the cache key.
func _zero_speed_stats(weapon: Node) -> Resource:
	var key: int = weapon.current_stats.get_instance_id()
	if not _zero_stats.has(key):
		if _zero_stats.size() >= 8:
			_zero_stats.clear()
		_zero_stats[key] = Timing.zero_speed_stats(weapon.stats, weapon.current_stats, weapon.player_index, weapon.weapon_sets, weapon.effects)
	return _zero_stats[key]
