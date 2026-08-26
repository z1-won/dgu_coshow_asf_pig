"""Convert AI Hub 622 CVAT keypoint/bbox XML labels into YOLO detection format.

Each annotations.xml (one per recorded clip) contains per-frame <image>
elements with either <box> (scene fixtures: Feedbox, Watercup) or <points>
(a pig instance, labeled with its current behavior: Lying, Standing,
Walking, ...). YOLO needs axis-aligned boxes, so each <points> polygon is
converted to its tight bounding box. Behavior labels are kept as separate
YOLO classes rather than collapsed into one "pig" class, since the source
data already distinguishes them and a detector that both localizes and
classifies behavior is strictly more useful than one that only localizes.

Output label .txt files mirror the relative folder path of their source
annotations.xml, so they can be dropped next to the matching image folder
once the (much larger) source image archive is downloaded and extracted.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from xml.etree import ElementTree as ET

DEFAULT_CLASSES = [
    "Watercup",
    "Feedbox",
    "Scrubbing",
    "Searching",
    "Lying",
    "Resting",
    "Suckling",
    "Urinating",
    "Defecating",
    "Drinking",
    "Standing",
    "Parturition",
    "Walking",
    "Sitting",
    "Running",
    "Eating",
]


def points_to_bbox(points_attr: str) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for pair in points_attr.split(";"):
        x_str, y_str = pair.split(",")
        xs.append(float(x_str))
        ys.append(float(y_str))
    return min(xs), min(ys), max(xs), max(ys)


def convert_annotation_file(
    xml_path: Path, output_root: Path, xml_root: Path, classes: list[str]
) -> dict[str, int]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    class_index = {name: idx for idx, name in enumerate(classes)}
    rel_dir = xml_path.parent.relative_to(xml_root)
    out_dir = output_root / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stats = {"images": 0, "boxes": 0, "skipped_unknown_label": 0}
    for image_el in root.findall("image"):
        width = float(image_el.get("width"))
        height = float(image_el.get("height"))
        name = image_el.get("name")
        stem = Path(name).stem
        lines = []

        for box_el in image_el.findall("box"):
            label = box_el.get("label")
            if label not in class_index:
                stats["skipped_unknown_label"] += 1
                continue
            xtl, ytl = float(box_el.get("xtl")), float(box_el.get("ytl"))
            xbr, ybr = float(box_el.get("xbr")), float(box_el.get("ybr"))
            lines.append(_yolo_line(class_index[label], xtl, ytl, xbr, ybr, width, height))
            stats["boxes"] += 1

        for points_el in image_el.findall("points"):
            label = points_el.get("label")
            if label not in class_index:
                stats["skipped_unknown_label"] += 1
                continue
            xtl, ytl, xbr, ybr = points_to_bbox(points_el.get("points"))
            lines.append(_yolo_line(class_index[label], xtl, ytl, xbr, ybr, width, height))
            stats["boxes"] += 1

        (out_dir / f"{stem}.txt").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        stats["images"] += 1

    return stats


def _yolo_line(class_id: int, xtl: float, ytl: float, xbr: float, ybr: float, width: float, height: float) -> str:
    cx = ((xtl + xbr) / 2) / width
    cy = ((ytl + ybr) / 2) / height
    w = (xbr - xtl) / width
    h = (ybr - ytl) / height
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def build_dataset(xml_root: str | Path, output_dir: str | Path, classes: list[str] | None = None) -> dict[str, int]:
    xml_root = Path(xml_root)
    # "labels_raw" (not "labels") because build_yolo_dataset.py's train/val split
    # needs "labels/train" and "labels/val" free for ultralytics' expected
    # images/<split> <-> labels/<split> sibling convention.
    output_root = Path(output_dir) / "labels_raw"
    classes = classes or DEFAULT_CLASSES

    total = {"images": 0, "boxes": 0, "skipped_unknown_label": 0, "files": 0}
    for xml_path in sorted(xml_root.rglob("annotations.xml")):
        stats = convert_annotation_file(xml_path, output_root, xml_root, classes)
        for key in ("images", "boxes", "skipped_unknown_label"):
            total[key] += stats[key]
        total["files"] += 1

    (Path(output_dir) / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    data_yaml = Path(output_dir) / "data.yaml"
    data_yaml.write_text(
        "\n".join(
            [
                "# Fill in path/train/val once the paired source images are extracted;",
                "# label .txt files are already laid out under labels/<same relative path as annotations.xml>.",
                "path: .",
                "train: images/train",
                "val: images/val",
                f"nc: {len(classes)}",
                f"names: {classes!r}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert 622 CVAT keypoint/bbox XML labels to YOLO format.")
    parser.add_argument("--xml-dir", required=True, help="Directory to search recursively for annotations.xml files.")
    parser.add_argument("--output-dir", default="artifacts/yolo_622_keypoint")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_dataset(args.xml_dir, args.output_dir)
    print(f"annotation files processed: {stats['files']}")
    print(f"images: {stats['images']}")
    print(f"boxes/points converted: {stats['boxes']}")
    print(f"skipped (unknown label): {stats['skipped_unknown_label']}")


if __name__ == "__main__":
    main()
