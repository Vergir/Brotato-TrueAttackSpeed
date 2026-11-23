extends "res://weapons/shooting_behaviors/melee_weapon_shooting_behavior.gd"

# Melee: the swing's moves run as stages of whole physics ticks instead of tweens on rendered frames.
# See docs/architecture.md.

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
const CyclePlanner = preload("res://mods-unpacked/vergir-TrueAttackSpeed/cycle_planner.gd")

enum TasEvent { NONE, STRIKE_START, STRIKE_END, DONE }

# Each stage: { targets: {property: value}, trans: Tween transition, ticks: int, event: TasEvent }
var tas_planner := CyclePlanner.new()
var _tas_stages := []
var _tas_stage := -1
var _tas_ticks_left := 0
var _tas_carry := 0.0


# The game's shoot(), with the swing built as stages and the cycle planned.
func shoot(distance: float) -> void :
	var initial_position: Vector2 = _parent.sprite.position
	shooting_data = MeleeShootingData.new(_parent.current_stats, _parent.player_index)

	_parent.set_shooting(true)
	_parent.tween.playback_process_mode = Tween.TWEEN_PROCESS_PHYSICS
	_parent._hitbox.player_attack_id = _get_next_attack_id()

	var stats = _parent.current_stats
	var player_index: int = _parent.player_index
	var thrust: bool = _parent.next_attack_type == MeleeAttackType.THRUST
	var atk_distance := -1.0
	if not thrust:
		atk_distance = min(stats.max_range, max(MIN_SWEEP_DISTANCE, distance))
		shooting_data.update_atk_duration(atk_distance)

	var ticks := Timing.melee_stage_ticks(stats, player_index, thrust, atk_distance)
	var scaled: bool = shooting_data.atk_spd != 0.0
	if scaled:
		var base_shooting := Timing.sum(Timing.melee_base_stage_ticks(stats, player_index, thrust, atk_distance))
		var cycle := tas_planner.plan(_parent, base_shooting, shooting_data.atk_spd)
		# The swing may take all of the cycle but 1 tick, which stays for the cooldown.
		var total := Timing.sum(ticks)
		if total > cycle - 1.0:
			for i in ticks.size():
				ticks[i] *= (cycle - 1.0) / total

	if thrust:
		_tas_stages = _tas_thrust_stages(initial_position, ticks)
	else:
		_tas_stages = _tas_sweep_stages(initial_position, atk_distance, ticks)

	if scaled:
		var shooting := 0
		for stage in _tas_stages:
			shooting += stage.ticks
		tas_planner.commit(shooting)
		call_deferred("_tas_apply_cooldown")
	else:
		tas_planner.skip()

	_tas_start_stage(0)


# Replaces the cooldown the weapon draws right after shoot() returns; runs deferred, in the same flush.
func _tas_apply_cooldown() -> void :
	tas_planner.apply(_parent)


func _physics_process(delta: float) -> void :
	tas_planner.guard(_parent, delta)
	if _tas_stage < 0:
		return
	_tas_ticks_left -= 1
	if _tas_ticks_left > 0:
		return
	_tas_finish_stage(_tas_stages[_tas_stage])
	_tas_start_stage(_tas_stage + 1)


func _tas_thrust_stages(initial_position: Vector2, ticks: Array) -> Array:
	var stats = _parent.current_stats
	return [
		_tas_new_stage({"position": Vector2(initial_position.x - stats.recoil, initial_position.y)},
				Tween.TRANS_EXPO, ticks[0], TasEvent.STRIKE_START),
		_tas_new_stage({"position": Vector2(initial_position.x + stats.max_range, initial_position.y)},
				Tween.TRANS_EXPO, ticks[1], TasEvent.STRIKE_END),
		_tas_new_stage({"position": initial_position},
				Tween.TRANS_EXPO, ticks[2], TasEvent.DONE),
	]


func _tas_sweep_stages(initial_position: Vector2, atk_distance: float, ticks: Array) -> Array:
	var stats = _parent.current_stats

	var side_range = atk_distance / 2
	var sweep_angle = 0.9 * PI
	var side_a = side_range
	var side_b = - side_range
	var angle_a = sweep_angle
	var angle_b = - sweep_angle
	if not _parent.sprite.flip_v:
		side_a = - side_range
		side_b = side_range
		angle_a = - sweep_angle
		angle_b = sweep_angle

	return [
		_tas_new_stage({"position": Vector2(initial_position.x - stats.recoil, initial_position.y + side_a), "rotation": angle_a},
				Tween.TRANS_EXPO, ticks[0], TasEvent.STRIKE_START),
		_tas_new_stage({"position": Vector2(initial_position.x + _parent.get_sweep_range(atk_distance) * 0.75, initial_position.y), "rotation": 0.0},
				Tween.TRANS_LINEAR, ticks[1], TasEvent.NONE),
		_tas_new_stage({"position": Vector2(initial_position.x - stats.recoil, initial_position.y + side_b), "rotation": angle_b},
				Tween.TRANS_LINEAR, ticks[2], TasEvent.STRIKE_END),
		_tas_new_stage({"position": initial_position, "rotation": 0.0},
				Tween.TRANS_EXPO, ticks[3], TasEvent.DONE),
	]


# Turns a stage's length into whole ticks, carrying the fraction to the next stage. At least 1 tick,
# 2 for the stage that ends the strike.
func _tas_new_stage(targets: Dictionary, trans: int, ticks: float, event: int) -> Dictionary:
	_tas_carry += ticks
	var whole := int(floor(_tas_carry + Timing.EPS))
	var minimum := 2 if event == TasEvent.STRIKE_END else 1
	if whole < minimum:
		whole = minimum
	_tas_carry = max(_tas_carry - whole, -1.0)
	return {"targets": targets, "trans": trans, "ticks": whole, "event": event}


# Starts the stage's move and its tick counter.
func _tas_start_stage(index: int) -> void :
	if index >= _tas_stages.size():
		_tas_stage = -1
		_tas_stages = []
		return

	var stage: Dictionary = _tas_stages[index]
	_tas_stage = index
	_tas_ticks_left = stage.ticks

	# The move is over one tick before the stage ends, as it is unmodded; half a tick off against rounding.
	var sprite = _parent.sprite
	var tween: Tween = _parent.tween
	var move_ticks: int = stage.ticks - 1
	for property in stage.targets:
		var _removed = tween.remove(sprite, property)
		if move_ticks > 0:
			var _added = tween.interpolate_property(sprite, property, sprite.get(property), stage.targets[property],
					(move_ticks - 0.5) / 60.0, stage.trans, Tween.EASE_OUT)
		else:
			sprite.set(property, stage.targets[property])
	if move_ticks > 0:
		var _started = tween.start()


# Puts the sprite at the stage's end position and does what the stage ends with.
func _tas_finish_stage(stage: Dictionary) -> void :
	var sprite = _parent.sprite
	for property in stage.targets:
		var _removed = _parent.tween.remove(sprite, property)
		sprite.set(property, stage.targets[property])

	match stage.event:
		TasEvent.STRIKE_START:
			SoundManager.play(Utils.get_rand_element(_parent.current_stats.shooting_sounds), _parent.current_stats.sound_db_mod, 0.2)
			_parent.enable_hitbox()
		TasEvent.STRIKE_END:
			if not _parent.stats.deal_dmg_on_return:
				_parent.disable_hitbox()
		TasEvent.DONE:
			if _parent.stats.deal_dmg_on_return:
				_parent.disable_hitbox()
			_parent.set_shooting(false)
