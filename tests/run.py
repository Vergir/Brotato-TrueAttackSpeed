"""Runs the mod's checks in hidden games. One line per step here, the cases in tests/out/<set>/.
What each step runs: docs/tests.md.

usage (from the workspace folder):
    python true_attack_speed/tests/run.py core [editor] [exe] [nodlc]      # default: all three
    python true_attack_speed/tests/run.py exhaustive
"""
import pathlib, re, subprocess, sys, time

HERE = pathlib.Path(__file__).parent
ROOT = HERE.parent.parent
DK = [sys.executable, str(ROOT / "tools" / "dk.py")]
SCENARIOS = "true_attack_speed/tests/scenarios/"
CORE_WEAPONS = "weapon_gatling_laser_4,weapon_smg_1,weapon_pistol_1,weapon_hatchet_1,weapon_whip_1,weapon_boomerang_1"
FPS_WEAPONS = "weapon_gatling_laser_4,weapon_smg_1,weapon_hatchet_1,weapon_whip_1,weapon_boomerang_1"
LIMIT_WEAPONS = "weapon_gatling_laser_4,weapon_knife_1,weapon_hatchet_1,weapon_whip_1,weapon_boomerang_1"
MODES = {"editor": [], "exe": ["--exe"], "nodlc": ["--exe", "--no-dlc"]}
# Log lines that are not from the mod. The game's class list names test doubles it does not ship
# (res://tests/partial_doubles/pd_turret.gd and others); the Mod Loader tries to reload them as child classes of
# an extended script and logs three errors per double at every start, four in the editor build. A co-op run
# started from the console has no second input device.
DOUBLES = ["partial_doubles", "load_source_code"]
NOISE = {"editor": DOUBLES + ["script_extension.gd:153", "ui_pause_", "has no config file"],
         "exe": DOUBLES + ["ui_pause_", "has no config file"], "nodlc": DOUBLES + ["ui_pause_", "has no config file"]}


class Run:
    def __init__(self, name):
        self.out = HERE / "out" / name
        self.out.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.bad = 0
        self.cases = 0
        self.t0 = time.time()

    def dk(self, *args):
        return subprocess.run(DK + list(args), cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout

    def launch(self, label, scenario, flags):
        self.dk("stop")
        text = self.dk("run", scenario if "/" in scenario else SCENARIOS + scenario + ".json", "--detach", "--hidden", *flags)
        (self.out / (label + "_launch.txt")).write_text(text, encoding="utf-8")
        if "game is running" not in text:
            print("%s launch | FAILED: %s" % (label, text.strip().splitlines()[-1][:120] if text.strip() else "no output"), flush=True)
            self.bad += 1
            return False
        return True

    def step(self, label, script, *args, gate=True):
        """Runs a test script; its lines with a verdict are the cases."""
        t = time.time()
        path = self.out / (label + ".txt")
        with open(path, "w", encoding="utf-8") as f:   # written as it goes, so a long step can be watched
            subprocess.run([sys.executable, "-u", str(HERE / script)] + list(args), cwd=ROOT, stdout=f, stderr=subprocess.STDOUT)
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        ok = sum(1 for l in lines if l.rstrip().endswith("| ok"))
        off = [l for l in lines if "DIFFERENT" in l or "too few" in l or "no card read" in l or "no turrets found" in l]
        crashed = "Traceback" in text
        bad = len(off) + (1 if crashed else 0) + (1 if gate and ok + len(off) == 0 else 0)
        if gate:
            self.bad += bad
            self.cases += ok + len(off)
        verdict = "ok" if bad == 0 else "%d OFF" % bad
        if not gate:
            verdict = "for information" + (", crashed" if crashed else "")
        print("%s | %d cases | %s | %.0f s" % (label, ok + len(off), verdict, time.time() - t), flush=True)
        for l in off[:4]:
            print("    " + l[:170], flush=True)
        if crashed:
            print("    " + lines[-1][:170], flush=True)

    def errors(self, label, mode):
        text = self.dk("errors")
        (self.out / (label + "_errors.txt")).write_text(text, encoding="utf-8")
        entries = re.split(r"\n(?=(?:SCRIPT )?ERROR:)", text)
        real = [e for e in entries if re.match(r"(SCRIPT )?ERROR:", e) and not any(n in e for n in NOISE[mode])]
        self.bad += len(real)
        print("%s errors | %s" % (label, "none" if not real else "%d: %s" % (len(real), real[0].splitlines()[0][:140])), flush=True)

    def finish(self):
        self.dk("stop")
        verdict = "PASS" if self.bad == 0 else "FAIL (%d off)" % self.bad
        line = "%s: %s, %d cases, %.0f min" % (self.name, verdict, self.cases, (time.time() - self.t0) / 60)
        print(line, flush=True)
        (self.out / "verdict.txt").write_text(line + "\n", encoding="utf-8")
        return 0 if self.bad == 0 else 1


def core(modes):
    run = Run("core")
    for mode in modes:
        if not run.launch(mode, "tas_grid", MODES[mode]):
            continue
        speeds = "-50,0,100,300" if mode == "editor" else "0,300"
        run.step(mode + " cadence", "cadence.py", "--weapons", CORE_WEAPONS, "--as=" + speeds, "--fps", "60v",
                 "--out", str(run.out / (mode + "_cadence.jsonl")))
        if mode != "nodlc":   # Crystal is an item of the first DLC
            run.step(mode + " crystal", "cadence.py", "--weapons", "weapon_hatchet_1,weapon_whip_1", "--as=-50,300",
                     "--fps", "60v", "--items", "item_crystal", "--out", str(run.out / (mode + "_crystal_cadence.jsonl")))
        run.step(mode + " chain", "extra.py", "chain", "--weapons", "weapon_smg_1", "--as", "300", "--secs", "6")
        run.step(mode + " turrets", "turrets.py", "speeds", "variants")
        run.step(mode + " card", "card.py")
        run.errors(mode, mode)
    return run.finish()


def exhaustive():
    run = Run("exhaustive")
    if run.launch("editor", "tas_grid", []):
        run.step("editor every weapon", "cadence.py", "--weapons", "all", "--as=-50,0,300", "--fps", "60v",
                 "--out", str(run.out / "all_cadence.jsonl"))
        run.step("editor frame rates", "cadence.py", "--weapons", FPS_WEAPONS, "--as=-50,100,300", "--fps", "30,144",
                 "--out", str(run.out / "fps_cadence.jsonl"))
        run.step("editor limits", "cadence.py", "--weapons", LIMIT_WEAPONS, "--as=-100,900,3000", "--fps", "60v",
                 "--out", str(run.out / "limits_cadence.jsonl"))
        run.step("editor recalculated stats", "cadence.py", "--weapons", CORE_WEAPONS, "--as=-50,0,300", "--fps", "60v",
                 "--items", "item_padding", "--out", str(run.out / "recalc_cadence.jsonl"))
        run.step("editor chain and co-op", "extra.py", "chain", "coop")
        run.step("editor hits", "hits.py", "--weapons", "weapon_whip_1,weapon_flail_1,weapon_boomerang_1,weapon_knife_1",
                 "--as=0,300", "--secs", "20", gate=False)
        run.errors("editor", "editor")
    if run.launch("unmodded", "scenarios/as_grid.json", []):
        run.step("unmodded chain", "extra.py", "chain", gate=False)
        run.step("unmodded turrets", "turrets.py", "speeds")
        run.step("unmodded hits", "hits.py", "--weapons", "weapon_whip_1,weapon_flail_1,weapon_boomerang_1,weapon_knife_1",
                 "--as=0,300", "--secs", "20", gate=False)
    if run.launch("tooltips", "tas_shop_it", []):
        run.step("editor card with Improved Tooltips", "card.py")
        run.errors("tooltips", "editor")
    if run.launch("exe", "tas_grid", MODES["exe"]):
        run.step("exe more weapons", "cadence.py", "--weapons",
                 "weapon_knife_1,weapon_flail_1,weapon_carbon_bow_1,weapon_sword_2,weapon_revolver_1,weapon_chainsaw_3,weapon_harpoon_gun_2",
                 "--as=-50,100", "--fps", "60v", "--out", str(run.out / "exe_cadence.jsonl"))
        run.step("exe frame rates", "cadence.py", "--weapons", "weapon_gatling_laser_4,weapon_whip_1,weapon_boomerang_1",
                 "--as=300", "--fps", "30,144", "--out", str(run.out / "exe_fps_cadence.jsonl"))
        run.step("exe co-op", "extra.py", "coop", "--weapons", "weapon_smg_1", "--as", "300")
        run.errors("exe", "exe")
    if run.launch("nodlc tooltips", "tas_shop_it", MODES["nodlc"]):
        run.step("nodlc card with Improved Tooltips", "card.py")
        run.step("nodlc more weapons", "cadence.py", "--weapons", "weapon_knife_1,weapon_sword_2,weapon_revolver_1",
                 "--as=-50,100", "--fps", "60v", "--out", str(run.out / "nodlc_cadence.jsonl"))
        run.errors("nodlc tooltips", "nodlc")
    return run.finish()


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "core"
    if which == "core":
        modes = [m for m in sys.argv[2:] if m in MODES] or list(MODES)
        return core(modes)
    if which == "exhaustive":
        return exhaustive()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
