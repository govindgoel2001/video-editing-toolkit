"""Extract every EDL range and stop, so captions can be timed off real clips."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import extract_all

ap = argparse.ArgumentParser()
ap.add_argument("edl", type=Path)
ap.add_argument("--draft", action="store_true")
a = ap.parse_args()
from config import load_edl
edl = load_edl(a.edl)
paths, offsets, _ = extract_all(edl, a.draft)
print(f"\n{len(paths)} clips, {offsets[-1]:.1f}s before the last segment")
