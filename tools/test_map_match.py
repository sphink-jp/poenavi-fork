"""
海岸8パターンの自己マッチングテスト

各パターンのスポーン周辺切り出しを「ミニマップ」として使い、
全パターンと比較して自分自身が1位に来るか検証する。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np
from src.utils.map_matcher import MapMatcher


def direct_match_test(matcher: MapMatcher, patterns, zone_name: str):
    """前処理済みマスク同士を直接比較（ミニマップ処理をバイパス）"""
    print("=== 直接マスク比較テスト ===")
    success = 0
    total = len(patterns)

    for test_pat in patterns:
        scores = []
        for ref_pat in patterns:
            # Hu Moments距離
            hu_dist = cv2.matchShapes(
                test_pat.spawn_crop_mask, ref_pat.spawn_crop_mask,
                cv2.CONTOURS_MATCH_I2, 0,
            )

            # 最大輪郭マッチ
            contour_dist = 0.0
            if test_pat.spawn_crop_contours and ref_pat.spawn_crop_contours:
                test_largest = max(test_pat.spawn_crop_contours, key=cv2.contourArea)
                ref_largest = max(ref_pat.spawn_crop_contours, key=cv2.contourArea)
                contour_dist = cv2.matchShapes(
                    test_largest, ref_largest,
                    cv2.CONTOURS_MATCH_I2, 0,
                )

            # アスペクト比差
            ar_diff = abs(test_pat.local_aspect_ratio - ref_pat.local_aspect_ratio)
            ar_score = ar_diff / max(test_pat.local_aspect_ratio, ref_pat.local_aspect_ratio, 0.01)

            combined = 0.5 * hu_dist + 0.3 * contour_dist + 0.2 * ar_score
            scores.append((ref_pat.pattern_index, combined))

        scores.sort(key=lambda x: x[1])
        best_idx, best_score = scores[0]
        is_correct = best_idx == test_pat.pattern_index
        status = "OK" if is_correct else "NG"
        if is_correct:
            success += 1

        top3 = scores[:3]
        scores_str = ", ".join(f"P{idx}={s:.4f}" for idx, s in top3)
        print(f"  パターン{test_pat.pattern_index} → 1位: P{best_idx} [{status}] | {scores_str}")

    print(f"\n結果: {success}/{total} 正解")
    return success == total


def minimap_simulation_test(matcher: MapMatcher, patterns, zone_name: str):
    """spawn_crop_maskをそのままmatch_minimapに渡すテスト"""
    print("=== ミニマップシミュレーションテスト ===")
    success = 0
    total = len(patterns)

    for pat in patterns:
        # グレースケールマスクをそのまま渡す（_process_minimapが二値対応済み）
        results = matcher.match_minimap(pat.spawn_crop_mask, zone_name)

        if not results:
            print(f"  パターン{pat.pattern_index}: マッチング失敗")
            continue

        best = results[0]
        is_correct = best.pattern_index == pat.pattern_index
        status = "OK" if is_correct else "NG"
        if is_correct:
            success += 1

        top3 = results[:3]
        scores_str = ", ".join(f"P{r.pattern_index}={r.score:.4f}" for r in top3)
        print(f"  パターン{pat.pattern_index} → 1位: P{best.pattern_index} "
              f"[{status}] ({best.confidence}) | {scores_str}")

    print(f"\n結果: {success}/{total} 正解")
    return success == total


def main():
    maps_dir = os.path.join(os.path.dirname(__file__), "..", "maps", "海岸")
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

    print("=== 前処理結果 ===")
    for pat in patterns:
        spawn_str = f"({pat.spawn_point[0]}, {pat.spawn_point[1]})" if pat.spawn_point else "未検出"
        crop_pixels = cv2.countNonZero(pat.spawn_crop_mask)
        n_contours = len(pat.spawn_crop_contours)
        print(f"  パターン{pat.pattern_index}: spawn={spawn_str}, "
              f"白px={crop_pixels}, contours={n_contours}, aspect={pat.local_aspect_ratio:.2f}")
    print()

    # デバッグ用: 切り出し画像を保存
    debug_dir = os.path.join(os.path.dirname(__file__), "..", "debug_crops")
    os.makedirs(debug_dir, exist_ok=True)
    for pat in patterns:
        cv2.imwrite(
            os.path.join(debug_dir, f"crop_{pat.pattern_index}.png"),
            pat.spawn_crop_mask,
        )
    print(f"切り出し画像を {debug_dir} に保存しました\n")

    # テスト1: 直接比較
    direct_ok = direct_match_test(matcher, patterns, "海岸")
    print()

    # テスト2: ミニマップシミュレーション
    minimap_ok = minimap_simulation_test(matcher, patterns, "海岸")


if __name__ == "__main__":
    main()
