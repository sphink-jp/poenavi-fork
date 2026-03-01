"""
海岸8パターンのテンプレートマッチングテスト

各パターンの地形マスクの一部を切り出して「ミニマップ」として使い、
全パターンとテンプレートマッチングして正しいパターンが1位になるか検証する。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
from src.utils.map_matcher import MapMatcher


def self_match_test(matcher: MapMatcher, patterns, zone_name: str):
    """パターン地形マスクの一部を切り出してミニマップとして自己マッチング"""
    print("=== テンプレートマッチング自己テスト ===")
    success = 0
    total = len(patterns)

    for pat in patterns:
        mask = pat.terrain_mask
        h, w = mask.shape

        # 地形がある領域の中心を探す
        coords = cv2.findNonZero(mask)
        if coords is None:
            print(f"  パターン{pat.pattern_index}: 地形なし")
            continue

        # 地形の重心周辺を切り出して「ミニマップ」として使う
        cx = int(np.mean(coords[:, 0, 0]))
        cy = int(np.mean(coords[:, 0, 1]))
        crop_size = min(w, h) // 4  # パターン画像の1/4サイズ

        x1 = max(0, cx - crop_size // 2)
        y1 = max(0, cy - crop_size // 2)
        x2 = min(w, x1 + crop_size)
        y2 = min(h, y1 + crop_size)

        fake_minimap = mask[y1:y2, x1:x2].copy()

        # このクロップをミニマップとしてマッチング
        results = matcher.match_minimap(fake_minimap, zone_name)

        if not results:
            print(f"  パターン{pat.pattern_index}: マッチング失敗")
            continue

        best = results[0]
        is_correct = best.pattern_index == pat.pattern_index
        status = "OK" if is_correct else "NG"
        if is_correct:
            success += 1

        top3 = results[:3]
        scores_str = ", ".join(
            f"P{r.pattern_index}={r.probability:.1f}%({r.score:.3f})" for r in top3
        )
        print(f"  パターン{pat.pattern_index} → 1位: P{best.pattern_index} "
              f"[{status}] | {scores_str}")

    print(f"\n結果: {success}/{total} 正解")
    return success == total


def main():
    maps_dir = os.path.join(os.path.dirname(__file__), "..", "maps", "海岸")
    if not os.path.isdir(maps_dir):
        print(f"エラー: {maps_dir} が見つかりません")
        return

    image_paths = sorted(
        [os.path.join(maps_dir, f) for f in os.listdir(maps_dir)
         if f.lower().endswith((".png", ".jpg"))],
    )

    print(f"パターン数: {len(image_paths)}")
    for p in image_paths:
        print(f"  {os.path.basename(p)}")
    print()

    matcher = MapMatcher()
    patterns = matcher.preprocess_zone("海岸", image_paths)

    print()
    self_match_test(matcher, patterns, "海岸")


if __name__ == "__main__":
    main()
