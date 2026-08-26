"""Pair YOLO label files (from keypoint_to_yolo.py) with their source images
and lay them out in the images/{train,val} + labels/{train,val} structure
ultralytics expects.

Split by clip (each annotations.xml's parent folder), not by frame: frames
5 apart in the same clip are near-duplicates, so splitting at the frame
level would leak near-identical images across train/val and make the
validation score meaningless.
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


def index_images_by_stem(image_root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in image_root.rglob("*"):
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            index.setdefault(path.stem, []).append(path)
    return index


def pair_images_and_labels(image_root: Path, label_root: Path) -> list[tuple[Path, Path]]:
    image_index = index_images_by_stem(image_root)
    pairs: list[tuple[Path, Path]] = []
    unmatched = 0
    for label_path in label_root.rglob("*.txt"):
        rel = label_path.relative_to(label_root)
        candidate = None
        for ext in IMAGE_EXTENSIONS:
            guess = image_root / rel.with_suffix(ext)
            if guess.exists():
                candidate = guess
                break
        if candidate is None:
            matches = image_index.get(label_path.stem, [])
            if len(matches) == 1:
                candidate = matches[0]
        if candidate is None:
            unmatched += 1
            continue
        pairs.append((candidate, label_path))
    if unmatched:
        print(f"warning: {unmatched} label files had no matching image")
    return pairs


def split_by_clip(
    pairs: list[tuple[Path, Path]], label_root: Path, val_ratio: float = 0.2, seed: int = 42
) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    by_clip: dict[Path, list[tuple[Path, Path]]] = {}
    for image_path, label_path in pairs:
        clip = label_path.relative_to(label_root).parent
        by_clip.setdefault(clip, []).append((image_path, label_path))

    clips = sorted(by_clip.keys())
    rng = random.Random(seed)
    rng.shuffle(clips)
    val_count = max(1, int(len(clips) * val_ratio))
    val_clips = set(clips[:val_count])

    train, val = [], []
    for clip, items in by_clip.items():
        (val if clip in val_clips else train).extend(items)
    return train, val


def materialize(pairs: list[tuple[Path, Path]], output_dir: Path, split: str, link: bool = True) -> None:
    images_dir = output_dir / "images" / split
    labels_dir = output_dir / "labels" / split
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    for image_path, label_path in pairs:
        image_dst = images_dir / f"{label_path.parent.name}__{image_path.name}"
        label_dst = labels_dir / f"{label_path.parent.name}__{label_path.name}"
        for src, dst in ((image_path, image_dst), (label_path, label_dst)):
            if dst.exists() or dst.is_symlink():
                continue
            if link:
                dst.symlink_to(src.resolve())
            else:
                shutil.copy2(src, dst)


def build(image_root: str | Path, label_root: str | Path, output_dir: str | Path, val_ratio: float = 0.2) -> dict[str, int]:
    image_root, label_root, output_dir = Path(image_root), Path(label_root), Path(output_dir)
    pairs = pair_images_and_labels(image_root, label_root)
    train, val = split_by_clip(pairs, label_root, val_ratio=val_ratio)
    materialize(train, output_dir, "train")
    materialize(val, output_dir, "val")
    return {"paired": len(pairs), "train": len(train), "val": len(val)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pair YOLO labels with source images and split by clip.")
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--label-root", default="artifacts/yolo_622_keypoint/labels_raw")
    parser.add_argument("--output-dir", default="artifacts/yolo_622_keypoint")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build(args.image_root, args.label_root, args.output_dir, val_ratio=args.val_ratio)
    print(f"paired: {stats['paired']}  train: {stats['train']}  val: {stats['val']}")


if __name__ == "__main__":
    main()
