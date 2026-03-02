#!/usr/bin/env python3
"""
Exile-UI のゾーンレイアウト画像を poenavi の maps/ ディレクトリにインポートするスクリプト。

使い方:
  python3 tools/import_exile_ui_maps.py [--dry-run] [--backup]

画像名の変換ルール:
  Exile-UI: "{zoneID} {variant}.jpg"
    例: "1_1_2 1.jpg", "1_1_2 1_1.jpg", "1_1_2 x.jpg"
  poenavi: "maps/{日本語ゾーン名}/{variant}.jpg"
    例: "maps/海岸/1.jpg", "maps/海岸/1_1.jpg", "maps/海岸/x.jpg"
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
ZONE_MAP_PATH = PROJECT_DIR / "data" / "exile_ui_zone_map.json"
EXILE_UI_ZONES_DIR = SCRIPT_DIR / "exile_ui_temp" / "img" / "GUI" / "act-decoder" / "zones"
MAPS_DIR = PROJECT_DIR / "maps"
BACKUP_DIR = PROJECT_DIR / "maps_backup"


def load_zone_map():
    with open(ZONE_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_image_filename(filename: str):
    """画像ファイル名からゾーンIDとバリアント部分を分離する。

    例:
      "1_1_2 1.jpg"     → ("1_1_2", "1", ".jpg")
      "1_1_2 1_1.jpg"   → ("1_1_2", "1_1", ".jpg")
      "1_1_2 x.jpg"     → ("1_1_2", "x", ".jpg")
      "1_1_2 x_x.jpg"   → ("1_1_2", "x_x", ".jpg")
    """
    stem = Path(filename).stem
    ext = Path(filename).suffix

    # ゾーンIDとバリアント部分はスペースで区切られている
    parts = stem.split(" ", 1)
    if len(parts) != 2:
        return None, None, None

    zone_id = parts[0]
    variant = parts[1]
    return zone_id, variant, ext


def get_exile_ui_images():
    """Exile-UI のゾーン画像を {zone_id: [(variant, filename), ...]} で返す"""
    images = {}
    if not EXILE_UI_ZONES_DIR.exists():
        print(f"エラー: Exile-UIのゾーン画像ディレクトリが見つかりません: {EXILE_UI_ZONES_DIR}")
        sys.exit(1)

    for f in sorted(EXILE_UI_ZONES_DIR.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        # explanation.jpg などはスキップ
        if " " not in f.name:
            continue

        zone_id, variant, ext = parse_image_filename(f.name)
        if zone_id is None:
            continue

        if zone_id not in images:
            images[zone_id] = []
        images[zone_id].append((variant, f.name, ext))

    return images


def do_import(dry_run=False, backup=False):
    zone_map = load_zone_map()
    exile_images = get_exile_ui_images()

    # 統計
    total_copied = 0
    total_skipped = 0
    zones_processed = 0
    new_dirs_created = 0

    for zone_id, zone_info in sorted(zone_map.items()):
        maps_dir_name = zone_info["maps_dir"]
        target_dir = MAPS_DIR / maps_dir_name

        if zone_id not in exile_images:
            continue

        images = exile_images[zone_id]
        zones_processed += 1

        # バックアップ
        if backup and target_dir.exists() and not dry_run:
            backup_target = BACKUP_DIR / maps_dir_name
            if not backup_target.exists():
                shutil.copytree(target_dir, backup_target)

        # 既存画像を削除（新しい画像で完全に置き換える）
        if target_dir.exists() and not dry_run:
            for existing in target_dir.iterdir():
                if existing.is_file() and existing.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    existing.unlink()

        # ディレクトリ作成
        if not target_dir.exists():
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
            new_dirs_created += 1

        for variant, src_name, ext in images:
            src_path = EXILE_UI_ZONES_DIR / src_name
            dst_path = target_dir / f"{variant}{ext}"

            if dry_run:
                print(f"  [DRY-RUN] {src_path.name} → {dst_path.relative_to(PROJECT_DIR)}")
            else:
                shutil.copy2(src_path, dst_path)

            total_copied += 1

    # マッピングにないExile-UIゾーンの統計
    unmapped_zones = set(exile_images.keys()) - set(zone_map.keys())

    print(f"\n=== インポート{'(DRY-RUN)' if dry_run else ''}完了 ===")
    print(f"  処理ゾーン数: {zones_processed}")
    print(f"  新規ディレクトリ: {new_dirs_created}")
    print(f"  コピーした画像: {total_copied}")
    print(f"  未マッピングゾーン: {len(unmapped_zones)}")
    if unmapped_zones:
        for z in sorted(unmapped_zones):
            print(f"    - {z} ({len(exile_images[z])}枚)")


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    backup = "--backup" in args

    if dry_run:
        print("=== DRY-RUN モード（実際のコピーは行いません）===\n")

    do_import(dry_run=dry_run, backup=backup)


if __name__ == "__main__":
    main()
