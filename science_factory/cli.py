"""CLI entry point. No interactive prompts or hidden paid fallbacks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import build
from .schema import Storyboard, StoryboardError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="science-factory", description="Original science animation factory")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate a safe, declarative storyboard")
    validate.add_argument("storyboard", type=Path)

    create = commands.add_parser("build", help="Build a narrated short from a storyboard")
    create.add_argument("storyboard", type=Path)
    create.add_argument("--output", type=Path, default=Path("output"))
    create.add_argument("--voice", choices=["kokoro", "tone"], default="kokoro")
    create.add_argument("--quality", choices=["preview", "full"], default="preview")

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            sb = Storyboard.from_file(args.storyboard)
            print(json.dumps({"valid": True, "title": sb.title, "scenes": len(sb.scenes),
                              "templates": [scene.kind for scene in sb.scenes]}, indent=2))
            return 0
        video = build(args.storyboard, output_root=args.output, voice=args.voice, quality=args.quality)
        print(f"Video generated: {video}")
        if args.voice == "tone":
            print("TEST-ONLY output: synthetic tone is not publishable narration.")
        return 0
    except (StoryboardError, ValueError, RuntimeError, OSError) as exc:
        print(f"science-factory: {exc}", file=sys.stderr)
        return 2

