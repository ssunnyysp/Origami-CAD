"""Kinematic wrap target for the square flasher fold ("natural folding" —
rotation of a polygon on a sheet).

Every flat vertex is described in "square-polar" coordinates about the hub
center: taxicab radius rho = max(|x|, |y|) and square-angle psi in [0, 4)
(perimeter position on the concentric square through the point, one unit per
side, CCW from the (+, -) corner). The fold target interpolates each vertex
between the flat sheet and a wrapped state around the hub:

- square-angle advances by wrap_per_ring per ring (the coil),
- taxicab radius collapses to hub + layer_gap_ratio per ring (the layers),
- z ACCORDIONS: each one-unit band between rings rises from the hub plane
  (valley ring) to the wall's ridge height (mountain ring) and back, so the
  whole sheet folds into a compact block one band tall, wrapped around the
  flat hub — whose colored top face never moves.

Like the previous engines, this target is NOT length-preserving — it is only
the attractor the PBD solver pulls toward while enforcing that every mesh
edge keeps its flat (paper) length. The length mismatch is exactly what
forces the sheet to pleat at the crease rings, the way a real flasher's
excess perimeter folds into its pleats.
"""

from __future__ import annotations

import numpy as np

from .generator import HUB_CENTER, HUB_HALF, FlasherParams


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

    psi_folded = psi + t * params.wrap_per_ring * beyond_hub
    half_folded = HUB_HALF + params.layer_gap_ratio * beyond_hub
    half = rho + (half_folded - rho) * t
    # Keep the hub interior at its true radius (half_folded would inflate it).
    inside = rho <= HUB_HALF
    half[inside] = rho[inside]

    x, y = point_on_square(psi_folded, half)

    # Vertical accordion: distance-from-hub d rises 0→1 across each band and
    # the wave direction flips per band, putting even (valley) rings at the
    # hub plane and odd (mountain) rings at the ridge height.
    band = np.floor(beyond_hub)
    frac = beyond_hub - band
    zig = np.where(band % 2 == 0, frac, 1.0 - frac)
    z = t * params.height_ratio * zig

    out = np.empty((len(flat), 3))
    out[:, 0] = x + HUB_CENTER[0]
    out[:, 1] = y + HUB_CENTER[1]
    out[:, 2] = z
    return out
