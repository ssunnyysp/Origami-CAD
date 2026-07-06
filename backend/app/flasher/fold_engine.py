"""Kinematic wrap target for the flasher fold.

Port of the original frontend foldEngine.ts. Each vertex's goal position is
interpolated in CYLINDRICAL coordinates between the flat pattern (z = 0) and
a wrapped state in which each successive ring winds `wrap_angle` further
around the hub, sits at a slightly larger layer radius (imitating accumulated
layer thickness), and rises in z. This target is NOT length-preserving — it
is only the attractor that FlasherFoldSolver pulls toward while enforcing
that every edge keeps its flat (paper) length.
"""

from __future__ import annotations

import math

from .generator import FlasherParams

LAYER_GAP_RATIO = 0.06  # fraction of central_radius of layer-radius growth per wrapped ring
HEIGHT_RATIO = 0.8  # fraction of the flat radial band width converted to stowed height


def compute_target_positions(params: FlasherParams, foldness: float) -> list[float]:
    """Returns xyz triples indexed by vertex id (id = ring * sides + sector)."""
    n = params.sides
    t = min(1.0, max(0.0, foldness))
    layer_gap = params.central_radius * LAYER_GAP_RATIO

    out = [0.0] * ((params.rings + 1) * n * 3)
    for j in range(params.rings + 1):
        flat_radius = params.central_radius * params.radius_ratio**j
        folded_radius = params.central_radius + j * layer_gap
        # Stowed height grows with the flat material consumed so far, so wider
        # rings produce a taller stowed cylinder (material conservation-ish).
        folded_z = HEIGHT_RATIO * (flat_radius - params.central_radius)

        radius = flat_radius + (folded_radius - flat_radius) * t
        z = folded_z * t

        for i in range(n):
            base_angle = 2 * math.pi * i / n
            flat_angle = base_angle + j * params.spiral_angle
            folded_angle = base_angle + j * params.wrap_angle
            angle = flat_angle + (folded_angle - flat_angle) * t

            k = (j * n + i) * 3
            out[k] = radius * math.cos(angle)
            out[k + 1] = radius * math.sin(angle)
            out[k + 2] = z
    return out
