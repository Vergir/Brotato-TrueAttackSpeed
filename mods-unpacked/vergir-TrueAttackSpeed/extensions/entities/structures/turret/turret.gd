extends "res://entities/structures/turret/turret.gd"

# Turrets and the structures built on them: structure attack speed scales the whole cycle (shoot
# animation plus cooldown), not only the cooldown. See docs/architecture.md.

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
const TAS_LOG_SIZE := 64

var _tas_data_speed := 1.0
# Structure attack speed (1.0 = +100%) of the shot that is being prepared or played. 0: unmodded.
var _tas_speed := 0.0
var _tas_speed_changed := false
# Ticks the shoot animation has been playing.
var _tas_elapsed := 0
var _tas_carry := 0.0
# For the tests: the last cycles (the fields are listed in docs/architecture.md).
var tas_log := []
var tas_cycles := 0


func set_data(data: Resource) -> void :
	.set_data(data)
	if "shooting_animation_speed" in data:
		_tas_data_speed = data.shooting_animation_speed


# Sets the animation speed for the next shot. Runs before the game's own _physics_process of the tick.
func _physics_process(_delta: float) -> void :
	if dead:
		return
	if _is_shooting:
		_tas_elapsed += 1
		return
	_tas_elapsed = 0
	if _cooldown > 1.5 or stats == null or stats.cooldown <= 0:
		return
	_tas_speed = WeaponService.get_structure_attack_speed(player_index) / 100.0
	if reset_shooting_speed_on_shoot:
		# A shot the game has just made instant (set_instant_shoot) keeps the game's animation speed.
		return
	if _tas_speed != 0.0:
		_shooting_speed = _tas_animation_speed(_tas_speed)
		_tas_speed_changed = true
	elif _tas_speed_changed:
		_shooting_speed = _tas_animation_speed(0.0)
		_tas_speed_changed = false


# Sets the cooldown to what is left of the planned cycle, after the game has drawn its own.
func _on_AnimationPlayer_animation_finished(anim_name: String) -> void :
	var scaled: bool = anim_name == "shoot" and not dead and _tas_speed != 0.0 and stats != null and stats.cooldown > 0
	var elapsed := _tas_elapsed
	._on_AnimationPlayer_animation_finished(anim_name)
	if not scaled:
		return
	var base_animation: float = Timing.animation_ticks(_tas_animation_length() / _tas_animation_speed(0.0))
	var base_cooldown: float = ceil(_tas_draw_base_cooldown() - Timing.EPS)
	var factor: float = Timing.cycle_factor(_tas_speed)
	var want: float
	if elapsed > 0:
		want = (base_animation + base_cooldown) * factor - elapsed + _tas_carry
	else:
		# The shot was called off halfway (no target left): only the cooldown part.
		want = base_cooldown * factor
	var ticks: float = max(Timing.TURRET_MIN_COOLDOWN, floor(want + Timing.EPS))
	_tas_carry = want - ticks if want >= Timing.TURRET_MIN_COOLDOWN and elapsed > 0 else 0.0
	# Half a tick short: the game counts the cooldown down in steps of 60 * delta, which is not exactly 1.
	_cooldown = ticks - 0.5
	tas_cycles += 1
	tas_log.push_back([base_animation, base_cooldown, _tas_speed, elapsed, ticks])
	if tas_log.size() > TAS_LOG_SIZE:
		tas_log.pop_front()


func _tas_animation_length() -> float:
	return _animation_player.get_animation("shoot").length


# The game's animation speed at structure attack speed 0, times 1 + structure attack speed when positive.
func _tas_animation_speed(structure_speed: float) -> float:
	var length_ticks: float = _tas_animation_length() * 60.0
	var speed: float = Timing.turret_base_animation_speed(length_ticks, _tas_data_speed, stats.cooldown, max_turret_anim_speed)
	if structure_speed > 0.0:
		speed = min(speed * (1.0 + structure_speed), max(speed, length_ticks))
	return speed


# The cooldown the game would draw at structure attack speed 0 (_get_next_cooldown).
func _tas_draw_base_cooldown() -> float:
	if is_big_reload_active():
		return max(Timing.TURRET_GAME_MIN_COOLDOWN, float(int(stats.cooldown * stats.additional_cooldown_multiplier)))
	var cooldown: float = max(Timing.TURRET_GAME_MIN_COOLDOWN, float(stats.cooldown))
	return rand_range(max(1.0, cooldown * 0.7), cooldown * 1.3)
