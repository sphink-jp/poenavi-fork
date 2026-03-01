"""
マップパターン自動検出
ミニマップのスクリーンショットと各パターン画像の輪郭を比較し、
一致するパターンを特定する。
"""
from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PatternData:
    """前処理済みパターンデータ"""
    pattern_index: int
    image_path: str
    spawn_point: tuple[int, int] | None
    spawn_crop_mask: np.ndarray
    spawn_crop_contours: list
    hu_moments: np.ndarray
    local_aspect_ratio: float


@dataclass
class MatchResult:
    """マッチング結果"""
    pattern_index: int
    image_path: str
    score: float        # 低いほど一致度が高い
    confidence: str     # "high", "medium", "low"
    confidence_pct: float = 0.0  # 信頼度パーセント (0-100)


class MapMatcher:
    """パターン画像の前処理とミニマップとのマッチングを行う"""

    # スポーン地点の青い十字マーカー (HSV)
    SPAWN_H_LOW, SPAWN_H_HIGH = 90, 115
    SPAWN_S_LOW = 80
    SPAWN_V_LOW = 150

    # スポーン周辺の切り出し半径（参照画像のピクセル単位）
    SPAWN_CROP_RADIUS = 150

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

        self._cache[zone_name] = patterns
        return patterns

    def _preprocess_single(self, image_path: str, index: int) -> PatternData | None:
        """1枚のパターン画像を前処理"""
        image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            return None

        # BGRに変換（BGRA対応）
        if image.shape[2] == 4:
            bgr = image[:, :, :3]
        else:
            bgr = image

        # 地形マスクを抽出
        terrain_mask = self._extract_terrain_mask(bgr)

        # スポーン地点を検出
        spawn = self._find_spawn_point(bgr)

        # スポーン周辺を切り出し
        if spawn is not None:
            crop = self._crop_around_spawn(terrain_mask, spawn, self.SPAWN_CROP_RADIUS)
        else:
            # スポーン検出失敗時は画像中央を使用
            h, w = terrain_mask.shape
            crop = self._crop_around_spawn(terrain_mask, (w // 2, h // 2), self.SPAWN_CROP_RADIUS)

        # 輪郭を検出
        contours, _ = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Hu Momentsを計算
        moments = cv2.moments(crop)
        hu = cv2.HuMoments(moments).flatten()

        # アスペクト比を計算
        aspect = self._compute_aspect_ratio(contours)

        return PatternData(
            pattern_index=index,
            image_path=image_path,
            spawn_point=spawn,
            spawn_crop_mask=crop,
            spawn_crop_contours=contours,
            hu_moments=hu,
            local_aspect_ratio=aspect,
        )

    def _extract_terrain_mask(self, bgr: np.ndarray) -> np.ndarray:
        """HSV色分離で地形マスクを抽出（背景・注釈を除外）"""
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # 背景（濃紺）以外を抽出: V > 50 で暗い背景を除外
        _, not_bg = cv2.threshold(hsv[:, :, 2], 50, 255, cv2.THRESH_BINARY)

        # 注釈を除外
        # ピンク矢印/丸: H=140-175, S>80, V>120
        pink = cv2.inRange(hsv, np.array([140, 80, 120]), np.array([175, 255, 255]))
        # オレンジ◆: H=10-25, S>150, V>150
        orange = cv2.inRange(hsv, np.array([10, 150, 150]), np.array([25, 255, 255]))
        # 青十字: H=90-115, S>80, V>150
        blue = cv2.inRange(hsv, np.array([90, 80, 150]), np.array([115, 255, 255]))
        # 黄マーカー: H=25-35, S>150, V>150
        yellow = cv2.inRange(hsv, np.array([25, 150, 150]), np.array([35, 255, 255]))

        annotations = pink | orange | blue | yellow

        # 地形 = 背景でない & 注釈でない
        terrain = not_bg & ~annotations

        # モルフォロジー処理でノイズ除去・穴埋め
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        terrain = cv2.morphologyEx(terrain, cv2.MORPH_CLOSE, kernel)
        terrain = cv2.morphologyEx(terrain, cv2.MORPH_OPEN, kernel)

        return terrain

    def _find_spawn_point(self, bgr: np.ndarray) -> tuple[int, int] | None:
        """青い十字マーカーの中心座標を検出"""
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(
            hsv,
            np.array([self.SPAWN_H_LOW, self.SPAWN_S_LOW, self.SPAWN_V_LOW]),
            np.array([self.SPAWN_H_HIGH, 255, 255]),
        )

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # 最大の青領域の重心を返す
        largest = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest)
        if M["m00"] == 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)

    def _crop_around_spawn(self, mask: np.ndarray, center: tuple[int, int], radius: int) -> np.ndarray:
        """指定中心点の周辺を円形マスク付きで切り出し"""
        h, w = mask.shape
        cx, cy = center

        # 切り出し範囲を計算（画像端をクリップ）
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)

        crop = mask[y1:y2, x1:x2].copy()

        # 円形マスクを適用
        crop_h, crop_w = crop.shape
        circle_mask = np.zeros((crop_h, crop_w), dtype=np.uint8)
        center_in_crop = (cx - x1, cy - y1)
        cv2.circle(circle_mask, center_in_crop, radius, 255, -1)
        crop = cv2.bitwise_and(crop, circle_mask)

        return crop

    def _compute_aspect_ratio(self, contours: list) -> float:
        """最大輪郭のバウンディングボックスのアスペクト比を計算"""
        if not contours:
            return 1.0
        largest = max(contours, key=cv2.contourArea)
        _, _, w, h = cv2.boundingRect(largest)
        return w / h if h > 0 else 1.0

    def match_minimap(self, minimap_image: np.ndarray, zone_name: str) -> list[MatchResult]:
        """ミニマップ画像を全パターンと比較し、スコア順にソートして返す"""
        patterns = self._cache.get(zone_name)
        if not patterns:
            return []

        # ミニマップの地形を抽出
        mini_mask, mini_contours, mini_hu, mini_aspect = self._process_minimap(minimap_image)

        if mini_mask is None or cv2.countNonZero(mini_mask) == 0:
            return []

        # 各パターンとスコアを計算
        results = []
        scores = []
        for pat in patterns:
            score = self._compute_score(pat, mini_hu, mini_aspect, mini_contours, mini_mask)
            scores.append(score)
            results.append((pat, score))

        # 信頼度を判定
        sorted_scores = sorted(scores)
        confidence, confidence_pct = self._classify_confidence(sorted_scores)

        # スコア順にソート（低いほど一致）
        results.sort(key=lambda x: x[1])

        return [
            MatchResult(
                pattern_index=pat.pattern_index,
                image_path=pat.image_path,
                score=score,
                confidence=confidence if i == 0 else "low",
                confidence_pct=confidence_pct if i == 0 else 0.0,
            )
            for i, (pat, score) in enumerate(results)
        ]

    def _process_minimap(self, minimap: np.ndarray) -> tuple:
        """ミニマップから地形マスク・輪郭・Hu Moments・アスペクト比を抽出"""
        if minimap is None or minimap.size == 0:
            return None, [], np.zeros(7), 1.0

        # 既に二値画像（グレースケール）の場合はそのまま使用
        if len(minimap.shape) == 2:
            binary = minimap
        elif minimap.shape[2] == 1:
            binary = minimap[:, :, 0]
        else:
            gray = cv2.cvtColor(minimap, cv2.COLOR_BGR2GRAY)
            # 適応的二値化
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 21, -10,
            )
            # ノイズ除去
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        # 輪郭
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Hu Moments
        moments = cv2.moments(binary)
        hu = cv2.HuMoments(moments).flatten()

        # アスペクト比
        aspect = self._compute_aspect_ratio(contours)

        return binary, contours, hu, aspect

    def _compute_score(
        self,
        pattern: PatternData,
        mini_hu: np.ndarray,
        mini_aspect: float,
        mini_contours: list,
        mini_mask: np.ndarray,
    ) -> float:
        """パターンとミニマップの類似度スコアを計算（低い=一致）"""
        # 1. Hu Moments距離 (weight: 0.5)
        hu_dist = cv2.matchShapes(
            pattern.spawn_crop_mask, mini_mask,
            cv2.CONTOURS_MATCH_I2, 0,
        )

        # 2. 最大輪郭マッチ (weight: 0.3)
        contour_dist = 0.0
        if mini_contours and pattern.spawn_crop_contours:
            mini_largest = max(mini_contours, key=cv2.contourArea)
            pat_largest = max(pattern.spawn_crop_contours, key=cv2.contourArea)
            contour_dist = cv2.matchShapes(
                mini_largest, pat_largest,
                cv2.CONTOURS_MATCH_I2, 0,
            )

        # 3. アスペクト比差 (weight: 0.2)
        ar_diff = abs(pattern.local_aspect_ratio - mini_aspect)
        ar_score = ar_diff / max(pattern.local_aspect_ratio, mini_aspect, 0.01)

        return 0.5 * hu_dist + 0.3 * contour_dist + 0.2 * ar_score

    def _classify_confidence(self, sorted_scores: list[float]) -> tuple[str, float]:
        """スコア分布から信頼度とパーセントを判定"""
        if len(sorted_scores) < 2:
            return "low", 0.0
        best, second = sorted_scores[0], sorted_scores[1]
        if second == 0:
            return "low", 0.0
        gap = (second - best) / second
        pct = min(99.9, gap * 100)
        if gap > 0.5:
            return "high", pct
        elif gap > 0.2:
            return "medium", pct
        return "low", pct
