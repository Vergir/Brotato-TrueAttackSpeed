extends Node
# Turret cadence recorder for turrets.py. Read-only, except that it keeps enemies alive so that the
# turrets always have a target. Per turret and cycle: ticks from one start of the shoot animation to
# the next, ticks the animation held the turret, ticks waited after it, the cooldown the turret had
# been given, and the mod's log entry for that cycle (null without the mod or at structure attack
# speed 0).

var tick := 0
var turrets := []
var st := {}
var keep_alive := true


func start() -> void:
	var main = get_tree().current_scene
	turrets = []
	st = {}
	for s in main._entity_spawner.structures:
		if is_instance_valid(s) and s is Turret:
			turrets.append(s)
			st[s.get_instance_id()] = {"shooting": s._is_shooting, "begin": -1, "end": -1, "drawn": 0.0,
				"entry": null, "seen": _cycles(s), "cycles": [], "shots0": s._nb_shots_taken}


func _cycles(t) -> int:
	return t.tas_cycles if "tas_cycles" in t else 0


func _physics_process(_delta: float) -> void:
	tick += 1
	var main = get_tree().current_scene
	if main == null or not ("_entity_spawner" in main):
		return
	if keep_alive:
		for e in main._entity_spawner.enemies:
			if is_instance_valid(e) and not e.dead:
				e.current_stats.health = 100000
	for t in turrets:
		if not is_instance_valid(t):
			continue
		var s = st[t.get_instance_id()]
		if t._is_shooting == s.shooting:
			continue
		s.shooting = t._is_shooting
		if s.shooting:
			if s.entry == null and _cycles(t) != s.seen:
				# A shot that was called off (no target left when the animation reached the shot): the turret
				# stopped "shooting" before the animation ended, and the mod logged the cycle only then.
				s.seen = _cycles(t)
				s.entry = t.tas_log.back().duplicate()
			if s.begin >= 0 and s.end >= 0:
				s.cycles.append([tick - s.begin, s.end - s.begin, tick - s.end, s.drawn, s.entry])
			s.begin = tick
			s.end = -1
		elif s.begin >= 0:
			s.end = tick
			s.drawn = t._cooldown
			s.entry = null
			if _cycles(t) != s.seen:
				s.seen = _cycles(t)
				s.entry = t.tas_log.back().duplicate()


func report() -> Array:
	var out := []
	for t in turrets:
		if not is_instance_valid(t):
			continue
		var s = st[t.get_instance_id()]
		var script: Script = t.get_script()
		out.append({"cycles": s.cycles, "cooldown": t.stats.cooldown, "speed": t._shooting_speed,
			"length": t._animation_player.get_animation("shoot").length,
			"scene": t.filename.get_file(), "base_type": script.get_instance_base_type() if script != null else "",
			"shots": t._nb_shots_taken - s.shots0, "mod_cycles": _cycles(t)})
	return out
