"""The rule of vergir-TrueAttackSpeed in Python, and the comparison with the unmodded game at 60 FPS.
See docs/tests.md.

usage: python true_attack_speed/tests/tas_rule.py   -> tests/out/rule_table.txt and a short table on stdout
"""
import os, math, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent / "research" / "attack_speed"))
import model  # noqa: E402

HERE = pathlib.Path(__file__).parent
# TAS_GAME_SRC: another decompiled copy of the game to read the weapons from.
WEAPONS = pathlib.Path(os.environ.get("TAS_GAME_SRC", HERE.parent.parent / "game_src")) / "weapons"
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV"}


def read_stats(path):
    d = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\w+) = (.+)$", line)
        if m:
            d[m.group(1)] = m.group(2).strip()
    return d


def load_weapons():
    """Every weapon tier of the game: found through its data file (my_id), stats from the file that one names."""
    out = []
    game = WEAPONS.parent
    roots = [WEAPONS] + sorted((game / "dlcs").glob("*/weapons"))   # DLC 1 keeps its weapons apart
    found = []
    for root in roots:
        for group in ("melee", "ranged"):
            for data in (root / group).rglob("*data*.tres"):
                text = data.read_text(encoding="utf-8")
                my_id = re.search(r'^my_id = "(weapon_[^"]+)"', text, re.M)
                ref = re.search(r'^stats = ExtResource\( (\d+) \)', text, re.M)
                if not my_id or not ref:
                    continue
                path = re.search(r'\[ext_resource path="res://([^"]+)"[^\]]*id=%s\]' % ref.group(1), text)
                if path:
                    found.append((my_id.group(1), group, data, game / path.group(1)))
    for my_id, group, data, stats in sorted(found):
        if True:
            in_tier_folder = data.parent.name.isdigit()
            tier = data.parent.name if in_tier_folder else "1"
            folder = data.parent.parent.name if in_tier_folder else data.parent.name
            d = read_stats(stats)
            if "cooldown" not in d:
                continue
            w = {
                "name": folder, "id": my_id, "tier": int(tier), "group": group,
                "cooldown": int(d["cooldown"]), "recoil": float(d.get("recoil_duration", 0.1)),
                "max_range": int(d.get("max_range", 150)),
                "anim_speed": float(d.get("animation_speed", 1.0)),
                "attack_duration": float(d.get("attack_duration", 0.0)),
                "alternate": d.get("alternate_attack_type", "false") == "true",
                "reload_every": int(d.get("additional_cooldown_every_x_shots", -1)),
                "reload_mult": float(d.get("additional_cooldown_multiplier", -1.0)),
                "projectile_speed": float(d.get("projectile_speed", 0)),
            }
            if w["attack_duration"] > 0:
                w["kind"] = "animated"       # Whip, Flail: the attack is an animation on physics ticks
            elif w["name"] == "boomerang":
                w["kind"] = "boomerang"      # the shooting state lasts until the projectile is back
            elif group == "ranged":
                w["kind"] = "ranged"
            else:
                w["kind"] = "sweep" if d.get("attack_type", "0") == "1" else "thrust"
            out.append(w)
    return out


def big_reload(w, atk=0.0):
    """Ticks of the long reload some weapons have every few shots (weapon_service.gd:236-247: the base
    cooldown times the multiplier is rounded to whole ticks before Attack Speed is applied)."""
    cd = model.cooldown_ticks(w["cooldown"], atk)
    return max(cd, model.cooldown_ticks(int(round(w["cooldown"] * w["reload_mult"])), atk))


def mean_cooldown(w, cd, ceil, atk=0.0):
    """Mean ticks the cooldown part takes, one weapon. ceil=True: the game counts whole ticks (ceil of the draw)."""
    lo, hi = model.jitter_range(cd, 1)
    m = model.mean_ceil_uniform(lo, hi) if ceil else (lo + hi) / 2
    if w["reload_every"] > 0:
        x = w["reload_every"]
        m = ((x - 1) * m + big_reload(w, atk)) / x
    return m


def tween_cost(d60, limiter):
    """Frames one tween occupies at 60 FPS in the game as shipped (d60 = duration in frames)."""
    return model.tween_frames(d60 / 60.0, 60, limiter)


def boomerang_flight_ticks(reach, speed, start_distance=25.0):
    """Ticks from a Boomerang's throw to its catch: boomerang_projectile.gd stepped tick by tick, player
    standing still (the same estimate as timing.gd of vergir-TrueAttackSpeed; measured: 71 for Boomerang I
    with one weapon, where the start distance is 11 px)."""
    dt, ticks, t, x = 1 / 60.0, 0, 0.0, 0.0
    out = reach / speed * 1.6
    while True:
        ticks += 1; t += dt
        u = min(1.0, t / out)
        x = reach * (1 - (1 - u) ** 2)
        if u >= 1.0:
            break
    t = 0.0
    while True:
        ticks += 1; t += dt
        x += speed * 0.25 * dt
        if t >= 0.15:
            break
    t = 0.0
    while ticks < 240:
        ticks += 1; t += dt
        left = x + start_distance
        if left <= 30.0:
            break
        x -= min(min(speed * 1.2, speed * (0.25 + 2.0 * t)) * dt, left)
    return ticks


def special_shooting_ticks(w):
    """Shooting ticks of the weapons whose shooting state does not depend on Attack Speed, unmodded."""
    if w["kind"] == "animated":
        return math.ceil(w["attack_duration"] * 60 - 1e-6) - 1
    return boomerang_flight_ticks(w["max_range"], w["projectile_speed"])


def cycles(w, atk, limiter=False):
    """Mean ticks per attack under each rule -> dict. atk = Attack Speed / 100."""
    cd = model.cooldown_ticks(w["cooldown"], atk)
    if w["kind"] in ("animated", "boomerang"):
        total = special_shooting_ticks(w) + mean_cooldown(w, cd, True, atk)
        return {"vanilla": total, "fix": total, "P": total, "Pcap": total, "D": total}
    kinds = ["thrust", "sweep"] if w["alternate"] else [w["kind"]]
    res = {"vanilla": 0.0, "fix": 0.0, "P": 0.0, "Pcap": 0.0, "D": 0.0}
    for kind in kinds:
        ph = [d * 60 for d in model.phases(kind, atk, w["recoil"], w["max_range"], w["anim_speed"])]
        ph0 = [d * 60 for d in model.phases(kind, 0.0, w["recoil"], w["max_range"], w["anim_speed"])]
        nominal = sum(ph)
        s_v = sum(tween_cost(d, limiter) for d in ph) - 1
        over0 = sum(tween_cost(d, limiter) for d in ph0) - 1 - sum(ph0)       # extra ticks at +0% Attack Speed
        # P, Pcap, D: rules considered before (docs/tests.md). The mod's rule is exact().
        s_p = s_v if atk <= 0 else nominal + over0 / (1 + atk)
        s_pcap = min(s_v, s_p)
        s_d = max(nominal, sum(tween_cost(d, limiter) if d >= 1 else 3 * d for d in ph) - 1)  # D: only phases under one frame
        s_d = min(s_v, s_d)
        cdc = mean_cooldown(w, cd, True, atk)
        res["vanilla"] += (s_v + cdc) / len(kinds)
        res["P"] += (s_p + cdc) / len(kinds)
        res["Pcap"] += (s_pcap + cdc) / len(kinds)
        res["D"] += (s_d + cdc) / len(kinds)
        res["fix"] += (nominal + mean_cooldown(w, cd, False, atk)) / len(kinds)
    return res


LEAST = {"ranged": 1, "thrust": 5, "sweep": 6, "animated": 5, "boomerang": 2}


def exact(w, atk):
    """Mean ticks per attack under the mod's rule (docs/tests.md). atk = Attack Speed / 100."""
    base = cycles(w, 0.0)["vanilla"]
    if atk == 0:
        return base
    kinds = ["thrust", "sweep"] if w["alternate"] and w["kind"] in ("thrust", "sweep") else [w["kind"]]
    least = sum(LEAST[k] for k in kinds) / len(kinds)
    return max(least, base / (1 + atk) if atk > 0 else base * (1 - atk))


def special(w):
    if w["attack_duration"] > 0:
        return "animation-driven: already timed on ticks, no change"
    if w["kind"] == "boomerang":
        return "cycle ends when the projectile returns, not modelled"
    return ""


def main():
    weapons = load_weapons()
    lines = ["weapon | tier | kind | cooldown | recoil s | today ticks (lo-hi) | nominal ticks | today att/s | fix att/s | fix gain %"]
    rows = []
    for w in weapons:
        if special(w):
            lines.append("%s | %d | %s | %s" % (w["name"], w["tier"], w["kind"], special(w)))
            continue
        a = cycles(w, 0.0, False)
        b = cycles(w, 0.0, True)
        lo, hi = sorted((a["vanilla"], b["vanilla"]))
        g_lo, g_hi = 100 * (lo / a["fix"] - 1), 100 * (hi / a["fix"] - 1)
        rows.append((w, lo, hi, a["fix"], g_lo, g_hi))
        lines.append("%s | %d | %s | %d | %.3f | %.1f-%.1f | %.1f | %.2f-%.2f | %.2f | %.0f-%.0f" % (
            w["name"], w["tier"], w["kind"], w["cooldown"], w["recoil"], lo, hi, a["fix"], 60 / hi, 60 / lo, 60 / a["fix"], g_lo, g_hi))
    lines.append("")
    lines.append("Rules at several Attack Speed values (attacks per second, one weapon, 60 FPS, vsync frame counts)")
    lines.append("weapon | AS % | today | D (dead zone only) | P (shooting state proportional) | X (whole cycle proportional, the mod) | fix")
    picks = [("gatling_laser", 4), ("smg", 1), ("smg", 4), ("minigun", 4), ("pistol", 1), ("shredder", 1), ("knife", 1), ("fist", 1), ("hatchet", 1), ("spear", 1),
             ("whip", 1), ("flail", 1), ("boomerang", 1)]   # for these three D, P and fix are the game as shipped
    for name, tier in picks:
        for w in weapons:
            if w["name"] == name and w["tier"] == tier:
                for speed in (-100, -50, 0, 25, 50, 100, 150, 200, 300):
                    c = cycles(w, speed / 100.0)
                    lines.append("%s %s | %+d | %.2f | %.2f | %.2f | %.2f | %.2f" % (name, ROMAN[tier], speed, 60 / c["vanilla"], 60 / c["D"], 60 / c["P"], 60 / exact(w, speed / 100.0), 60 / c["fix"]))
    (HERE / "out" / "rule_table.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    t1 = sorted((r for r in rows if r[0]["tier"] == 1), key=lambda r: -r[5])
    print("tier 1 weapons at +0%% Attack Speed: %d (plus %d special)" % (len(t1), sum(1 for w in weapons if w["tier"] == 1 and special(w))))
    for w, lo, hi, fix, g_lo, g_hi in t1:
        print("%-16s %-6s cd %3d rec %.2f  today %5.1f-%5.1f ticks  nominal %5.1f  gain %+3.0f..%+3.0f%%" % (w["name"], w["kind"], w["cooldown"], w["recoil"], lo, hi, fix, g_lo, g_hi))
    for tier in (1, 2, 3, 4):
        g = [r[5] for r in rows if r[0]["tier"] == tier]
        gl = [r[4] for r in rows if r[0]["tier"] == tier]
        print("tier %d: %d weapons, fix gain median %+.0f%% (range %+.0f%% to %+.0f%%)" % (tier, len(g), sorted(g)[len(g) // 2], min(gl), max(g)))


if __name__ == "__main__":
    main()
