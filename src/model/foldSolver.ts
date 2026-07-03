import type { CreasePattern } from "./types";
import type { FlasherParams } from "./flasherGenerator";
import { computeTargetPositions } from "./foldEngine";

// Paper-like folding via position-based dynamics: paper can hinge at creases
// but never stretch, so every triangle edge is a hard length constraint at
// its flat-pattern length. Each solve step pulls free vertices a fraction of
// the way toward the kinematic wrap target, then repeatedly projects all
// edge-length constraints (Gauss-Seidel). The sheet therefore coils around
// the hub the only way an inextensible surface can — by folding into itself
// and buckling at creases — instead of stretching like sheet metal.
//
// Hub (ring 0) vertices are pinned: their target is the flat hub at every
// foldness, and pinning anchors the wrap.
const TARGET_PULL = 0.3; // fraction of the gap to the kinematic target applied per substep
const PROJECT_ITERATIONS = 12; // Gauss-Seidel passes over all edges per substep
const MAX_FOLDNESS_SUBSTEP = 0.02; // large slider jumps are subdivided for stability
const MAX_SUBSTEPS = 80;

interface LengthConstraint {
  a: number; // vertex id
  b: number; // vertex id
  rest: number;
}

export class FlasherFoldSolver {
  private readonly params: FlasherParams;
  private readonly pinnedCount: number; // ring-0 vertex ids are [0, pinnedCount)
  private readonly constraints: LengthConstraint[];
  private readonly pos: Float64Array;
  private lastFoldness = 0;

  constructor(pattern: CreasePattern, params: FlasherParams) {
    this.params = params;
    this.pinnedCount = params.sides;
    this.pos = computeTargetPositions(params, 0);

    // Constraints come from the RENDERED triangles (faces fan-triangulated
    // from their first vertex), so the constrained surface is exactly the
    // surface drawn on screen — including the central polygon's fan
    // diagonals, which aren't pattern edges.
    const seen = new Set<string>();
    this.constraints = [];
    const addConstraint = (a: number, b: number) => {
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      if (seen.has(key)) return;
      seen.add(key);
      const ka = a * 3;
      const kb = b * 3;
      this.constraints.push({
        a,
        b,
        rest: Math.hypot(
          this.pos[ka] - this.pos[kb],
          this.pos[ka + 1] - this.pos[kb + 1],
          this.pos[ka + 2] - this.pos[kb + 2],
        ),
      });
    };
    for (const face of pattern.faces) {
      const ids = face.vertexIds;
      for (let i = 1; i < ids.length - 1; i++) {
        addConstraint(ids[0], ids[i]);
        addConstraint(ids[i], ids[i + 1]);
        addConstraint(ids[0], ids[i + 1]);
      }
    }
  }

  // Advances the solver from its previous foldness to `foldness` and returns
  // the vertex positions (xyz triples indexed by vertex id). Warm-started:
  // consecutive calls with nearby foldness values are cheap.
  positionsAt(foldness: number): Float32Array {
    const t = Math.min(1, Math.max(0, foldness));

    if (t === 0) {
      this.pos.set(computeTargetPositions(this.params, 0));
      this.lastFoldness = 0;
      return Float32Array.from(this.pos);
    }

    const substeps = Math.min(
      MAX_SUBSTEPS,
      Math.max(1, Math.ceil(Math.abs(t - this.lastFoldness) / MAX_FOLDNESS_SUBSTEP)),
    );
    for (let s = 1; s <= substeps; s++) {
      const stepT = this.lastFoldness + ((t - this.lastFoldness) * s) / substeps;
      const target = computeTargetPositions(this.params, stepT);

      for (let v = 0; v < this.pos.length / 3; v++) {
        const k = v * 3;
        const pull = v < this.pinnedCount ? 1 : TARGET_PULL;
        this.pos[k] += (target[k] - this.pos[k]) * pull;
        this.pos[k + 1] += (target[k + 1] - this.pos[k + 1]) * pull;
        this.pos[k + 2] += (target[k + 2] - this.pos[k + 2]) * pull;
      }

      for (let iter = 0; iter < PROJECT_ITERATIONS; iter++) {
        for (const { a, b, rest } of this.constraints) {
          const ka = a * 3;
          const kb = b * 3;
          const dx = this.pos[kb] - this.pos[ka];
          const dy = this.pos[kb + 1] - this.pos[ka + 1];
          const dz = this.pos[kb + 2] - this.pos[ka + 2];
          const dist = Math.hypot(dx, dy, dz);
          if (dist < 1e-9) continue;

          const wa = a < this.pinnedCount ? 0 : 1;
          const wb = b < this.pinnedCount ? 0 : 1;
          const wSum = wa + wb;
          if (wSum === 0) continue;

          const scale = ((dist - rest) / dist / wSum) * 1.0;
          this.pos[ka] += dx * scale * wa;
          this.pos[ka + 1] += dy * scale * wa;
          this.pos[ka + 2] += dz * scale * wa;
          this.pos[kb] -= dx * scale * wb;
          this.pos[kb + 1] -= dy * scale * wb;
          this.pos[kb + 2] -= dz * scale * wb;
        }
      }
    }
    this.lastFoldness = t;
    return Float32Array.from(this.pos);
  }
}
