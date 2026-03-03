"""
マップパターン自動検出（テンプレートマッチング方式）

パターン画像から注釈除外済みの地形マスクを生成し、
ミニマップの地形マスクをテンプレートとしてスライドマッチングで一致箇所を探す。
"""
from __future__ import annotations

import os
import sys
import cv2
import numpy as np
from dataclasses import dataclass


def _get_debug_dir():
    """デバッグ画像の保存先"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "debug_capture")


@dataclass
class PatternData:
    """前処理済みパターンデータ"""
    pattern_index: int
    image_path: str
    terrain_mask: np.ndarray  # 注釈除外済み地形マスク（二値画像）


@dataclass
class MatchResult:
    """マッチング結果"""
    pattern_index: int
    image_path: str
    score: float          # テンプレートマッチングスコア (0-1, 高い=一致)
    probability: float    # 確率 (0-100)
    match_loc: tuple[int, int] = (0, 0)  # マッチ位置 (デバッグ用)


class MapMatcher:
    """テンプレートマッチングでミニマップからパターンを特定"""

    # マルチスケールマッチングのスケール範囲
    # ミニマップ1pxがパターン画像の何pxに相当するか
    SCALE_MIN = 0.5
    SCALE_MAX = 3.0
    SCALE_STEPS = 20

    def __init__(self):
        self._cache: dict[str, list[PatternData]] = {}

    def preprocess_zone(self, zone_name: str, image_paths: list[str]) -> list[PatternData]:
        """ゾーンの全パターン画像を前処理してキャッシュ"""
        if zone_name in self._cache:
            return self._cache[zone_name]

        patterns = []
        for i, path in enumerate(image_paths):
            data = self._preprocess_single(path, i + 1)
            if data is not None:
                patterns.append(data)

        print(f"[MATCH] 前処理完了: zone={zone_name}, "
              f"画像数={len(image_paths)}, 成功={len(patterns)}")

        # デバッグ: 地形マスクを保存
        try:
            debug_dir = _get_debug_dir()
            os.makedirs(debug_dir, exist_ok=True)
            for pat in patterns:
                fname = f"terrain_P{pat.pattern_index}.png"
                cv2.imwrite(os.path.join(debug_dir, fname), pat.terrain_mask)
                h, w = pat.terrain_mask.shape
                px = cv2.countNonZero(pat.terrain_mask)
                print(f"[MATCH]   P{pat.pattern_index}: {w}x{h}, 地形px={px}")
        except Exception as e:
            print(f"[MATCH] デバッグ保存失敗: {e}")

        self._cache[zone_name] = patterns
        return patterns

    @staticmethod
    def _imread_safe(path: str, flags=cv2.IMREAD_UNCHANGED) -> np.ndarray | None:
        """日本語パス対応の画像読み込み"""
        try:
            data = np.fromfile(path, dtype=np.uint8)
            return cv2.imdecode(data, flags)
        except Exception:
            return None

    def _preprocess_single(self, image_path: str, index: int) -> PatternData | None:
        """1枚のパターン画像を前処理"""
        image = self._imread_safe(image_path)
        if image is None:
            print(f"[MATCH] 画像読み込み失敗: {image_path}")
            return None

        if image.shape[2] == 4:
            bgr = image[:, :, :3]
        else:
            bgr = image

        terrain_gray = self._extract_terrain_gray(bgr)

        return PatternData(
            pattern_index=index,
            image_path=image_path,
            terrain_mask=terrain_gray,
        )

    def _extract_terrain_gray(self, bgr: np.ndarray) -> np.ndarray:
        """ガイド注釈（ピンク矢印）だけ消してグレースケール化

        グレースケール変換後、オレンジ◆（出入口）と水色十字（ウェイポイント）の
        ピクセルを白(255)に復元し、テンプレートマッチングの特徴点として強調する。
        """
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # 背景マスク（濃紺 = V < 50）
        bg_mask = hsv[:, :, 2] < 50

        # ガイド注釈だけ除外（ピンク矢印/丸: H=140-175, S>80, V>120）
        pink = cv2.inRange(hsv, np.array([140, 80, 120]), np.array([175, 255, 255]))

        # オレンジ◆（出入口マーカー: H=5-25, S>100, V>150）
        orange = cv2.inRange(hsv, np.array([5, 100, 150]), np.array([25, 255, 255]))

        # 水色十字（ウェイポイント: H=85-105, S>80, V>150）
        cyan = cv2.inRange(hsv, np.array([85, 80, 150]), np.array([105, 255, 255]))

        # グレースケール化
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # 背景を黒に、ピンク注釈を黒に
        gray[bg_mask] = 0
        gray[pink > 0] = 0

        # オレンジ◆と水色十字を白(255)に復元 → 強い特徴点になる
        gray[orange > 0] = 255
        gray[cyan > 0] = 255

        return gray

    def _extract_minimap_gray(self, minimap_bgr: np.ndarray) -> np.ndarray | None:
        """ミニマップをグレースケール化（未探索領域=黒）

        オレンジ◆と水色十字をパターン画像と同様に白(255)に強調する。
        """
        if minimap_bgr is None or minimap_bgr.size == 0:
            return None

        if len(minimap_bgr.shape) == 2:
            return minimap_bgr

        hsv = cv2.cvtColor(minimap_bgr, cv2.COLOR_BGR2HSV)

        # 背景（暗い部分=未探索）
        bg_mask = hsv[:, :, 2] < 40

        # オレンジ◆（出入口マーカー）
        orange = cv2.inRange(hsv, np.array([5, 100, 150]), np.array([25, 255, 255]))

        # 水色十字（ウェイポイント）
        cyan = cv2.inRange(hsv, np.array([85, 80, 150]), np.array([105, 255, 255]))

        # グレースケール化
        gray = cv2.cvtColor(minimap_bgr, cv2.COLOR_BGR2GRAY)
        gray[bg_mask] = 0

        # マーカーを白に強調
        gray[orange > 0] = 255
        gray[cyan > 0] = 255

        return gray

    def match_minimap(self, minimap_image: np.ndarray, zone_name: str) -> list[MatchResult]:
        """ミニマップをテンプレートとして全パターンとマッチング"""
        patterns = self._cache.get(zone_name)
        if not patterns:
            print(f"[MATCH] キャッシュなし: zone={zone_name}")
            return []

        print(f"[MATCH] マッチング開始: zone={zone_name}, パターン数={len(patterns)}, "
              f"入力画像={minimap_image.shape}")

        # ミニマップのグレースケール地形画像を抽出
        mini_mask = self._extract_minimap_gray(minimap_image)
        if mini_mask is None:
            print("[MATCH] エラー: ミニマップマスク抽出失敗")
            return []

        nonzero = cv2.countNonZero(mini_mask)
        print(f"[MATCH] ミニマップマスク: {mini_mask.shape}, 白px={nonzero}")

        if nonzero == 0:
            print("[MATCH] エラー: ミニマップマスクが全黒")
            return []

        # デバッグ: ミニマップマスクを保存
        try:
            debug_dir = _get_debug_dir()
            os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(os.path.join(debug_dir, "last_minimap_mask.png"), mini_mask)
        except Exception:
            pass

        # マルチスケールテンプレートマッチング
        scales = np.linspace(self.SCALE_MIN, self.SCALE_MAX, self.SCALE_STEPS)
        pattern_scores = []

        for pat in patterns:
            best_score = -1.0
            best_loc = (0, 0)
            best_scale = 1.0

            for scale in scales:
                score, loc = self._template_match_at_scale(
                    pat.terrain_mask, mini_mask, scale
                )
                if score > best_score:
                    best_score = score
                    best_loc = loc
                    best_scale = scale

            pattern_scores.append((pat, best_score, best_loc, best_scale))
            print(f"[MATCH]   P{pat.pattern_index}: score={best_score:.4f} "
                  f"scale={best_scale:.2f} loc=({best_loc[0]},{best_loc[1]})")

        # スコアを確率に変換
        scores = [s for _, s, _, _ in pattern_scores]
        probabilities = self._scores_to_probabilities(scores)

        results = []
        for i, (pat, score, loc, scale) in enumerate(pattern_scores):
            results.append(MatchResult(
                pattern_index=pat.pattern_index,
                image_path=pat.image_path,
                score=score,
                probability=probabilities[i],
                match_loc=loc,
            ))

        # デバッグ: ベストマッチの位置を可視化
        try:
            debug_dir = _get_debug_dir()
            best_pat, best_score, best_loc, best_scale = max(
                pattern_scores, key=lambda x: x[1]
            )
            # パターン画像にマッチ位置を描画
            vis = cv2.cvtColor(best_pat.terrain_mask, cv2.COLOR_GRAY2BGR)
            th, tw = mini_mask.shape
            scaled_w = int(tw * best_scale)
            scaled_h = int(th * best_scale)
            cv2.rectangle(vis, best_loc,
                         (best_loc[0] + scaled_w, best_loc[1] + scaled_h),
                         (0, 255, 0), 3)
            cv2.imwrite(os.path.join(debug_dir, "best_match_vis.png"), vis)
            print(f"[MATCH] ベスト: P{best_pat.pattern_index} "
                  f"(score={best_score:.4f}, scale={best_scale:.2f}) "
                  f"→ debug_capture/best_match_vis.png")
        except Exception:
            pass

        results.sort(key=lambda r: r.probability, reverse=True)
        return results

    def _template_match_at_scale(
        self,
        pattern_mask: np.ndarray,
        mini_mask: np.ndarray,
        scale: float,
    ) -> tuple[float, tuple[int, int]]:
        """指定スケールでテンプレートマッチングを実行

        scale: ミニマップ1pxがパターン画像の何pxに相当するか
        """
        th, tw = mini_mask.shape
        new_w = int(tw * scale)
        new_h = int(th * scale)

        # テンプレートがパターン画像より大きくなったらスキップ
        ph, pw = pattern_mask.shape
        if new_w >= pw or new_h >= ph or new_w < 10 or new_h < 10:
            return -1.0, (0, 0)

        # ミニマップマスクをリサイズ
        template = cv2.resize(mini_mask, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # テンプレートマッチング (正規化相関係数)
        result = cv2.matchTemplate(
            pattern_mask, template, cv2.TM_CCOEFF_NORMED
        )

        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return max_val, max_loc

    def _scores_to_probabilities(self, scores: list[float]) -> list[float]:
        """テンプレートマッチングスコア(高い=良い)を確率(%)に変換"""
        if not scores:
            return []
        if len(scores) == 1:
            return [100.0]

        arr = np.array(scores, dtype=np.float64)

        # スコアを0以上にクリップ（負のスコアは無関係）
        arr = np.clip(arr, 0, None)

        total = np.sum(arr)
        if total == 0:
            return [100.0 / len(scores)] * len(scores)

        # スコアの差を強調するために二乗
        arr_sq = arr ** 2
        total_sq = np.sum(arr_sq)
        if total_sq == 0:
            return [100.0 / len(scores)] * len(scores)

        probs = (arr_sq / total_sq) * 100.0
        return probs.tolist()
