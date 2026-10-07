"""Draw the app icons from the planner's own icon (tools/build.py), into assets/generated/.

They're generated rather than committed because tools/build.py --check keeps every image out of the repo.
Runs before every prebuild (npm run prebuild / EAS post-install). Needs Pillow.
"""
import sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.parent / "tools"))
from build import make_icons  # noqa: E402
from PIL import Image  # noqa: E402

out = HERE / "assets" / "generated"
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    make_icons(Path(tmp))
    square = Image.open(Path(tmp) / "icon-maskable-512.png").convert("RGBA")
    square.resize((1024, 1024), Image.LANCZOS).save(out / "icon.png")
    # Adaptive icon: the launcher masks it, so the glyph needs the extra padding of the maskable icon.
    square.resize((1024, 1024), Image.LANCZOS).save(out / "adaptive-icon.png")
    # Notification icon: Android shows only the alpha channel, so keep the white glyph and drop the blue.
    small = square.resize((96, 96), Image.LANCZOS)
    mono = Image.new("RGBA", small.size, (255, 255, 255, 0))
    mono.putalpha(small.getchannel("R").point(lambda v: max(0, min(255, (v - 90) * 255 // 165))))  # blue has little red, white has all
    mono.save(out / "notification-icon.png")
print("icons ->", out.relative_to(HERE))
