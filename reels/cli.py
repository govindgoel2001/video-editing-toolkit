"""Render the approved local scene library with a continuous presenter and word timings."""
from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import ROOT, render_job


def main(argv=None):
    parser = argparse.ArgumentParser(prog='toolkit.py reel', description=__doc__)
    parser.add_argument('job', nargs='?', type=Path, help='Version 1 JSON job; paths are relative to this file')
    parser.add_argument('--demo', action='store_true', help='Generate a synthetic 36-second scene-library test')
    parser.add_argument('--dir', type=Path, default=ROOT / 'workspaces/reel-demo')
    parser.add_argument('--model', default='medium', help='Local Whisper model when transcript is omitted')
    parser.add_argument('--language', default='auto')
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--no-render', action='store_true', help='Prepare the project and run HyperFrames checks')
    packs = parser.add_mutually_exclusive_group()
    packs.add_argument('--pack', dest='pack', action='store_true', help='Create a private freelancer asset ZIP (default)')
    packs.add_argument('--no-pack', dest='pack', action='store_false', help='Skip the freelancer asset ZIP')
    parser.set_defaults(pack=True)
    args = parser.parse_args(argv)
    if args.demo == bool(args.job):
        parser.error('Choose a job JSON or --demo.')
    if args.demo:
        from .demo import create
        args.job = create(args.dir / 'inputs')
    render_job(args.job, args.dir, model=args.model, language=args.language,
               draft=args.draft, no_render=args.no_render, pack=args.pack)
