"""Kinematic wrap target for the square flasher fold — the sheet rotates
around the central hub square and folds down into a CUBE.

Every flat vertex is described in "square-polar" coordinates about the hub
center: taxicab radius rho = max(|x|, |y|) and square-angle psi in [0, 4)
(perimeter position on the concentric square through the point, one unit per
side, CCW from the (+, -) corner). The fold target interpolates each vertex
between the flat sheet and a folded cube:

- the hub square stays flat at z = 0 as the cube's TOP face — everything
  else rotates and folds around it;
- beyond the hub, each point wraps onto the cube's square walls, winding
  around the hub by rho/half turns (paper-length preserving, so the excess
  paper fits onto the small footprint instead of fighting the solver);
- z descends monotonically from the hub (top) to the sheet edge (open
  bottom), so the walls build a cube whose height ≈ its width.

The winding target is not EXACTLY length-preserving (square arc length vs
straight chords once a ring winds past a corner), so the PBD solver still
reconciles a residual — the folded walls are layered/rough rather than
crisp flat panels, which is inherent to wrapping this much paper.
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


# Folded-cube shape targets. The hub square becomes the cube's TOP face; the
# rest of the sheet spirals DOWN and AROUND it to build the four vertical
# walls, leaving the underside open. OUTER_HALF is the folded footprint's
# half-width — the wrapped walls grow from the hub out to this fixed size
# regardless of grid, so the cube is the same proportions at every
# resolution, and it is large enough that the wound paper fits without
# bulging out of plane.
OUTER_HALF = 1.0


def compute_target_positions(
    flat: np.ndarray, params: FlasherParams, foldness: float
) -> np.ndarray:
    """(V, 2) flat positions → (V, 3) target positions at `foldness`.

    At foldness 1 the target is a CUBE: the central hub square is the top
    face at z = 0, and every point beyond the hub is wrapped onto the four
    walls of a HUB-sized square column, winding around the hub (so the whole
    fold rotates about the central square) while descending to the open
    bottom. The winding rate is set by paper-length conservation — a ring of
    circumference 8·rho wound onto a wall of circumference 8·half must wind
    rho/half times — so the paper actually fits onto the small footprint
    instead of the length constraint fighting the collapse.
    """
    t = min(1.0, max(0.0, foldness))
    centered = flat - np.array(HUB_CENTER)
    rho, psi = square_polar(centered)
    beyond_hub = np.maximum(rho - HUB_HALF, 0.0)  # hub itself never moves

    reach = float(params.grid_divisions) / 2.0 - HUB_HALF
    reach = reach if reach > 1e-9 else 1.0
    frac = np.clip(beyond_hub / reach, 0.0, 1.0)  # 0 at hub, 1 at sheet edge

    # Horizontal: wrap each point onto the folded footprint (hub at the top of
    # the wall, growing to OUTER_HALF at the sheet edge), winding around the
    # hub the length-preserving number of turns.
    half_folded = HUB_HALF + (OUTER_HALF - HUB_HALF) * frac
    half = rho + (half_folded - rho) * t
    inside = rho <= HUB_HALF
    half[inside] = rho[inside]
    safe_half = np.where(half < 1e-9, 1.0, half)
    wrap_ratio = np.where(rho < 1e-9, 1.0, rho / safe_half)
    psi_folded = psi * wrap_ratio  # rho/half turns → paper length preserved
    psi_t = psi + (psi_folded - psi) * t

    x, y = point_on_square(psi_t, half)

    # Vertical: hub square stays on top (z = 0); paper descends monotonically
    # to the open bottom so the walls build a cube (height ≈ folded width),
    # instead of the old accordion that stayed squat.
    cube_height = 2.0 * OUTER_HALF
    z = -t * cube_height * frac

    out = np.empty((len(flat), 3))
    out[:, 0] = x + HUB_CENTER[0]
    out[:, 1] = y + HUB_CENTER[1]
    out[:, 2] = z
    return out
