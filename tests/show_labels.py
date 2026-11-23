"""One line per weapon from the outputs of label_probe.gd and breakpoint_text_probe.gd.
usage: python show_labels.py LABEL.json [BREAKPOINTS.json]"""
import json, sys

labels = json.load(open(sys.argv[1], encoding="utf-8"))
labels = labels.get("result", labels) if isinstance(labels, dict) else labels
texts = {}
if len(sys.argv) > 2:
    texts = json.load(open(sys.argv[2], encoding="utf-8"))
    texts = texts.get("result", texts)
for r in labels:
    it = r.get("it_cycle_ticks")
    bp = texts.get(r["id"])
    print("%-16s AS %+d | %-18s | mod %.3f | IT %s | %s" % (
        r["id"][7:], r["attack_speed"], r["card_line"].strip(), r["mod_cycle_ticks"],
        None if it is None else [round(x, 3) for x in it], bp["SHOW_DPS"] if isinstance(bp, dict) else ""))
