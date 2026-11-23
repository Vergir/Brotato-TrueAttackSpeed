"""Images for the Steam Workshop page: three graphs (1920x1080) and the thumbnail (1024x1024).

    python true_attack_speed/workshop/make_images.py [name ...]      names: double, curve, fps, thumbnail

Rates come from the rule model in tests/tas_rule.py (the same numbers as the README table). Each image is an
HTML page rendered by headless Edge. Uses the game's font and icons from game_src/ and out/_wave.png (one
screenshot of a wave) as the blurred background; out/_potato_3.png is a zoomed shot for the thumbnail."""
import base64, pathlib, subprocess, sys

from PIL import Image, ImageEnhance, ImageFilter

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parent / "tests"))
sys.path.insert(0, str(ROOT / "research" / "attack_speed"))
import tas_rule

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
FONT = ROOT / "game_src" / "resources" / "fonts" / "raw" / "Anybody-Medium.ttf"
GREY, ACCENT = "#8c8c8c", "#e03828"          # unmodded, with the mod (the red of the Brotato logo)
INK, TAN, MUTED, GRID, DARK = "#ffffff", "#dccfa8", "#a09a8c", "rgba(255,255,255,0.16)", "#0d0d0d"
W = {w["id"]: w for w in tas_rule.load_weapons()}


def unmodded(wid, atk):
    return 60 / tas_rule.cycles(W[wid], atk / 100.0)["vanilla"]


def modded(wid, atk):
    return 60 / tas_rule.exact(W[wid], atk / 100.0)


def uri(path):
    kind = "font/ttf" if str(path).endswith(".ttf") else "image/jpeg" if str(path).endswith(".jpg") else "image/png"
    return "data:%s;base64,%s" % (kind, base64.b64encode(pathlib.Path(path).read_bytes()).decode())


def icon(rel):
    return uri(ROOT / "game_src" / rel)


def background(size, focus):
    """The wave screenshot, blurred and dimmed, with the player (640, 350 in the shot) at `focus`."""
    img = Image.open(OUT / "_wave.png").convert("RGB")
    w, h = size
    scale = 1.9 * w / 1920 if w > h else 1.6
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", size, (10, 10, 10))
    canvas.paste(img, (round(focus[0] - 640 * scale), round(focus[1] - 350 * scale)))
    canvas = ImageEnhance.Brightness(canvas.filter(ImageFilter.GaussianBlur(7))).enhance(0.8)
    path = OUT / ("_bg_%dx%d.jpg" % size)
    canvas.save(path, quality=88)
    return uri(path)


def text(x, y, s, size, fill=INK, anchor="start", font="body", weight=400, extra=""):
    family = "Anybody" if font == "game" else "Segoe UI"
    return ('<text x="%s" y="%s" font-family="%s" font-size="%s" font-weight="%s" fill="%s" text-anchor="%s" %s>%s</text>'
            % (x, y, family, size, weight, fill, anchor, extra, s))


def bar(x, y, width, height, fill):
    """Bar from the baseline x to the right, square at the baseline, 4 px rounded at the data end."""
    r = min(4, width)
    return ('<path d="M%s %s h%s a%s %s 0 0 1 %s %s v%s a%s %s 0 0 1 -%s %s h-%s z" fill="%s"/>'
            % (x, y, width - r, r, r, r, r, height - 2 * r, r, r, r, r, width - r, fill))


def legend(y, first, second):
    return ('<rect x="100" y="%d" width="30" height="22" rx="4" fill="%s"/>' % (y - 20, GREY) + text(144, y, first, 30, TAN)
            + '<rect x="%d" y="%d" width="30" height="22" rx="4" fill="%s"/>' % (200 + len(first) * 16, y - 20, ACCENT)
            + text(244 + len(first) * 16, y, second, 30, TAN))


def header(title, subtitle):
    return text(98, 168, title, 84, weight=700) + text(100, 232, subtitle, 34, TAN)


def page(size, body, shade, focus, bg=None):
    w, h = size
    return """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "Anybody"; src: url(%s); }
html, body { margin: 0; width: %dpx; height: %dpx; overflow: hidden; background: #0a0a0a; }
.bg, .shade, svg { position: absolute; left: 0; top: 0; width: %dpx; height: %dpx; }
.bg { background: url(%s); }
.shade { background: %s; }
</style></head><body><div class="bg"></div><div class="shade"></div>
<svg width="%d" height="%d" viewBox="0 0 %d %d" xmlns="http://www.w3.org/2000/svg">%s</svg></body></html>""" % (
        uri(FONT), w, h, w, h, bg or background(size, focus), shade, w, h, w, h, body)


def render(name, size, body, shade="linear-gradient(90deg, rgba(8,8,8,0.97) 0%, rgba(8,8,8,0.9) 55%, rgba(8,8,8,0.62) 100%)",
           focus=(1600, 560), bg=None):
    html = OUT / ("_%s.html" % name)
    html.write_text(page(size, body, shade, focus, bg), encoding="utf-8")
    png = OUT / (name + ".png")
    raw = OUT / ("_%s_raw.png" % name)
    # The window is larger than the page: headless Edge's viewport is smaller than the window it is given.
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=%d,%d" % (size[0] + 200, size[1] + 200), "--screenshot=" + str(raw), html.as_uri()],
                   check=True, capture_output=True, timeout=120)
    Image.open(raw).convert("RGB").crop((0, 0, size[0], size[1])).save(png, optimize=True)
    raw.unlink()
    print("%s: %s, %d KB" % (name, "%dx%d" % size, png.stat().st_size // 1024))


# ---------------------------------------------------------------- 1. +100% is twice the attacks

DOUBLE = [("Gatling Laser IV", "weapon_gatling_laser_4", "weapons/ranged/gatling_laser/gatling_laser_icon.png"),
          ("SMG I", "weapon_smg_1", "weapons/ranged/smg/smg_icon.png"),
          ("Pistol I", "weapon_pistol_1", "weapons/ranged/pistol/pistol_icon.png"),
          ("Whip I", "weapon_whip_1", "weapons/melee/whip/whip_icon.png"),
          ("Boomerang I", "weapon_boomerang_1", "weapons/ranged/boomerang/boomerang_icon.png")]


def double():
    x0, unit, top, row, height = 500, 620, 372, 128, 42
    s = header("+100% Attack Speed = twice the attacks", "Attack rate at +100% Attack Speed, compared with the same weapon at +0%")
    s += legend(306, "Unmodded, 60 FPS", "With True Attack Speed")
    bottom = top + row * len(DOUBLE) - 24
    for mult, label in ((0, ""), (1, "×1  (the rate at +0%)"), (2, "×2")):
        x = x0 + unit * mult
        s += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="%d"/>' % (
            x, top - 16, x, bottom, ACCENT if mult == 2 else GRID, 3 if mult == 2 else 2)
        s += text(x, bottom + 42, label, 28, TAN if mult == 2 else MUTED, "middle")
    for i, (name, wid, art) in enumerate(DOUBLE):
        y = top + row * i
        base = unmodded(wid, 0)
        s += '<image href="%s" x="96" y="%d" width="84" height="84"/>' % (icon(art), y + 2)
        s += text(196, y + 40, name, 32, weight=700) + text(196, y + 76, "%.2f /s at +0%%" % base, 24, MUTED)
        for k, (rate, fill) in enumerate(((unmodded(wid, 100), GREY), (modded(wid, 100), ACCENT))):
            by = y + k * (height + 4)
            width = unit * rate / base
            s += bar(x0, by, width, height, fill)
            ink = INK if k else DARK
            s += text(x0 + width - 150, by + 31, "×%.2f" % (rate / base), 32, ink, "end", weight=700)
            s += text(x0 + width - 18, by + 30, "%.2f /s" % rate, 25, ink, "end")
    render("double", (1920, 1080), s)


# ---------------------------------------------------------------- 2. every point counts (SMG I, 0 to +300%)

def curve():
    wid = "weapon_smg_1"
    left, right, top, bottom, ymax = 190, 1480, 380, 950, 20.0
    px = lambda a: left + (right - left) * a / 300.0
    py = lambda r: bottom - (bottom - top) * r / ymax
    s = header("Every point of Attack Speed counts", "SMG I: attacks per second from +0% to +300% Attack Speed")
    s += legend(306, "Unmodded, 60 FPS", "With True Attack Speed")
    for r in (0, 5, 10, 15, 20):
        s += '<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="%s" stroke-width="2"/>' % (left, py(r), right, py(r), GRID)
        s += text(left - 18, py(r) + 10, "%d /s" % r if r else "0", 28, MUTED, "end")
    for a in (0, 100, 200, 300):
        s += text(px(a), bottom + 48, "+%d%%" % a, 28, MUTED, "middle")
    s += text((left + right) / 2, bottom + 96, "Attack Speed", 28, MUTED, "middle")
    # The unmodded rate moves in steps: draw it as steps, not as a smoothed line.
    pts, prev = [], None
    for a in range(0, 301):
        r = unmodded(wid, a)
        if prev is not None and abs(r - prev) > 1e-9:
            pts.append((px(a), py(prev)))
        pts.append((px(a), py(r)))
        prev = r
    s += '<polyline points="%s" fill="none" stroke="%s" stroke-width="5" stroke-linejoin="round"/>' % (
        " ".join("%.1f,%.1f" % p for p in pts), GREY)
    s += '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="6" stroke-linecap="round"/>' % (
        px(0), py(modded(wid, 0)), px(300), py(modded(wid, 300)), ACCENT)
    for a, mult in ((0, "×1"), (100, "×2"), (200, "×3"), (300, "×4")):
        r = modded(wid, a)
        s += '<circle cx="%.1f" cy="%.1f" r="11" fill="%s" stroke="#0a0a0a" stroke-width="3"/>' % (px(a), py(r), ACCENT)
        if a:
            s += text(px(a) - 16, py(r) - 30, mult, 50, INK, "end", weight=700)
            if a < 300:
                s += text(px(a) - 16, py(r) - 84, "%.1f /s" % r, 28, TAN, "end")
    s += text(right + 30, py(modded(wid, 300)) + 12, "%.1f /s" % modded(wid, 300), 40, INK, weight=700)
    s += text(right + 30, py(modded(wid, 300)) + 50, "with the mod", 28, TAN)
    s += text(right + 30, py(unmodded(wid, 300)) + 12, "%.1f /s" % unmodded(wid, 300), 40, INK)
    s += text(right + 30, py(unmodded(wid, 300)) + 50, "unmodded", 28, TAN)
    s += text(px(156), py(unmodded(wid, 126)) + 46, "unmodded: nothing gained from +51% to +200%", 28, MUTED, "middle")
    render("curve", (1920, 1080), s)


# ---------------------------------------------------------------- 3. the frame rate does not matter

# Gatling Laser IV at +0% Attack Speed, attacks per second. Unmodded: research/attack_speed.md table 2
# (measured 6.71, 7.93 to 8.08, 12.00). With the mod the rule is 8.00; measured 8.01 at 30 FPS and 7.93 at 144 FPS.
FPS = [("30 FPS", 6.7, 8.0), ("60 FPS", 8.0, 8.0), ("144 FPS", 12.0, 8.0)]


def fps():
    x0, unit, top, row, height = 330, 84, 400, 186, 62
    s = header("The same speed at any frame rate", "Gatling Laser IV at +0% Attack Speed: attacks per second")
    s += legend(306, "Unmodded", "With True Attack Speed")
    bottom = top + row * len(FPS) - 36
    for r in (0, 4, 8, 12):
        x = x0 + unit * r
        s += '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2"/>' % (x, top - 16, x, bottom, GRID)
        s += text(x, bottom + 42, "%d /s" % r if r else "0", 28, MUTED, "middle")
    for i, (name, plain, mod) in enumerate(FPS):
        y = top + row * i
        s += text(100, y + 80, name, 44, weight=700)
        for k, (rate, fill) in enumerate(((plain, GREY), (mod, ACCENT))):
            by = y + k * (height + 4)
            s += bar(x0, by, unit * rate, height, fill)
            s += text(x0 + unit * rate + 18, by + 44, "%.1f /s" % rate, 36, INK, weight=700 if k else 400)
    s += text(1496, 640, "8.0", 170, ACCENT, weight=700)
    s += text(1506, 700, "attacks per second,", 34, TAN) + text(1506, 746, "whatever your frame rate", 34, TAN)
    s += text(100, 1030, "Unmodded, the recoil or swing of every attack is timed on rendered frames.", 28, MUTED)
    render("fps", (1920, 1080), s)


# ---------------------------------------------------------------- thumbnail

def thumbnail():
    shot = Image.open(OUT / "_potato_3.png").convert("RGB").crop((556, 60, 1356, 860)).resize((1024, 1024), Image.LANCZOS)
    path = OUT / "_bg_potato.jpg"
    shot.save(path, quality=92)
    s = text(512, 150, "TRUE ATTACK SPEED", 92, INK, "middle", "game")
    s += '<rect x="0" y="800" width="1024" height="224" fill="%s"/>' % ACCENT
    s += text(512, 955, "+100% = ×2", 150, INK, "middle", weight=700)
    shade = "linear-gradient(180deg, rgba(8,8,8,0.85) 0%, rgba(8,8,8,0.75) 18%, rgba(8,8,8,0) 30%, rgba(8,8,8,0) 100%)"
    render("thumbnail", (1024, 1024), s, shade, bg=uri(path))


ALL = {"double": double, "curve": curve, "fps": fps, "thumbnail": thumbnail}
if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name in sys.argv[1:] or ALL:
        ALL[name]()
