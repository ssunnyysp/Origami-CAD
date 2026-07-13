"""Flasher presets — the only structural parameter source exposed to the UI.

`gridDivisions` must be ODD, so the sheet has a single, well-centered hub
cell (an even count splits the center between four cells with no true
middle). Ring count = (gridDivisions - 1) / 2; the rigid Newton-continuation
solver's cost and residual both grow with ring count (see solver.py), so
presets stay in the range validated by scripts/validate_flasher.py.

`layerGapRatio` and `heightRatio` are accepted for API compatibility but are
currently unused: the fold is driven entirely by the crease pattern's own
mountain/valley angles (see solver.py), not by a prescribed wrap shape.
"""

PRESETS: list[dict] = [
    {
        "id": "simple-5",
        "name": "Simple Flasher (5x5)",
        "gridDivisions": 5,
        "layerGapRatio": 0.14,
        "heightRatio": 0.90,
        "paperColor": "#d97757",
        "roughness": 0.8,
        "metalness": 0.02,
    },
    {
        "id": "flasher-7",
        "name": "Flasher (7x7)",
        "gridDivisions": 7,
        "layerGapRatio": 0.10,
        "heightRatio": 0.90,
        "paperColor": "#7c9c8e",
        "roughness": 0.75,
        "metalness": 0.05,
    },
    {
        "id": "flasher-9",
        "name": "Flasher (9x9)",
        "gridDivisions": 9,
        "layerGapRatio": 0.08,
        "heightRatio": 0.90,
        "paperColor": "#5b7fa6",
        "roughness": 0.7,
        "metalness": 0.05,
    },
    {
        "id": "flasher-11",
        "name": "Flasher (11x11)",
        "gridDivisions": 11,
        "layerGapRatio": 0.07,
        "heightRatio": 0.90,
        "paperColor": "#c9a35b",
        "roughness": 0.65,
        "metalness": 0.08,
    },
]
