#!/usr/bin/env python3
"""
Exile-UI zone ID → poenavi zone name マッピングを生成するスクリプト。

Exile-UIの areas.json の英語名と poenavi の config.json の zone_en を突合して
data/exile_ui_zone_map.json を生成する。
"""

import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

EXILE_UI_AREAS = os.path.join(SCRIPT_DIR, "exile_ui_temp", "data", "english", "[leveltracker] areas.json")
CONFIG_JSON = os.path.join(PROJECT_DIR, "config.json")
OUTPUT_PATH = os.path.join(PROJECT_DIR, "data", "exile_ui_zone_map.json")


def normalize_name(name: str) -> str:
    """英語名を正規化して比較可能にする"""
    # "The " プレフィックスを除去
    name = re.sub(r"^The\s+", "", name, flags=re.IGNORECASE)
    # "(1)" / "(2)" → "Level 1" / "Level 2" への変換（逆方向も）
    # Exile-UI: "Chamber of Sins (1)", poenavi: "The Chamber of Sins Level 1"
    name = re.sub(r"\s*\((\d)\)", r" Level \1", name)
    # 大文字小文字とスペースの正規化
    name = name.strip().lower()
    # 複数スペースを1つに
    name = re.sub(r"\s+", " ", name)
    return name


def load_exile_ui_areas():
    """Exile-UI の areas.json を読み込み、{normalized_name: {id, name, ...}} のdictを返す"""
    with open(EXILE_UI_AREAS, "r", encoding="utf-8") as f:
        data = json.load(f)

    areas = {}
    for act in data:
        for zone in act:
            zone_id = zone["id"]
            zone_name = zone["name"]
            norm = normalize_name(zone_name)
            # town や Labyrinth はスキップ
            if "town" in zone_id or zone_id.startswith("Labyrinth"):
                continue
            # 同じ正規化名が複数ある場合（Part 1 / Part 2）、リストで保持
            if norm not in areas:
                areas[norm] = []
            areas[norm].append({
                "id": zone_id,
                "name": zone_name,
            })
    return areas


def load_poenavi_zones():
    """poenavi の config.json から zone_data を読み込む"""
    with open(CONFIG_JSON, "r", encoding="utf-8") as f:
        config = json.load(f)

    zones = []
    for act_name, act_zones in config["zone_data"].items():
        for zone in act_zones:
            zone_en = zone.get("zone_en", "")
            if not zone_en:
                continue
            zones.append({
                "poenavi_id": zone["id"],
                "zone_jp": zone["zone"],
                "zone_en": zone_en,
                "act": act_name,
                "norm": normalize_name(zone_en),
            })
    return zones


def determine_maps_dir(zone_jp: str, poenavi_id: str) -> str:
    """poenavi の maps/ ディレクトリ名を決定する。
    Part 2 (act6以降) で同名ゾーンの場合は #2 サフィックスを付ける。
    """
    act_num = int(re.search(r"act(\d+)", poenavi_id).group(1))
    if act_num >= 6:
        return f"{zone_jp}#2"
    return zone_jp


def build_mapping():
    exile_areas = load_exile_ui_areas()
    poenavi_zones = load_poenavi_zones()

    mapping = {}
    matched = 0
    unmatched_poenavi = []
    unmatched_exile = set()

    # poenavi の各ゾーンについて Exile-UI のゾーンIDを探す
    for pz in poenavi_zones:
        norm = pz["norm"]
        if norm in exile_areas:
            candidates = exile_areas[norm]
            act_num = int(re.search(r"act(\d+)", pz["poenavi_id"]).group(1))

            # Part判定: act1-5 = Part 1 (1_*), act6-10 = Part 2 (2_*)
            if act_num <= 5:
                part_prefix = "1_"
            else:
                part_prefix = "2_"

            # candidatesからpartが合うものを探す
            matched_candidate = None
            for c in candidates:
                if c["id"].startswith(part_prefix):
                    matched_candidate = c
                    break

            if not matched_candidate and len(candidates) == 1:
                # Part関係なく1つしかない場合はそれを使う
                matched_candidate = candidates[0]

            if matched_candidate:
                exile_id = matched_candidate["id"]

                # maps_dir の決定
                maps_dir = pz["zone_jp"]
                # Part 2 で Part 1 と同名のゾーンがある場合は #2
                if act_num >= 6:
                    # Part 1 に同じ日本語名のゾーンがあるか確認
                    has_part1 = any(
                        z["zone_jp"] == pz["zone_jp"]
                        for z in poenavi_zones
                        if int(re.search(r"act(\d+)", z["poenavi_id"]).group(1)) <= 5
                    )
                    if has_part1:
                        maps_dir = f"{pz['zone_jp']}#2"

                mapping[exile_id] = {
                    "poenavi_id": pz["poenavi_id"],
                    "zone_jp": pz["zone_jp"],
                    "zone_en": pz["zone_en"],
                    "maps_dir": maps_dir,
                }
                matched += 1
            else:
                unmatched_poenavi.append(pz)
        else:
            unmatched_poenavi.append(pz)

    # Exile-UI にのみ存在するゾーンをチェック
    matched_exile_ids = set(mapping.keys())
    for norm, candidates in exile_areas.items():
        for c in candidates:
            if c["id"] not in matched_exile_ids:
                unmatched_exile.add(f"{c['id']} ({c['name']})")

    # 出力
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    # IDでソート
    sorted_mapping = dict(sorted(mapping.items(), key=lambda x: x[0]))
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted_mapping, f, ensure_ascii=False, indent=2)

    print(f"マッピング生成完了: {OUTPUT_PATH}")
    print(f"  マッチ成功: {matched} ゾーン")
    print(f"  poenavi未マッチ: {len(unmatched_poenavi)} ゾーン")
    for uz in unmatched_poenavi:
        print(f"    - {uz['poenavi_id']}: {uz['zone_jp']} ({uz['zone_en']})")
    print(f"  Exile-UI未マッチ: {len(unmatched_exile)} ゾーン")
    for ue in sorted(unmatched_exile):
        print(f"    - {ue}")


if __name__ == "__main__":
    build_mapping()
