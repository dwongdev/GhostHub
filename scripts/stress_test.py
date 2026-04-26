## #!/usr/bin/env python3
“””
GhostHub Stress Test Utility - CHAOS EDITION v3

Creates REAL playable video files and viewable images.
Uses ffmpeg for videos, Pillow for images.
Pre-generates a pool of source files then copies with variation for speed.
“””

import os
import sys
import shutil
import signal
import atexit
import argparse
import time
import random
import string
import struct
import threading
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
from PIL import Image, ImageDraw, ImageFont
HAS_PILLOW = True
except ImportError:
HAS_PILLOW = False
print(”[WARN] Pillow not installed - images will use minimal JPEG fallback”)

# ── Cleanup ──────────────────────────────────────────────────────────────────

cleanup_paths = []
cleanup_lock = threading.Lock()
cleanup_enabled = False

def cleanup():
if not cleanup_enabled:
print(”\n[Cleanup disabled]”)
return
print(”\n[Cleaning up…]”)
paths = sorted(set(cleanup_paths), key=lambda x: x.count(os.sep), reverse=True)
for path in paths:
if os.path.exists(path):
try:
shutil.rmtree(path)
print(f”  ✗ {path}”)
except Exception as e:
print(f”  ! Failed {path}: {e}”)

def signal_handler(signum, frame):
cleanup()
sys.exit(0)

atexit.register(cleanup)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# ── Real File Generators ─────────────────────────────────────────────────────

def generate_real_video(output_path, duration=1, width=320, height=240, label=None):
“””
Generate an actual playable MP4 using ffmpeg.
Creates a solid color background with optional text overlay.
“””
color = f”{random.randint(0,255):02x}{random.randint(0,255):02x}{random.randint(0,255):02x}”

```
cmd = [
    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
    "-f", "lavfi",
    "-i", f"color=c=0x{color}:s={width}x{height}:d={duration}:r=24",
]

# Add text overlay if label provided
if label:
    safe_label = label.replace("'", "").replace(":", " ")[:30]
    cmd += [
        "-vf", f"drawtext=text='{safe_label}':fontsize=20:fontcolor=white:"
               f"x=(w-text_w)/2:y=(h-text_h)/2:borderw=2:bordercolor=black"
    ]

cmd += [
    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    str(output_path)
]

try:
    subprocess.run(cmd, check=True, timeout=15, capture_output=True)
    return True
except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
    return False
```

def generate_real_image(output_path, width=320, height=240, label=None):
“””
Generate an actual viewable JPEG using Pillow.
Random gradient/color with optional text.
“””
if not HAS_PILLOW:
# Fallback: minimal valid JPEG
with open(output_path, ‘wb’) as f:
f.write(MINIMAL_JPEG_FALLBACK)
return True

```
try:
    # Random style
    style = random.choice(["solid", "gradient_h", "gradient_v", "noise_block"])
    
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    
    c1 = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
    c2 = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
    
    if style == "solid":
        img.paste(c1, (0, 0, width, height))
    elif style == "gradient_h":
        for x in range(width):
            r = int(c1[0] + (c2[0] - c1[0]) * x / width)
            g = int(c1[1] + (c2[1] - c1[1]) * x / width)
            b = int(c1[2] + (c2[2] - c1[2]) * x / width)
            draw.line([(x, 0), (x, height)], fill=(r, g, b))
    elif style == "gradient_v":
        for y in range(height):
            r = int(c1[0] + (c2[0] - c1[0]) * y / height)
            g = int(c1[1] + (c2[1] - c1[1]) * y / height)
            b = int(c1[2] + (c2[2] - c1[2]) * y / height)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    elif style == "noise_block":
        block = 16
        for y in range(0, height, block):
            for x in range(0, width, block):
                c = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
                draw.rectangle([x, y, x+block, y+block], fill=c)
    
    # Text overlay
    if label:
        safe = label[:25]
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None
        bbox = draw.textbbox((0, 0), safe, font=font) if font else (0, 0, len(safe)*6, 12)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx, ty = (width - tw) // 2, (height - th) // 2
        # Shadow
        draw.text((tx+1, ty+1), safe, fill=(0, 0, 0), font=font)
        draw.text((tx, ty), safe, fill=(255, 255, 255), font=font)
    
    img.save(str(output_path), "JPEG", quality=75)
    return True
except Exception as e:
    print(f"  [img error] {e}")
    return False
```

# Minimal JPEG fallback if no Pillow

MINIMAL_JPEG_FALLBACK = bytes([
0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F,
0x00, 0xFB, 0xD5, 0xDB, 0x20, 0xA8, 0xF1, 0x45, 0x00, 0xFF, 0xD9
])

# ── File Pool (pre-generate, then copy) ──────────────────────────────────────

class FilePool:
“””
Pre-generates a pool of real video/image files, then serves copies.
This is the key trick: ffmpeg encoding is slow (~0.3s per file),
but copying a 15KB file is instant. So we make ~50 unique source files
and copy them out with slight variation.
“””

```
def __init__(self, pool_size_video=40, pool_size_image=20):
    self.pool_dir = Path(tempfile.mkdtemp(prefix="ghosthub_pool_"))
    self.video_pool = []
    self.image_pool = []
    self.pool_size_video = pool_size_video
    self.pool_size_image = pool_size_image
    self._lock = threading.Lock()

def build(self):
    """Pre-generate the pool. This is the slow part (~15-30s)."""
    print(f"Pre-generating file pool ({self.pool_size_video} videos, {self.pool_size_image} images)...")
    start = time.time()
    
    # Videos - parallel ffmpeg calls
    vid_tasks = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        for i in range(self.pool_size_video):
            path = self.pool_dir / f"pool_v_{i:03d}.mp4"
            dur = random.choice([1, 1, 2, 2, 3])
            w, h = random.choice([(320, 240), (640, 480), (480, 360)])
            label = f"Test {i+1}"
            vid_tasks.append(executor.submit(generate_real_video, path, dur, w, h, label))
        
        for i, future in enumerate(as_completed(vid_tasks)):
            if future.result():
                self.video_pool.append(self.pool_dir / f"pool_v_{i:03d}.mp4")
    
    # Images - fast with Pillow
    for i in range(self.pool_size_image):
        path = self.pool_dir / f"pool_i_{i:03d}.jpg"
        w, h = random.choice([(320, 240), (640, 480), (800, 600), (1280, 720)])
        if generate_real_image(path, w, h, f"IMG {i+1}"):
            self.image_pool.append(path)
    
    # Filter to files that actually exist and have content
    self.video_pool = [p for p in self.video_pool if p.exists() and p.stat().st_size > 100]
    self.image_pool = [p for p in self.image_pool if p.exists() and p.stat().st_size > 100]
    
    elapsed = time.time() - start
    print(f"  Pool ready: {len(self.video_pool)} videos, {len(self.image_pool)} images ({elapsed:.1f}s)")
    
    if not self.video_pool:
        print("  [WARN] No videos generated - ffmpeg might have issues. Falling back to direct gen.")

def copy_video(self, dest_path):
    """Copy a random pool video to dest. Fast."""
    if not self.video_pool:
        return generate_real_video(dest_path, 1, 320, 240)
    src = random.choice(self.video_pool)
    try:
        shutil.copy2(str(src), str(dest_path))
        return True
    except Exception:
        return False

def copy_image(self, dest_path):
    """Copy a random pool image to dest. Fast."""
    if not self.image_pool:
        return generate_real_image(dest_path, 320, 240)
    src = random.choice(self.image_pool)
    try:
        shutil.copy2(str(src), str(dest_path))
        return True
    except Exception:
        return False

def cleanup(self):
    """Remove temp pool dir"""
    try:
        shutil.rmtree(self.pool_dir)
    except Exception:
        pass
```

# ── Chaos Generator ──────────────────────────────────────────────────────────

class FastChaos:
“”“Threaded chaos generator using real files from the pool.”””

```
MOVIE_GENRES = {
    "Action": ["War", "Superhero", "Spy", "Martial_Arts", "Disaster"],
    "Comedy": ["Romantic", "Dark", "Slapstick", "Parody", "Sitcom"],
    "Drama": ["Legal", "Medical", "Family", "Political", "Historical"],
    "Horror": ["Zombie", "Supernatural", "Slasher", "Psychological", "Monster"],
    "Sci-Fi": ["Space", "Cyberpunk", "Time_Travel", "Post_Apocalyptic", "Aliens"],
    "Documentary": ["Nature", "History", "True_Crime", "Science", "Biography"],
    "Thriller": ["Crime", "Mystery", "Espionage", "Conspiracy", "Survival"]
}

TV_SHOWS = [
    ("Breaking_Bad", 5), ("The_Office", 9), ("Stranger_Things", 4),
    ("The_Crown", 6), ("Game_of_Thrones", 8), ("Succession", 4),
    ("The_Bear", 3), ("Severance", 2), ("Silo", 2), ("Fargo", 5)
]

UNICODE_WEAPONS = ["🔥", "💀", "🎬", "🌟", "👻", " ", "_", "-"]

def __init__(self, base_path, pool, chaos=0.3, max_workers=8):
    self.base = Path(base_path)
    self.pool = pool
    self.chaos = chaos
    self.max_workers = max_workers
    self.files_created = 0
    self.lock = threading.Lock()
    
def track_root(self, path):
    with cleanup_lock:
        s = str(path)
        if s not in cleanup_paths:
            cleanup_paths.append(s)

def random_name(self, ext=".mp4"):
    adjectives = ["Final", "Last", "Hidden", "Dark", "Lost", "Red", "Silent",
                   "Broken", "Frozen", "Golden", "Iron", "Crimson", "Hollow"]
    nouns = ["Star", "Night", "Shadow", "Storm", "Fire", "River", "Mountain",
             "Crown", "Throne", "Blade", "Dream", "World", "Horizon"]
    
    if random.random() < self.chaos * 0.3:
        name = random.choice(self.UNICODE_WEAPONS) + random.choice(adjectives)
        if random.random() > 0.5:
            name += random.choice(self.UNICODE_WEAPONS)
        name += random.choice(nouns)
    elif random.random() > self.chaos:
        name = f"{random.choice(adjectives)}_{random.choice(nouns)}"
        if random.random() > 0.5:
            name += f"_{random.randint(1990, 2025)}"
    else:
        if random.random() > 0.5:
            name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        else:
            name = f"file_{random.randint(1,9999)}"
    
    return f"{name}{ext}"

def write_file(self, filepath, file_type="mp4"):
    """Copy a real file from the pool to the target path."""
    try:
        if file_type in ("jpg", "jpeg"):
            ok = self.pool.copy_image(filepath)
        else:
            ok = self.pool.copy_video(filepath)
        
        if ok:
            with self.lock:
                self.files_created += 1
        return ok
    except Exception as e:
        return False

def create_deep_movies(self):
    print("  [Movies] generating...")
    movie_root = self.base / "Movies"
    movie_root.mkdir(parents=True, exist_ok=True)
    self.track_root(movie_root)
    
    tasks = []
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        for genre, subgenres in self.MOVIE_GENRES.items():
            if random.random() < 0.1:
                continue
            genre_path = movie_root / genre
            genre_path.mkdir(exist_ok=True)
            
            for _ in range(random.randint(10, 30)):
                tasks.append(executor.submit(
                    self.write_file, genre_path / self.random_name(), "mp4"))
            
            for sub in subgenres:
                if random.random() < 0.2:
                    continue
                sub_path = genre_path / sub
                sub_path.mkdir(exist_ok=True)
                
                for _ in range(random.randint(20, 80)):
                    tasks.append(executor.submit(
                        self.write_file, sub_path / self.random_name(), "mp4"))
                
                if random.random() < self.chaos:
                    deep = sub_path / f"Misc_{random.randint(1,9)}"
                    deep.mkdir(exist_ok=True)
                    for _ in range(random.randint(5, 20)):
                        tasks.append(executor.submit(
                            self.write_file, deep / self.random_name(), "mp4"))
        
        for f in as_completed(tasks):
            pass
    return len(tasks)

def create_tv_structure(self):
    print("  [TV Shows] generating...")
    tv_root = self.base / "TV_Shows"
    tv_root.mkdir(parents=True, exist_ok=True)
    self.track_root(tv_root)
    
    tasks = []
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        for show_name, seasons in self.TV_SHOWS:
            if random.random() < 0.15:
                continue
            show_path = tv_root / show_name
            show_path.mkdir(exist_ok=True)
            
            if random.random() > 0.5:
                extras = show_path / "Extras"
                extras.mkdir(exist_ok=True)
                for i in range(random.randint(3, 8)):
                    ftype = "jpg" if random.random() > 0.7 else "mp4"
                    ext = ".jpg" if ftype == "jpg" else ".mp4"
                    tasks.append(executor.submit(
                        self.write_file, extras / f"Behind_Scenes_{i}{ext}", ftype))
            
            for s in range(1, random.randint(1, seasons) + 1):
                season_path = show_path / f"Season_{s:02d}"
                season_path.mkdir(exist_ok=True)
                
                for e in range(1, random.randint(6, 12) + 1):
                    r = random.random()
                    if r > 0.6:
                        fname = f"{show_name}.S{s:02d}E{e:02d}.mp4"
                    elif r > 0.3:
                        fname = f"S{s:02d}E{e:02d} - Episode_{e}.mp4"
                    else:
                        fname = f"ep_{random.randint(100,999)}.mp4"
                    
                    if random.random() < 0.1:
                        tasks.append(executor.submit(
                            self.write_file,
                            season_path / fname.replace('.mp4', '.thumb.jpg'), "jpg"))
                    
                    tasks.append(executor.submit(
                        self.write_file, season_path / fname, "mp4"))
        
        for f in as_completed(tasks):
            pass
    return len(tasks)

def create_cursed_dumps(self):
    print("  [Cursed dumps] generating...")
    dump_names = ["Downloads", "Temp", "Misc", "Unsorted", "New", "Old"]
    
    tasks = []
    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
        for name in dump_names:
            if random.random() < 0.3:
                continue
            dump_path = self.base / f"{name}_{random.randint(1,5)}"
            dump_path.mkdir(exist_ok=True)
            self.track_root(dump_path)
            
            for _ in range(random.randint(50, 200)):
                ext = random.choice(['.mp4', '.mp4', '.mp4', '.mp4', '.jpg'])
                ftype = "jpg" if ext == ".jpg" else "mp4"
                uname = self.random_name(ext=ext)
                tasks.append(executor.submit(
                    self.write_file, dump_path / uname, ftype))
        
        for f in as_completed(tasks):
            pass
    return len(tasks)

def generate(self, target_files=10000):
    print(f"\nSpawning {self.max_workers} threads for ~{target_files} files...")
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = [
            ex.submit(self.create_deep_movies),
            ex.submit(self.create_tv_structure),
            ex.submit(self.create_cursed_dumps)
        ]
        results = [f.result() for f in futures]
    
    created = self.files_created
    
    if created < target_files:
        remaining = target_files - created
        print(f"  [Batch fill] topping up {remaining} files...")
        batch_size = 200
        tasks = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for i in range(0, remaining, batch_size):
                folder = self.base / f"Batch_{i//batch_size}"
                folder.mkdir(exist_ok=True)
                for j in range(min(batch_size, remaining - i)):
                    ext = ".jpg" if random.random() < 0.15 else ".mp4"
                    ftype = "jpg" if ext == ".jpg" else "mp4"
                    tasks.append(executor.submit(
                        self.write_file, folder / f"media_{i+j:05d}{ext}", ftype))
            for f in as_completed(tasks):
                pass
    
    elapsed = time.time() - start
    rate = self.files_created / elapsed if elapsed > 0 else 0
    print(f"\n  Created {self.files_created} REAL files in {elapsed:.1f}s ({rate:.0f} files/sec)")
```

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
global cleanup_enabled

```
parser = argparse.ArgumentParser(
    description='GhostHub Chaos Generator v3 - Real Playable Files')
parser.add_argument('--path', default='./chaos_test', help='Base output path')
parser.add_argument('--files', type=int, default=5000,
                    help='Target file count (default 5000, pool copies are fast)')
parser.add_argument('--chaos', type=float, default=0.3, help='Chaos level 0.0-1.0')
parser.add_argument('--workers', type=int, default=8, help='Thread pool size')
parser.add_argument('--pool-videos', type=int, default=40,
                    help='Number of unique source videos to generate (more = more variety)')
parser.add_argument('--pool-images', type=int, default=20,
                    help='Number of unique source images to generate')
parser.add_argument('--no-cleanup', action='store_true', help='Keep files after exit')

args = parser.parse_args()
cleanup_enabled = not args.no_cleanup
base_path = os.path.abspath(args.path)

print("=" * 60)
print("GhostHub CHAOS Generator v3 (Real Files Edition)")
print(f"Target: ~{args.files} files @ {base_path}")
print(f"Chaos: {args.chaos} | Workers: {args.workers}")
print(f"Pool: {args.pool_videos} videos, {args.pool_images} images")
print("=" * 60)

pool = FilePool(args.pool_videos, args.pool_images)

try:
    # Phase 1: Build the source pool (slow, ~15-30s for 40 videos)
    pool.build()
    
    # Phase 2: Copy files out into chaos structure (fast)
    os.makedirs(base_path, exist_ok=True)
    gen = FastChaos(base_path, pool, args.chaos, args.workers)
    gen.generate(args.files)
    
    # Stats
    total_size = sum(f.stat().st_size for f in Path(base_path).rglob('*') if f.is_file())
    mp4_count = len(list(Path(base_path).rglob('*.mp4')))
    jpg_count = len(list(Path(base_path).rglob('*.jpg')))
    print(f"\n  Total size: {total_size / 1024/1024:.1f} MB")
    print(f"  Videos: {mp4_count} | Images: {jpg_count}")
    print(f"  Every file is a real, playable media file.")
    
    if cleanup_enabled:
        print("\nRunning... Ctrl+C to cleanup & exit")
        while True:
            time.sleep(1)
    else:
        print(f"\nFiles preserved at: {base_path}")
        
except KeyboardInterrupt:
    print("\nStopping...")
finally:
    pool.cleanup()
```

if **name** == ‘**main**’:
main()