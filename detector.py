from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from paths import ROOT


@dataclass(frozen=True)
class DetectionResult:
    score: float
    position: tuple[int, int] | None
    scale: float | None
    color_score: float | None = None
    color_match: bool | None = None
    candidate: bool | None = None


@dataclass
class BurstMetrics:
    classification: str
    inner_edge: float
    ring_edge: float
    emblem_score: float = 0.0
    normal_tick_edge: float = 0.0
    gauge_level: float | None = None
    glow_score: float | None = None
    glow_classification: str = "UNKNOWN"
    hud_observable: bool = False
    cut_in_detected: bool = False


@dataclass(frozen=True)
class BurstGeometry:
    center: tuple[int, int]
    radius: float


@dataclass(frozen=True)
class MaskedTemplate:
    image: np.ndarray
    mask: np.ndarray


class TemplateBank:
    FILES = {
        "battle_start": "battle_start.png",
        "victory": "victory.png",
        "defeat": "defeat.png",
    }
    OPTIONAL_FILES = {"match_confirmed_2v2": "match_confirmed_2v2.png"}

    def __init__(self, directory: str | Path, min_component_area: int = 32):
        directory = Path(directory)
        for name, filename in self.FILES.items():
            setattr(self, name, self._load_rgba(directory / filename, min_component_area))
        for name, filename in self.OPTIONAL_FILES.items():
            path = directory / filename
            setattr(self, name, self._load_rgba(path, min_component_area) if path.exists() else None)
        self.go = self.battle_start

    @staticmethod
    def _load_rgba(path: Path, min_component_area: int) -> MaskedTemplate:
        encoded = np.fromfile(path, dtype=np.uint8) if path.exists() else None
        rgba = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED) if encoded is not None else None
        if rgba is None:
            raise FileNotFoundError(f"Cannot load template: {path}")
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ValueError(f"Template must be RGBA: {path}")

        alpha = rgba[:, :, 3]
        foreground = (alpha > 0).astype(np.uint8)
        count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground, 8)
        cleaned = np.zeros_like(foreground)
        for label in range(1, count):
            if stats[label, cv2.CC_STAT_AREA] >= min_component_area:
                cleaned[labels == label] = 1

        ys, xs = np.nonzero(cleaned)
        if not len(xs):
            raise ValueError(f"Template has no usable alpha pixels: {path}")
        x1, x2 = int(xs.min()), int(xs.max()) + 1
        y1, y2 = int(ys.min()), int(ys.max()) + 1
        image = cv2.cvtColor(rgba[y1:y2, x1:x2, :3], cv2.COLOR_BGR2GRAY)
        mask = (alpha[y1:y2, x1:x2] * cleaned[y1:y2, x1:x2]).copy()
        return MaskedTemplate(image=image, mask=mask)


class ScreenDetector:
    def __init__(self, config, templates: TemplateBank):
        self.cfg = config
        self.debug = bool(config.get("_debug", False))
        self.templates = templates
        template_dir = ROOT / "templates"
        self._awakening_emblems = []
        for filename in self.cfg["burst_emblem_templates"]:
            try:
                self._awakening_emblems.append(self._load_gray_template(template_dir / filename))
            except (FileNotFoundError, ValueError) as exc:
                print(f"Template warning: optional awakening template unavailable: {exc}")
        self._burst_samples: list[tuple[float, float, float]] = []
        self._burst_geometry: BurstGeometry | None = None
        self._burst_inner_ring_seen = False
        self._debug_ready_episode = 0
        self._debug_ready_active = False
        self._debug_ready_missing_samples = 0
        self._debug_ready_gauge_samples = 0
        self._debug_ready_missing_limit = int(self.cfg.get("debug_ready_missing_samples", 2))
        self._debug_ready_gauge_limit = int(self.cfg.get("debug_ready_gauge_samples", 10))

    @staticmethod
    def _load_gray_template(path):
        encoded = np.fromfile(path, dtype=np.uint8) if path.exists() else None
        image = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE) if encoded is not None else None
        if image is None:
            raise FileNotFoundError(f"Cannot load awakening emblem template: {path}")
        return image[4:-4, 4:-4]

    @property
    def burst_geometry(self):
        return self._burst_geometry

    def reset_burst_calibration(self):
        self._burst_samples.clear()
        self._burst_geometry = None
        self._burst_inner_ring_seen = False
        self._debug_ready_episode = 0
        self._debug_ready_active = False
        self._debug_ready_missing_samples = 0
        self._debug_ready_gauge_samples = 0

    def _begin_debug_ready_episode(self, mode):
        if not self.debug:
            return
        if mode == "ready" and not self._debug_ready_active:
            self._debug_ready_episode += 1
            self._debug_ready_missing_samples = 0
            self._debug_ready_gauge_samples = 0
            self._debug_ready_active = True
            print(f"READY gauge episode={self._debug_ready_episode} begin")
        elif mode != "ready":
            self._debug_ready_active = False

    def _debug_ready_gauge(self, image, roi, visible, gauge_level, lit_sectors, lit_pixels, reason="sample"):
        if not self.debug:
            return
        valid = gauge_level is not None
        if valid:
            if self._debug_ready_gauge_samples >= self._debug_ready_gauge_limit:
                return
            self._debug_ready_gauge_samples += 1
            sample = self._debug_ready_gauge_samples
            limit = self._debug_ready_gauge_limit
            kind = "gauge"
        else:
            if self._debug_ready_missing_samples >= self._debug_ready_missing_limit:
                return
            self._debug_ready_missing_samples += 1
            sample = self._debug_ready_missing_samples
            limit = self._debug_ready_missing_limit
            kind = "missing"
        x1, y1, x2, y2 = roi
        print(
            "READY gauge ROI "
            f"episode={self._debug_ready_episode} kind={kind} sample={sample}/{limit} roi=({x1},{y1})-({x2},{y2}) "
            f"hud_visible={visible} gauge={gauge_level if gauge_level is not None else 'n/a'} "
            f"lit_sectors={lit_sectors}/72 lit_pixels={lit_pixels} "
            f"raw=resize96,band=37:46,value_min={self.cfg['burst_gauge_value_min']} reason={reason}"
        )
        if image is not None:
            output = ROOT / "debug_ready_gauge"
            output.mkdir(exist_ok=True)
            path = output / f"ready_{self._debug_ready_episode:02d}_{kind}_{sample:02d}.png"
            cv2.imwrite(str(path), image)
            print(f"READY gauge ROI saved={path}")

    def _burst_circle_candidates(self, frame):
        roi, (offset_x, offset_y) = self._scaled_roi(frame, self.cfg["burst_search_roi"])
        if roi.size == 0:
            return []

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 1.0)
        h, w = frame.shape[:2]
        scale = self._frame_scale(frame)
        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.0,
            # Keep concentric responses so the outer HUD rim can be selected
            # instead of losing it to the stronger inner tick ring.
            minDist=max(2, int(round(4 * scale))),
            param1=100,
            param2=self.cfg["burst_calibration_hough_threshold"],
            minRadius=max(4, int(round(self.cfg["burst_calibration_radius_min"] * scale))),
            maxRadius=max(5, int(round(self.cfg["burst_calibration_radius_max"] * scale))),
        )
        if circles is None:
            return []
        return [
            (float(offset_x + x), float(offset_y + y), float(radius))
            for x, y, radius in circles[0]
        ]

    def _update_burst_calibration(self, frame):
        candidates = self._burst_circle_candidates(frame)
        if not candidates:
            return

        scale = self._frame_scale(frame)
        reference_radius = self.cfg["burst_calibration_reference_radius"] * scale
        center_tolerance = self.cfg["burst_calibration_center_tolerance"] * scale
        radius_tolerance = self.cfg["burst_calibration_radius_tolerance"] * scale

        if self._burst_samples:
            recent = np.asarray(self._burst_samples[-self.cfg["burst_calibration_window_frames"]:])
            reference = np.median(recent, axis=0)
            candidates = [
                circle for circle in candidates
                if np.hypot(circle[0] - reference[0], circle[1] - reference[1])
                <= center_tolerance
            ]
            if not candidates:
                return
            center_candidate = candidates[0]
        else:
            # Hough returns the strongest circle first; use it to anchor the
            # HUD center, then inspect concentric candidates for its outer rim.
            center_candidate = candidates[0]

        concentric = [
            circle for circle in candidates
            if np.hypot(circle[0] - center_candidate[0], circle[1] - center_candidate[1])
            <= center_tolerance
        ]
        if center_candidate[2] < reference_radius - 2.0:
            self._burst_inner_ring_seen = True
        candidate = (
            center_candidate[0],
            center_candidate[1],
            max(circle[2] for circle in concentric)
            if self._burst_inner_ring_seen else center_candidate[2],
        )

        self._burst_samples.append(candidate)
        window_size = self.cfg["burst_calibration_window_frames"]
        if len(self._burst_samples) > window_size:
            del self._burst_samples[:-window_size]
        # Do not finalize from the first few frames: Hough can initially lock
        # onto the inner tick ring while the HUD is animating into place.
        if len(self._burst_samples) < window_size:
            return

        samples = np.asarray(self._burst_samples)
        center = np.median(samples[:, :2], axis=0)
        center_inliers = samples[
            np.hypot(samples[:, 0] - center[0], samples[:, 1] - center[1])
            <= center_tolerance
        ]
        if len(center_inliers) < self.cfg["burst_calibration_confirm_frames"]:
            return

        # A radius cluster clearly inside the reference HUD size is the tick
        # ring, not the rim. Keep observing until the outer circle dominates.
        if np.median(center_inliers[:, 2]) < reference_radius - 1.0:
            return

        # Hough often alternates between the inner and outer edges of the same
        # HUD ring.  The outer edge is the HUD radius, so estimate its cluster
        # from the upper quartile and reject both inner-edge and large outliers.
        separated_outer = center_inliers[
            center_inliers[:, 2] >= reference_radius + 4.0
        ]
        if len(separated_outer) >= self.cfg["burst_calibration_confirm_frames"]:
            outer_inliers = separated_outer
        elif self._burst_inner_ring_seen:
            return
        elif len(separated_outer):
            return
        else:
            radius_reference = np.percentile(center_inliers[:, 2], 75)
            outer_inliers = center_inliers[
                np.abs(center_inliers[:, 2] - radius_reference)
                <= radius_tolerance
            ]
        if len(outer_inliers) < max(4, self.cfg["burst_calibration_confirm_frames"] // 2):
            return
        stable_center = np.median(outer_inliers[:, :2], axis=0)
        stable_radius = float(np.median(outer_inliers[:, 2]))
        self._burst_geometry = BurstGeometry(
            center=(int(round(stable_center[0])), int(round(stable_center[1]))),
            radius=stable_radius,
        )

    def _scale_point(self, x, y, frame):
        h, w = frame.shape[:2]
        sx = w / self.cfg["reference_width"]
        sy = h / self.cfg["reference_height"]
        return int(round(x * sx)), int(round(y * sy)), sx, sy

    def _frame_scale(self, frame):
        """Uniform UI scale relative to the 1280x720 reference canvas."""
        h, w = frame.shape[:2]
        return ((w / self.cfg["reference_width"]) * (h / self.cfg["reference_height"])) ** 0.5

    def _scaled_roi(self, frame, roi):
        x1, y1, x2, y2 = roi
        h, w = frame.shape[:2]
        sx = w / self.cfg["reference_width"]
        sy = h / self.cfg["reference_height"]
        left = max(0, int(round(x1 * sx)))
        top = max(0, int(round(y1 * sy)))
        right = min(w, int(round(x2 * sx)))
        bottom = min(h, int(round(y2 * sy)))
        return frame[top:bottom, left:right], (left, top)

    def _detect(self, frame, template: MaskedTemplate, roi_key: str, scales_key="template_scales") -> DetectionResult:
        roi, (offset_x, offset_y) = self._scaled_roi(frame, self.cfg[roi_key])
        if roi.size == 0:
            return DetectionResult(0.0, None, None)
        roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        best = DetectionResult(0.0, None, None)
        frame_scale = self._frame_scale(frame)
        for reference_scale in self.cfg[scales_key]:
            scale = reference_scale * frame_scale
            width = int(round(template.image.shape[1] * scale))
            height = int(round(template.image.shape[0] * scale))
            if width < 2 or height < 2 or width > roi.shape[1] or height > roi.shape[0]:
                continue

            interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            image = cv2.resize(template.image, (width, height), interpolation=interpolation)
            mask = cv2.resize(template.mask, (width, height), interpolation=cv2.INTER_AREA)
            mask = np.where(mask >= self.cfg["template_alpha_threshold"], 255, 0).astype(np.uint8)
            if cv2.countNonZero(mask) == 0:
                continue

            scores = cv2.matchTemplate(roi, image, cv2.TM_CCOEFF_NORMED, mask=mask)
            scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)
            _, score, _, location = cv2.minMaxLoc(scores)
            if score > best.score:
                best = DetectionResult(float(score), (offset_x + location[0], offset_y + location[1]), float(scale))
        return best

    def _with_color_check(self, frame, result, template, color_name, score_threshold):
        if result.position is None or result.scale is None:
            return DetectionResult(result.score, result.position, result.scale, 0.0, False, False)

        width = int(round(template.image.shape[1] * result.scale))
        height = int(round(template.image.shape[0] * result.scale))
        x, y = result.position
        candidate_roi = frame[y:y + height, x:x + width]
        if candidate_roi.shape[:2] != (height, width):
            return DetectionResult(result.score, result.position, result.scale, 0.0, False, False)

        alpha = cv2.resize(template.mask, (width, height), interpolation=cv2.INTER_AREA)
        alpha_mask = alpha >= self.cfg["template_alpha_threshold"]
        hsv = cv2.cvtColor(candidate_roi, cv2.COLOR_BGR2HSV)
        saturated = alpha_mask & (hsv[:, :, 1] >= self.cfg["result_color_saturation_min"])
        saturated_count = int(np.count_nonzero(saturated))
        h, w = frame.shape[:2]
        min_color_pixels = self.cfg["result_color_min_pixels"] * (
            w / self.cfg["reference_width"]
        ) * (h / self.cfg["reference_height"])
        if saturated_count < min_color_pixels:
            color_score = 0.0
        else:
            hue_match = np.zeros_like(saturated)
            for low, high in self.cfg[f"{color_name}_hue_ranges"]:
                hue_match |= (hsv[:, :, 0] >= low) & (hsv[:, :, 0] <= high)
            color_score = float(np.count_nonzero(saturated & hue_match) / saturated_count)

        color_match = color_score >= self.cfg[f"{color_name}_color_ratio_min"]
        expected_x, expected_y, sx, sy = self._scale_point(*self.cfg["result_position"], frame)
        position_match = (
            result.position is not None
            and abs(result.position[0] - expected_x) <= self.cfg["result_position_tolerance_x"] * sx
            and abs(result.position[1] - expected_y) <= self.cfg["result_position_tolerance_y"] * sy
        )
        reference_scale = result.scale / self._frame_scale(frame)
        scale_epsilon = 1e-9
        scale_match = (
            self.cfg["result_scale_min"] - scale_epsilon
            <= reference_scale
            <= self.cfg["result_scale_max"] + scale_epsilon
        )
        candidate = (
            result.score >= self.cfg["result_template_score_min"]
            and result.score >= score_threshold
            and scale_match
            and position_match
            and color_match
        )
        if getattr(self, "debug", False) and result.position is not None and result.score >= score_threshold:
            reasons = []
            if result.score < self.cfg["result_template_score_min"]:
                reasons.append("template_score")
            if not scale_match:
                reasons.append("scale")
            if not position_match:
                reasons.append("anchor")
            if not color_match:
                reasons.append("color")
            print(
                "RESULT candidate "
                f"type={color_name} score={result.score:.3f} "
                f"raw_scale={result.scale:.6f} reference_scale={reference_scale:.6f} "
                f"anchor={position_match} color={color_match} "
                f"accept={candidate} reason={','.join(reasons) if reasons else 'accepted'}"
            )
        return DetectionResult(
            result.score,
            result.position,
            result.scale,
            color_score,
            color_match,
            candidate,
        )

    def detect_battle_start(self, frame):
        return self._detect(frame, self.templates.battle_start, "battle_start_roi")

    def detect_victory(self, frame):
        result = self._detect(frame, self.templates.victory, "result_ui_roi", "result_template_scales")
        return self._with_color_check(
            frame, result, self.templates.victory, "victory", self.cfg["victory_threshold"]
        )

    def detect_defeat(self, frame):
        result = self._detect(frame, self.templates.defeat, "result_ui_roi", "result_template_scales")
        return self._with_color_check(
            frame, result, self.templates.defeat, "defeat", self.cfg["defeat_threshold"]
        )

    def detect_match_confirmed_2v2(self, frame):
        if self.templates.match_confirmed_2v2 is None:
            return DetectionResult(0.0, None, None)
        return self._detect(frame, self.templates.match_confirmed_2v2, "match_confirmed_2v2_roi")

    # Keep the current main.py/state_machine.py interface unchanged.
    def go_score(self, frame):
        return self.detect_battle_start(frame).score

    def victory_score(self, frame):
        result = self.detect_victory(frame)
        return result.score if result.candidate else 0.0

    def defeat_score(self, frame):
        result = self.detect_defeat(frame)
        return result.score if result.candidate else 0.0

    def burst_metrics(self, frame, calibrate=True, mode=None):
        self._begin_debug_ready_episode(mode)
        if self._burst_geometry is None and calibrate:
            self._update_burst_calibration(frame)
        if self._burst_geometry is None:
            if mode == "ready":
                self._debug_ready_gauge(frame, (0, 0, 0, 0), False, None, 0, 0, "geometry_unavailable")
                if self.debug:
                    print("AWAKENING_START cutin detected=False score=n/a reason=geometry_unavailable")
            elif self.debug and mode == "awakening":
                print("AWAKENING_END icon_observable=False reason=geometry_unavailable")
            return BurstMetrics("unknown", 0.0, 0.0)

        cx, cy = self._burst_geometry.center
        # Include the space immediately outside the HUD rim: this is where an
        # active Awakening's colour-independent glow appears.
        half = int(round(self._burst_geometry.radius * 1.25))
        if cy - half < 0 or cx - half < 0 or cy + half > frame.shape[0] or cx + half > frame.shape[1]:
            if mode == "ready":
                self._debug_ready_gauge(frame, (cx - half, cy - half, cx + half, cy + half), False, None, 0, 0, "roi_out_of_bounds")
                if self.debug:
                    print("AWAKENING_START cutin detected=False score=n/a reason=roi_out_of_bounds")
            elif self.debug and mode == "awakening":
                print("AWAKENING_END icon_observable=False reason=roi_out_of_bounds")
            return BurstMetrics("unknown", 0.0, 0.0)

        roi = (cx - half, cy - half, cx + half, cy + half)
        hud = frame[roi[1]:roi[3], roi[0]:roi[2]]
        hud = cv2.resize(hud, (96, 96), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(hud, cv2.COLOR_BGR2GRAY)
        # The cut-in emblem templates were authored against the tight HUD
        # crop.  Keep that crop independent from the wider outer-glow crop.
        icon_half = int(round(self._burst_geometry.radius * 1.08))
        icon = frame[cy - icon_half:cy + icon_half, cx - icon_half:cx + icon_half]
        icon = cv2.resize(icon, (96, 96), interpolation=cv2.INTER_AREA)
        icon_gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)
        emblem_roi = icon_gray[19:77, 19:77]
        emblem_score = max(
            (float(cv2.matchTemplate(emblem_roi, template, cv2.TM_CCOEFF_NORMED).max())
             for template in self._awakening_emblems),
            default=0.0,
        )
        cut_in_detected = (
            mode != "awakening"
            and emblem_score >= self.cfg["burst_emblem_score_min"]
        )
        if self.debug and mode == "ready":
            print(
                "AWAKENING_START cutin "
                f"detected={cut_in_detected} score={emblem_score:.3f} "
                f"threshold={self.cfg['burst_emblem_score_min']:.3f} "
                f"geometry=center({cx},{cy}) radius={self._burst_geometry.radius:.1f}"
            )
        edges = cv2.Canny(gray, 80, 160) > 0
        hsv = cv2.cvtColor(hud, cv2.COLOR_BGR2HSV)
        yy, xx = np.indices((96, 96))
        radius = np.sqrt((xx - 47.5) ** 2 + (yy - 47.5) ** 2)
        sectors = 72
        angles = (
            (np.arctan2(yy - 47.5, xx - 47.5) + np.pi)
            * sectors / (2 * np.pi)
        ).astype(np.int32) % sectors

        def angular_edge_coverage(inner, outer):
            band = (radius >= inner) & (radius < outer)
            return float(sum(
                np.any(edges[band & (angles == sector)])
                for sector in range(sectors)
            ) / sectors)

        tick_edge = angular_edge_coverage(25, 35)
        inner_icon_edge = angular_edge_coverage(8, 22)
        outer_edge = angular_edge_coverage(38, 48)
        circle_present = outer_edge >= self.cfg["burst_normal_outer_edge_min"]
        if cut_in_detected:
            cls = "active"
        elif circle_present and tick_edge >= self.cfg["burst_normal_tick_edge_min"]:
            cls = "normal"
        else:
            cls = "unknown"

        # The bright outer progress arc is proportional to the player's burst
        # gauge.  Count lit angular sectors rather than pixels so effects over
        # a small part of the HUD do not materially alter the measurement.
        gauge_band = (radius >= 37) & (radius < 46)
        lit = gauge_band & (hsv[:, :, 2] >= self.cfg["burst_gauge_value_min"])
        lit_sectors = int(sum(np.any(lit & (angles == sector)) for sector in range(sectors)))
        # The tick ring remains after the outer effect fades, but it alone can
        # be mimicked by scene edges. Require stable central icon detail too;
        # neither signal depends on outer-glow strength.
        hud_observable = (
            tick_edge >= self.cfg["burst_normal_tick_edge_min"]
            and inner_icon_edge >= self.cfg["burst_hud_inner_icon_edge_min"]
        )
        # During an Awakening, partial HUD/background edges are not a valid
        # observation. They must remain UNKNOWN so they cannot end it.
        if mode == "awakening" and not hud_observable:
            cls = "unknown"
        gauge_level = (
            float(lit_sectors / sectors)
            if cls == "normal" or (mode == "awakening" and hud_observable) else None
        )
        # Glow is measured from brightness/chroma energy in the annulus just
        # outside the rim, relative to its immediate exterior.  It deliberately
        # does not use hue, because each Awakening type has a different colour.
        glow_band = (radius >= 40) & (radius < 47)
        background_band = (radius >= 49) & (radius < 58)
        energy = hsv[:, :, 2].astype(np.float32) * (0.35 + 0.65 * hsv[:, :, 1] / 255.0)
        glow_energy = float(np.mean(energy[glow_band]))
        background_energy = float(np.mean(energy[background_band]))
        glow_score = max(0.0, (glow_energy - background_energy) / 255.0)
        if self.debug and mode == "awakening":
            print(
                "AWAKENING_END icon_observable "
                f"value={hud_observable} source=inner_tick_ring circle_present={circle_present} "
                f"tick_edge={tick_edge:.3f} tick_min={self.cfg['burst_normal_tick_edge_min']:.3f} "
                f"inner_icon_edge={inner_icon_edge:.3f} inner_icon_min={self.cfg['burst_hud_inner_icon_edge_min']:.3f} "
                f"outer_edge={outer_edge:.3f} outer_min={self.cfg['burst_normal_outer_edge_min']:.3f} "
                f"geometry=center({cx},{cy}) radius={self._burst_geometry.radius:.1f}"
            )
        if not hud_observable:
            glow_classification = "UNKNOWN"
        elif glow_score >= self.cfg.get("awakening_glow_present_score_min", 0.12):
            glow_classification = "PRESENT"
        elif glow_score <= self.cfg.get("awakening_glow_absent_score_max", 0.05):
            glow_classification = "ABSENT"
        else:
            # Ambiguous samples are not evidence that the glow disappeared.
            glow_classification = "UNKNOWN"
        if self.debug and mode == "awakening":
            print(
                "AWAKENING glow "
                f"score={glow_score:.3f} glow_energy={glow_energy:.1f} "
                f"background_energy={background_energy:.1f} hud_observable={hud_observable} "
                f"classification={glow_classification}"
            )
        if mode == "ready":
            self._debug_ready_gauge(
                hud, roi, cls == "normal", gauge_level, lit_sectors,
                int(np.count_nonzero(lit)), "normal" if cls == "normal" else "hud_classification_failed",
            )
        return BurstMetrics(
            cls,
            tick_edge,
            outer_edge,
            emblem_score=emblem_score,
            normal_tick_edge=tick_edge,
            gauge_level=gauge_level,
            glow_score=glow_score,
            glow_classification=glow_classification,
            hud_observable=hud_observable,
            cut_in_detected=cut_in_detected,
        )
