extends "res://weapons/shooting_behaviors/animated_hitbox_shooting_behavior.gd"

# Whip and Flail: the whole cycle (animation plus cooldown) is planned. When the cycle is shorter than
# the animation, the animation is stepped by hand. See docs/architecture.md.

const Timing = preload("res://mods-unpacked/vergir-TrueAttackSpeed/timing.gd")
const CyclePlanner = preload("res://mods-unpacked/vergir-TrueAttackSpeed/cycle_planner.gd")

enum TasEvent { OPEN, CLOSE, DONE }

var tas_planner := CyclePlanner.new()
# True while this script steps the animation; the animation's own calls are ignored then.
var _tas_driven := false
# Each stage: [ticks, animation position at its end, TasEvent]
var _tas_stages := []
var _tas_stage := 0
var _tas_tick := 0
var _tas_from := 0.0
var _tas_times_of := ""
var _tas_times := []


# Plays the animation as it is while it fits into the cycle; otherwise steps it by hand.
func shoot(distance: float) -> void :
	_tas_driven = false
	_animation_player.playback_process_mode = AnimationPlayer.ANIMATION_PROCESS_PHYSICS

	var atk_spd := Timing.attack_speed(_parent.current_stats, _parent.player_index)
	var animation: Animation = _animation_player.get_animation(animation_name)
	if atk_spd == 0.0 or animation == null:
		tas_planner.skip()
		.shoot(distance)
		return

	var base_shooting := Timing.animation_ticks(animation.length)
	var cycle := tas_planner.plan(_parent, base_shooting, atk_spd)
	var shooting := int(base_shooting)
	var times := _tas_hitbox_times(animation)
	if shooting > cycle - 1 and not times.empty():
		shooting = int(max(Timing.ANIMATED_MIN_SHOOTING, cycle - 1))
		_tas_start_driven(shooting, times, animation.length)
	else:
		.shoot(distance)

	tas_planner.commit(shooting)
	call_deferred("_tas_apply_cooldown")


# See the function of the same name in ranged_weapon_shooting_behavior.gd.
func _tas_apply_cooldown() -> void :
	tas_planner.apply(_parent)


func open_hitbox() -> void :
	if not _tas_driven:
		.open_hitbox()


func close_hitbox() -> void :
	if not _tas_driven:
		.close_hitbox()


func _on_animation_finished(anim_name: String) -> void :
	if not _tas_driven:
		._on_animation_finished(anim_name)


func _physics_process(delta: float) -> void :
	tas_planner.guard(_parent, delta)
	if not _tas_driven:
		return

	var stage: Array = _tas_stages[_tas_stage]
	_tas_tick += 1
	_animation_player.seek(lerp(_tas_from, stage[1], float(_tas_tick) / stage[0]), true)
	if _tas_tick < stage[0]:
		return

	match stage[2]:
		TasEvent.OPEN:
			.open_hitbox()
		TasEvent.CLOSE:
			.close_hitbox()
		TasEvent.DONE:
			_tas_driven = false
			_parent.disable_hitbox()
			_parent.set_shooting(false)
			return
	_tas_from = stage[1]
	_tas_stage += 1
	_tas_tick = 0


# Splits `shooting` ticks into before, open and after the hitbox, and takes over the animation.
func _tas_start_driven(shooting: int, times: Array, length: float) -> void :
	# The hitbox stays open as long as unmodded if there is room; the rest is shared in proportion.
	var open_ticks := int(clamp(round((times[1] - times[0]) * 60.0), 2.0, shooting - 2.0))
	var rest := shooting - open_ticks
	var before_ticks := int(clamp(round(rest * times[0] / (times[0] + length - times[1])), 1.0, rest - 1.0))
	var after_ticks := rest - before_ticks
	_tas_stages = [
		[before_ticks, times[0], TasEvent.OPEN],
		[open_ticks, times[1], TasEvent.CLOSE],
		[after_ticks, length, TasEvent.DONE],
	]
	_tas_stage = 0
	_tas_tick = 0
	_tas_from = 0.0

	_parent._hitbox.player_attack_id = _get_next_attack_id()
	_parent.set_shooting(true)

	_tas_driven = true
	_animation_player.playback_process_mode = AnimationPlayer.ANIMATION_PROCESS_MANUAL
	_animation_player.stop()
	_animation_player.play(animation_name)
	_animation_player.seek(0.0, true)


# [time the animation opens the hitbox, time it closes it], or [] if it does not call both.
func _tas_hitbox_times(animation: Animation) -> Array:
	if _tas_times_of == animation_name:
		return _tas_times

	var open_time := -1.0
	var close_time := -1.0
	for track in animation.get_track_count():
		if animation.track_get_type(track) != Animation.TYPE_METHOD:
			continue
		for key in animation.track_get_key_count(track):
			var method := animation.method_track_get_name(track, key)
			if method == "open_hitbox" and open_time < 0.0:
				open_time = animation.track_get_key_time(track, key)
			elif method == "close_hitbox" and close_time < 0.0:
				close_time = animation.track_get_key_time(track, key)

	_tas_times_of = animation_name
	_tas_times = []
	if open_time > 0.0 and close_time > open_time and close_time < animation.length:
		_tas_times = [open_time, close_time]
	return _tas_times
