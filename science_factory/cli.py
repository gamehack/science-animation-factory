"""Science animation and editorial short-form CLI; no untrusted code execution."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .pipeline import build
from .schema import Storyboard, StoryboardError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="science-factory", description="Storyboard-driven original video producer")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="Validate the science v1 storyboard")
    validate.add_argument("storyboard", type=Path)
    create = commands.add_parser("build", help="Build or resume a narrated science short")
    create.add_argument("storyboard", type=Path)
    create.add_argument("--output", type=Path, default=Path("output"))
    create.add_argument("--voice", choices=["kokoro", "tone"], default="kokoro")
    create.add_argument("--quality", choices=["preview", "full"], default="preview")
    create.add_argument("--job-id", help="Stable job ID; reuse it to resume verified stages")

    editor_validate = commands.add_parser("validate-editorial", help="Validate editorial storyboard v2")
    editor_validate.add_argument("storyboard", type=Path)
    editor_build = commands.add_parser("build-editorial", help="Build illustrated editorial shorts")
    editor_build.add_argument("storyboard", type=Path)
    editor_build.add_argument("--assets-dir", required=True, type=Path,
                              help="Approved local asset root; storyboard paths must stay within this directory")
    editor_build.add_argument("--output", type=Path, default=Path("output"))
    editor_build.add_argument("--voice", choices=["kokoro", "tone"], default="kokoro")
    editor_build.add_argument("--quality", choices=["preview", "mobile", "full"], default="preview")
    editor_build.add_argument("--job-id", help="Stable job ID; reuse it to resume verified stages")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            sb = Storyboard.from_file(args.storyboard)
            print(json.dumps({"valid": True, "title": sb.title,
                              "scenes": len(sb.scenes),
                              "templates": [scene.kind for scene in sb.scenes]}, indent=2))
            return 0
        if args.command == "validate-editorial":
            from .editorial_schema import EditorialStoryboard
            sb = EditorialStoryboard.from_file(args.storyboard)
            print(json.dumps({"valid": True, "mode": sb.kind, "title": sb.title,
                              "scenes": len(sb.scenes), "music": bool(sb.music)}, indent=2))
            return 0
        if args.command == "build-editorial":
            from .editorial_pipeline import build_editorial
            video = build_editorial(args.storyboard, assets_dir=args.assets_dir,
                                    output_root=args.output, quality=args.quality,
                                    voice=args.voice, job_id=args.job_id)
            print(f"Editorial video generated: {video}")
            if args.voice == "tone":
                print("PREVIEW ONLY: diagnostic tone is not publishable narration")
            return 0
        video = build(args.storyboard, output_root=args.output, voice=args.voice,
                      quality=args.quality, job_id=args.job_id)
        print(f"Video generated: {video}")
        if args.voice == "tone":
            print("TEST-ONLY output: synthetic tone is not publishable narration.")
        return 0
    except (StoryboardError, ValueError, RuntimeError, OSError) as exc:
        print(f"science-factory: {exc}", file=sys.stderr)
        return 2
