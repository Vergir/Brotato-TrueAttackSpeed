extends "res://weapons/shooting_behaviors/ranged_weapon_shooting_behavior.gd"

# Guns, and the Boomerang (the part at the end): the shooting state lasts a number of physics ticks
# instead of two recoil tweens on rendered frames. See docs/architecture.md.

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
const CyclePlanner = preload("res://mods-unpacked/vergir-TrueAttackSpeed/cycle_planner.gd")

var tas_planner := CyclePlanner.new()
var _tas_ticks_left := 0
var _tas_rest_position := Vector2.ZERO

# The Boomerang.
var _tas_flight_checked := false
var _tas_has_flights := false
var _tas_flying := false
var _tas_flight_atk_spd := 0.0
var _tas_flight_ticks := 0
var _tas_flight_extra_steps := 0
var _tas_flight_debt := 0.0
var _tas_in_extra_step := false


# The game's shoot(), with the shooting state counted in ticks and the cycle planned.
func shoot(_distance: float) -> void :
	SoundManager.play(Utils.get_rand_element(_parent.current_stats.shooting_sounds), _parent.current_stats.sound_db_mod, 0.2)

	_parent.set_shooting(true)

	var attack_id: = _get_next_attack_id()
	for i in _parent.current_stats.nb_projectiles:
		var proj_rotation = rand_range(_parent.rotation - _parent.current_stats.projectile_spread, _parent.rotation + _parent.current_stats.projectile_spread)
		var projectile = shoot_projectile(proj_rotation, Vector2(cos(proj_rotation), sin(proj_rotation)))
		projectile._hitbox.player_attack_id = attack_id

	_tas_play_recoil()

	var stats = _parent.current_stats
	var player_index: int = _parent.player_index
	var atk_spd := Timing.attack_speed(stats, player_index)
	var shooting := int(round(Timing.sum(Timing.ranged_stage_ticks(stats, player_index))))
	if atk_spd != 0.0:
		var cycle := tas_planner.plan(_parent, Timing.sum(Timing.ranged_base_stage_ticks(stats, player_index)), atk_spd)
		shooting = int(clamp(shooting, 0, cycle - 1))
		tas_planner.commit(shooting)
		call_deferred("_tas_apply_cooldown")
	else:
		tas_planner.skip()

	_tas_ticks_left = shooting
	if _tas_ticks_left <= 0:
		_parent.set_shooting(false)


# Replaces the cooldown the weapon draws right after shoot() returns; runs deferred, in the same flush.
func _tas_apply_cooldown() -> void :
	tas_planner.apply(_parent)


func _physics_process(delta: float) -> void :
	tas_planner.guard(_parent, delta)
	if not _tas_flight_checked:
		_tas_flight_checked = true
		_tas_has_flights = "_projectiles_in_flight" in self
	if _tas_has_flights:
		_tas_flight_tick(delta)
		return

	if _tas_ticks_left <= 0:
		return
	_tas_ticks_left -= 1
	if _tas_ticks_left == 0:
		_parent.set_shooting(false)


# Recoil out and back as one animation that nothing waits for; it always starts from the rest position.
func _tas_play_recoil() -> void :
	var sprite = _parent.sprite
	var tween: Tween = _parent.tween
	var recoil_duration: float = _parent.current_stats.recoil_duration

	if not tween.is_active():
		_tas_rest_position = sprite.position

	var recoil_position := Vector2(_tas_rest_position.x - _parent.current_stats.recoil, _tas_rest_position.y)

	var _removed = tween.remove(sprite, "position")
	sprite.position = _tas_rest_position
	var _a = tween.interpolate_property(sprite, "position", _tas_rest_position, recoil_position, recoil_duration, Tween.TRANS_EXPO, Tween.EASE_OUT)
	var _b = tween.interpolate_property(sprite, "position", recoil_position, _tas_rest_position, recoil_duration, Tween.TRANS_EXPO, Tween.EASE_OUT, recoil_duration)
	var _started = tween.start()


# ---------------------------------------------------------------------------------------------
# The Boomerang (docs/architecture.md, "Boomerang")

# Counts the flight's ticks and, with positive Attack Speed, makes the projectile take extra steps.
func _tas_flight_tick(delta: float) -> void :
	var flying: Array = get("_projectiles_in_flight")
	if flying.empty():
		_tas_flying = false
		return

	if not _tas_flying:
		# The first tick after a throw.
		_tas_flying = true
		_tas_flight_atk_spd = Timing.attack_speed(_parent.current_stats, _parent.player_index)
		_tas_flight_ticks = 0
		_tas_flight_extra_steps = 0
		_tas_flight_debt = 0.0
		for projectile in flying:
			if not projectile.is_connected("returned", self, "_tas_on_projectile_returned"):
				var _error = projectile.connect("returned", self, "_tas_on_projectile_returned", [], CONNECT_ONESHOT)

	_tas_flight_ticks += 1
	if _tas_flight_atk_spd <= 0.0:
		return

	# The extra steps of this tick; the projectile takes its own step afterwards.
	_tas_flight_debt += _tas_flight_atk_spd
	_tas_in_extra_step = true
	while _tas_flight_debt >= 1.0 - Timing.EPS and _tas_flying:
		_tas_flight_debt -= 1.0
		_tas_flight_extra_steps += 1
		for projectile in flying.duplicate():
			if is_instance_valid(projectile):
				projectile._physics_process(delta)
	_tas_in_extra_step = false


# Plans the cycle when the last projectile is back. It counts the projectiles itself: the game's
# handler of the same signal may run before or after this one.
func _tas_on_projectile_returned(projectile: Node) -> void :
	var flying: Array = get("_projectiles_in_flight")
	if not _tas_flying or flying.size() - (1 if flying.has(projectile) else 0) > 0:
		return
	_tas_flying = false
	if _tas_flight_atk_spd == 0.0 or not is_instance_valid(_parent):
		return

	# The projectile's own step of this tick has been taken unless the catch came in an extra step.
	var own_steps := _tas_flight_ticks - 1 if _tas_in_extra_step else _tas_flight_ticks
	var _cycle := tas_planner.plan(_parent, own_steps + _tas_flight_extra_steps, _tas_flight_atk_spd)
	tas_planner.commit(_tas_flight_ticks)
	tas_planner.apply(_parent)
