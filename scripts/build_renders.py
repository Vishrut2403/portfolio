#!/usr/bin/env python3
"""Turn the raw `Blender Renders/` folder into web-sized media + data/renders.json.

Usage: python3 scripts/build_renders.py   (re-runs only process new files)
Needs: ffmpeg, ffprobe, magick (ImageMagick 7).
"""
import json, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Blender Renders"
OUT = ROOT / "static" / "renders"
MANIFEST = ROOT / "data" / "renders.json"

SKIP_DIRS = {"BL_proxy", "Sprites", "Procedural_ASCII_Art"}  # proxies + a third-party asset pack
SKIP_NAMES = re.compile(r"original footage|texture", re.I)   # raw footage / texture maps, not renders
IMG_EXT, VID_EXT = {".png", ".jpg", ".jpeg"}, {".mp4"}
MAX_VIDEO_SEC = 30
TOKENS = re.compile(r"[_ ]?(4k|8k|60fps|60|tp)(?=[_ .]|$)", re.I)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def key(stem):  # pairing key: "RockyRiver_4K_60FPS" == "Rockyriver_4K"
    return re.sub(r"[\W_]+", "", TOKENS.sub("", stem.lower()))


def pretty(stem):
    return re.sub(r"\s+", " ", TOKENS.sub("", stem).replace("_", " ")).strip()


def run(*cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def to_webp(src, base):
    full, thumb = OUT / f"{base}.webp", OUT / f"{base}.thumb.webp"
    if not full.exists():
        run("magick", f"{src}[0]", "-resize", "1920x1920>", "-quality", "82", str(full))
    if not thumb.exists():
        run("magick", str(full), "-resize", "720x720>", "-quality", "74", str(thumb))
    small = OUT / f"{base}.thumb360.webp"   # srcset variant for phones
    if not small.exists():
        run("magick", str(thumb), "-resize", "360x360>", "-quality", "72", str(small))
    w, h = subprocess.check_output(["magick", "identify", "-format", "%w %h", str(thumb)], text=True).split()
    return int(w), int(h)


def encode_video(src, base):
    out = OUT / f"{base}.mp4"
    if not out.exists():
        run("ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", str(MAX_VIDEO_SEC),
            "-vf", "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v", "libx264", "-crf", "28", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out))
    return out


def poster_from_video(src, base):
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)], text=True))
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "f.png"
        run("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{min(dur * 0.4, MAX_VIDEO_SEC - 1):.2f}",
            "-i", str(src), "-frames:v", "1", str(png))
        return to_webp(png, base)


def collect():
    groups = {}  # (category, sub) -> {"img": [...], "vid": [...]}
    for f in sorted(SRC.rglob("*")):
        rel = f.relative_to(SRC)
        if not f.is_file() or SKIP_DIRS & set(rel.parts) or SKIP_NAMES.search(f.stem):
            continue
        kind = "img" if f.suffix.lower() in IMG_EXT else "vid" if f.suffix.lower() in VID_EXT else None
        if kind:
            g = groups.setdefault((rel.parts[0], rel.parts[1] if len(rel.parts) > 2 else ""), {"img": [], "vid": []})
            g[kind].append(f)

    items = []
    for (cat, sub), g in groups.items():
        images = {key(f.stem): f for f in reversed(g["img"])}  # first file wins on duplicate keys
        used, n = set(), 0
        for f in g["vid"] + g["img"]:
            k = key(f.stem)
            is_vid = f.suffix.lower() in VID_EXT
            if not is_vid and k in used:
                continue  # still already used as a video poster
            title = pretty(f.stem)
            if sub and re.fullmatch(r"untitled\d*|\d{4}-\d{4}|sample|another one", f.stem, re.I):
                n += 1
                title = f"{pretty(sub)} {n:02d}"
            poster = images.get(k) if is_vid else f
            if is_vid and poster:
                used.add(k)
            items.append({
                "src": f, "poster_src": poster, "is_vid": is_vid, "title": title,
                "category": pretty(cat), "base": "/".join(filter(None, [slug(cat), slug(sub), slug(f.stem)])),
            })
    return items


def process(it):
    (OUT / it["base"]).parent.mkdir(parents=True, exist_ok=True)
    w, h = to_webp(it["poster_src"], it["base"]) if it["poster_src"] else poster_from_video(it["src"], it["base"])
    if it["is_vid"]:
        encode_video(it["src"], it["base"])
    print("ok", it["base"], flush=True)
    return {
        "id": it["base"], "title": it["title"], "category": it["category"],
        "thumb": f"renders/{it['base']}.thumb.webp", "full": f"renders/{it['base']}.webp",
        "video": f"renders/{it['base']}.mp4" if it["is_vid"] else "", "w": w, "h": h,
    }


def main():
    items = collect()
    print(f"{len(items)} items ({sum(i['is_vid'] for i in items)} videos)", flush=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        out = list(pool.map(process, items))
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(out, indent=1))
    print(f"wrote {MANIFEST} with {len(out)} items")


if __name__ == "__main__":
    # tiny self-check of the naming rules
    assert key("RockyRiver_4K_60FPS") == key("Rockyriver_4K") == "rockyriver"
    assert key("Abstract Animation_006_4K") == key("Abstract Animation_006") != key("Abstract Animation_007")
    assert pretty("Newton's Craddle_8K") == "Newton's Craddle"
    if "--check" not in sys.argv:
        main()
