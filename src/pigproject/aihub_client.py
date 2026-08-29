"""Small wrapper around AI Hub's official aihubshell downloader."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_AIHUBSHELL = PROJECT_ROOT / "bin" / "aihubshell"
DATASET_MANIFEST = PROJECT_ROOT / "config" / "aihub_datasets.json"


def get_api_key(required: bool = False) -> str | None:
    key = os.environ.get("AIHUB_API_KEY")
    if required and not key:
        raise RuntimeError("AIHUB_API_KEY is not set. Export it before downloading data.")
    return key


def shell_bin() -> str:
    configured = os.environ.get("AIHUBSHELL_BIN")
    if configured:
        return configured
    if PROJECT_AIHUBSHELL.exists():
        return str(PROJECT_AIHUBSHELL)
    return "aihubshell"


def run_aihubshell(
    args: list[str],
    capture: bool = False,
    cwd: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [shell_bin(), *args]
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=capture,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "aihubshell executable was not found. "
            "Set AIHUBSHELL_BIN or place it at /Users/bangjiwon/dev/pigproject/bin/aihubshell."
        ) from exc


def list_datasets() -> str:
    result = run_aihubshell(["-mode", "l"], capture=True)
    return result.stdout


def list_files(dataset_key: str) -> str:
    result = run_aihubshell(["-mode", "l", "-datasetkey", dataset_key], capture=True)
    return result.stdout


def download_dataset(
    dataset_key: str,
    output_dir: str | Path,
    file_key: str | None = None,
) -> None:
    api_key = get_api_key(required=True)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    args = [
        "-mode",
        "d",
        "-datasetkey",
        dataset_key,
    ]
    if file_key:
        args.extend(["-filekey", file_key])
    args.extend(["-aihubapikey", api_key or ""])

    run_aihubshell(args, capture=False, cwd=output)


def load_dataset_manifest() -> dict[str, object]:
    if not DATASET_MANIFEST.exists():
        raise FileNotFoundError(f"Dataset manifest not found: {DATASET_MANIFEST}")
    return json.loads(DATASET_MANIFEST.read_text(encoding="utf-8"))


def recommended_downloads(dataset_key: str | None = None) -> str:
    manifest = load_dataset_manifest()
    keys = [dataset_key] if dataset_key else sorted(manifest)
    lines: list[str] = []
    for key in keys:
        item = manifest.get(key)
        if not isinstance(item, dict):
            lines.append(f"{key}: not found")
            continue
        lines.append(f"{key}: {item.get('name')} [{item.get('track')}]")
        note = item.get("note")
        if note:
            lines.append(f"  note: {note}")
        for rec in item.get("recommended_first_downloads", []):
            file_key = rec.get("file_key") or "TBD after `pig-aihub files`"
            lines.append(
                "  - "
                f"{rec.get('split')} / {rec.get('modality')} / {rec.get('filename')} "
                f"({rec.get('size')}) filekey={file_key} "
                f"- {rec.get('reason')}"
            )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Hub aihubshell wrapper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List available datasets.")

    files = subparsers.add_parser("files", help="List files for a dataset.")
    files.add_argument("--dataset-key", required=True)

    recommended = subparsers.add_parser("recommended", help="Show recommended first downloads.")
    recommended.add_argument("--dataset-key", default=None)

    download = subparsers.add_parser("download", help="Download a dataset or a specific file.")
    download.add_argument("--dataset-key", required=True)
    download.add_argument("--file-key", default=None)
    download.add_argument("--output-dir", default="data/raw/aihub")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "list":
        print(list_datasets(), end="")
    elif args.command == "files":
        print(list_files(args.dataset_key), end="")
    elif args.command == "recommended":
        print(recommended_downloads(args.dataset_key), end="")
    elif args.command == "download":
        download_dataset(
            dataset_key=args.dataset_key,
            file_key=args.file_key,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
