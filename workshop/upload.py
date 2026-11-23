"""Creates or updates the mod's Steam Workshop item through the game's own Steam interface.
How it works and what it needs: docs/workshop.md.

usage (from the workspace folder, with a hidden `dk run ... --exe` game running):
    python true_attack_speed/workshop/upload.py --new [--gallery]            # new item, private
    python true_attack_speed/workshop/upload.py --id ID [--note TEXT] [--no-text] [--no-zip] [--gallery]
    python true_attack_speed/workshop/upload.py --id ID --visibility public   # only changes who can see it
"""
import argparse, json, pathlib, shutil, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "research" / "attack_speed"))
import dkc

MOD = HERE.parent / "mods-unpacked" / "vergir-TrueAttackSpeed"
TITLE = "TrueAttackSpeed"
TAGS = ["Reworks"]
GALLERY = ["double.png", "curve.png", "fps.png"]
VISIBILITY = {"public": 0, "friends": 1, "private": 2, "unlisted": 3}
OK = 1   # Steam's k_EResultOK

INSTALL = '''var old = dk.get_node_or_null("TasUpload")
if old != null:
	old.free()
var f = File.new()
f.open(%s, File.READ)
var script = GDScript.new()
script.source_code = f.get_as_text()
f.close()
var err = script.reload()
var node = Node.new()
node.name = "TasUpload"
node.set_script(script)
dk.add_child(node)
return [err, Steam.loggedOn(), Steam.getAppID()]'''


def gd(value):
    return json.dumps(str(value).replace("\\", "/") if isinstance(value, pathlib.Path) else value)


def wait(field, seconds):
    end = time.time() + seconds
    while time.time() < end:
        result = dkc.ev('dk.get_node("TasUpload").%s' % field)
        if result is not None:
            return result
        time.sleep(1.0)
    sys.exit("no answer from Steam for '%s' within %d s" % (field, seconds))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--id", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--visibility", choices=sorted(VISIBILITY), default="")
    ap.add_argument("--gallery", action="store_true", help="also add the three graphs (adds, does not replace)")
    ap.add_argument("--no-text", action="store_true", help="leave title, description and tags as they are")
    ap.add_argument("--no-zip", action="store_true", help="leave the mod's files and the thumbnail as they are")
    args = ap.parse_args()
    if args.new == bool(args.id):
        sys.exit("give either --new or --id ID")

    err, logged_on, app_id = dkc.ex(INSTALL % gd(HERE / "upload_node.gd"))
    if err != 0 or not logged_on:
        sys.exit("cannot start: script error %s, logged on to Steam: %s" % (err, logged_on))

    item = args.id
    if args.new:
        dkc.ex("Steam.createItem(Steam.getAppID(), 0)\nreturn 1")
        result, item, accept = wait("created", 60)
        print("created: result %s, id %s, legal agreement still to accept: %s" % (result, item, accept))
        if result != OK:
            sys.exit("Steam did not create the item")

    only_visibility = bool(args.visibility) and not args.new and not args.note and not args.gallery
    lines = ["var h = Steam.startItemUpdate(Steam.getAppID(), int(%s))" % gd(item), "var done = []"]
    if not only_visibility and not args.no_text:
        lines += ["var f = File.new()", "f.open(%s, File.READ)" % gd(HERE.parent / "docs" / "workshop_description.txt"),
                  "var text = f.get_as_text()", "f.close()",
                  "done.append(Steam.setItemTitle(h, %s))" % gd(TITLE),
                  "done.append(Steam.setItemDescription(h, text))",
                  "done.append(Steam.setItemTags(h, %s, false))" % json.dumps(TAGS)]
    if not only_visibility and not args.no_zip:
        version = json.loads((MOD / "manifest.json").read_text(encoding="utf-8"))["version_number"]
        zip_file = ROOT / "build" / ("vergir-TrueAttackSpeed-%s.zip" % version)
        content = ROOT / "build" / "workshop_upload"
        shutil.rmtree(content, ignore_errors=True)
        content.mkdir(parents=True)
        shutil.copy2(zip_file, content / zip_file.name)
        lines += ["done.append(Steam.setItemContent(h, %s))" % gd(content),
                  "done.append(Steam.setItemPreview(h, %s))" % gd(HERE / "out" / "thumbnail.png")]
    if args.gallery:
        lines += ["done.append(Steam.addItemPreviewFile(h, %s, 0))" % gd(HERE / "out" / name) for name in GALLERY]
    if args.visibility or args.new:
        lines.append("done.append(Steam.setItemVisibility(h, %d))" % VISIBILITY[args.visibility or "private"])
    lines += ['dk.get_node("TasUpload").updated = null', "Steam.submitItemUpdate(h, %s)" % gd(args.note), "return done"]
    accepted = dkc.ex("\n".join(lines))
    print("fields accepted:", accepted)
    result, accept, _ = wait("updated", 300)
    print("updated: result %s, legal agreement still to accept: %s" % (result, accept))
    print("https://steamcommunity.com/sharedfiles/filedetails/?id=%s" % item)
    if result != OK:
        sys.exit("Steam did not accept the update")


if __name__ == "__main__":
    main()
