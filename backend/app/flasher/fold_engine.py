"""Kinematic wrap target for the square flasher fold ("natural folding" —
rotation of a polygon on a sheet).

Every flat vertex is described in "square-polar" coordinates about the hub
center: taxicab radius rho = max(|x|, |y|) and square-angle psi in [0, 4)
(perimeter position on the concentric square through the point, one unit per
side, CCW from the (+, -) corner). The fold target interpolates each vertex
between the flat sheet and a wrapped state around the hub:

- taxicab radius collapses to hub + layer_gap_ratio per ring (the layers),
- square-angle is rescaled by (rho / half) — the ratio of the point's
  original perimeter to the shrunken target perimeter — so a ring's
  circumference maps onto its (smaller) wrapped layer WITHOUT stretching or
  compressing paper tangentially. This is what actually produces the coil:
  a ring wrapped onto a much smaller square necessarily winds around it
  several times to use up its original length, exactly the way real excess
  paper spirals when wrapped onto a narrower core. (An earlier version used
  a hand-tuned constant rotation per ring instead of this ratio, which
  under- or over-wrapped depending on grid size and fought the solver's
  length constraint hard enough to crumple visibly by full foldness.)
- z ACCORDIONS: each one-unit band between rings rises from the hub plane
  (valley ring) to the wall's ridge height (mountain ring) and back. Which
  way a band rises is read directly from `generator.ring_gender` — the same
  function the crease pattern uses to color that ring — so the 3D fold can
  never silently disagree with the drawn mountain/valley lines.

This target is still not EXACTLY length-preserving (arc length along a
square isn't identical to straight-line chord length once a ring winds past
a corner), so the PBD solver still has real work reconciling it — but the
mismatch is now a residual correction rather than the dominant signal.
"""

from __future__ import annotations

import numpy as np

from .generator import HUB_CENTER, HUB_HALF, FlasherParams, ring_gender


def square_polar(flat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(V, 2) positions relative to the hub center → (rho, psi).

    psi is 0 at the (+h, -h) corner, CCW."""
    x, y = flat[:, 0], flat[:, 1]
    rho = np.maximum(np.abs(x), np.abs(y))
    safe_rho = np.where(rho < 1e-12, 1.0, rho)
    xn, yn = x / safe_rho, y / safe_rho

    psi = np.zeros(len(flat))
    right = xn >= np.abs(yn)
    top = yn >= np.abs(xn)
    left = xn <= -np.abs(yn)
    bottom = ~(right | top | left)
    psi[right] = (yn[right] + 1) / 2
    psi[top] = 1 + (1 - xn[top]) / 2
    psi[left] = 2 + (1 - yn[left]) / 2
    psi[bottom] = 3 + (xn[bottom] + 1) / 2
    psi[rho < 1e-12] = 0.0
    return rho, psi


def point_on_square(psi: np.ndarray, half: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Perimeter point at square-angle psi on the square of half-size `half`."""
    psi = np.mod(psi, 4.0)
    side = np.floor(psi).astype(int)
    f = psi - side

    x = np.empty_like(psi)
    y = np.empty_like(psi)
    s0, s1, s2, s3 = side == 0, side == 1, side == 2, side == 3
    x[s0], y[s0] = half[s0], -half[s0] + 2 * half[s0] * f[s0]
    x[s1], y[s1] = half[s1] - 2 * half[s1] * f[s1], half[s1]
    x[s2], y[s2] = -half[s2], half[s2] - 2 * half[s2] * f[s2]
    x[s3], y[s3] = -half[s3] + 2 * half[s3] * f[s3], -half[s3]
    return x, y


def compute_target_positions(
    flat: np.ndarray, params: FlasherParams, foldness: float
) -> np.ndarray:
    """(V, 2) flat positions → (V, 3) target positions at `foldness`."""
    t = min(1.0, max(0.0, foldness))
    centered = flat - np.array(HUB_CENTER)
    rho, psi = square_polar(centered)
    beyond_hub = np.maximum(rho - HUB_HALF, 0.0)  # hub itself never moves

    half_folded = HUB_HALF + params.layer_gap_ratio * beyond_hub
    half = rho + (half_folded - rho) * t
    # Keep the hub interior at its true radius (half_folded would inflate it).
    inside = rho <= HUB_HALF
    half[inside] = rho[inside]

    safe_half = np.where(half < 1e-9, 1.0, half)
    wrap_ratio = np.where(rho < 1e-9, 1.0, rho / safe_half)
    psi_folded = psi * wrap_ratio

    x, y = point_on_square(psi_folded, half)

    # Vertical accordion: within the band for ring `ring_index`, height rises
    # 0→1 across the band if that ring is a mountain (its far edge, shared
    # with the next ring, is the ridge) or falls 1→0 if it's a valley (its
    # far edge is the trough) — read straight from ring_gender, the same
    # source the crease-pattern generator uses.
    band = np.floor(beyond_hub)
    frac = beyond_hub - band
    ring_index = (band + 1).astype(int)
    max_ring = int(ring_index.max()) if len(ring_index) else 0
    is_mountain = np.array([ring_gender(k) == "mountain" for k in range(max_ring + 1)])
    mountain_here = is_mountain[ring_index]
    zig = np.where(mountain_here, frac, 1.0 - frac)
    # Negative: the hub is pinned at z=0 and must end up on TOP of the folded
    # block (colored side up, as if resting on a table), so everything else
    # hangs DOWN from it, leaving the underside open — there is no separate
    # bottom panel in the mesh at all, just the coiled walls.
    z = -t * params.height_ratio * zig

    out = np.empty((len(flat), 3))
    out[:, 0] = x + HUB_CENTER[0]
    out[:, 1] = y + HUB_CENTER[1]
    out[:, 2] = z
    return out
