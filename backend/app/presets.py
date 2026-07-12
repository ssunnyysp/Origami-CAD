"""Flasher presets — the only structural parameter source exposed to the UI.

`sides` must be even (a hexagon=6 or octagon=8 hub). `pleatRatio` and
`twistRatio` were picked by measuring residual fold-sweep strain and
"monotonic gathering" (does the model fold progressively toward the stowed
state, or fold partway and spring back?) with `scripts/validate_flasher.py`
across a grid of candidates — see the PR description for the sweep. They
are not free-form UI sliders (yet) because most combinations measure poorly;
each preset below is one of the validated-good points.
"""

PRESETS: list[dict] = [
    {
        "id": "hex-3",
        "name": "Hexagon Flasher (3 rings)",
        "sides": 6,
        "rings": 3,
        "pleatRatio": 0.45,
        "twistRatio": 0.55,
        "paperColor": "#d97757",
        "roughness": 0.8,
        "metalness": 0.02,
    },
    {
        "id": "hex-5",
        "name": "Hexagon Flasher (5 rings)",
        "sides": 6,
        "rings": 5,
        "pleatRatio": 0.5,
        "twistRatio": 0.55,
        "paperColor": "#7c9c8e",
        "roughness": 0.75,
        "metalness": 0.05,
    },
    {
        "id": "oct-4",
        "name": "Octagon Flasher (4 rings)",
        "sides": 8,
        "rings": 4,
        "pleatRatio": 0.4,
        "twistRatio": 0.5,
        "paperColor": "#5b7fa6",
        "roughness": 0.7,
        "metalness": 0.05,
    },
    {
        "id": "oct-5",
        "name": "Octagon Flasher (5 rings)",
        "sides": 8,
        "rings": 5,
        "pleatRatio": 0.4,
        "twistRatio": 0.5,
        "paperColor": "#c9a35b",
        "roughness": 0.65,
        "metalness": 0.08,
    },
]
