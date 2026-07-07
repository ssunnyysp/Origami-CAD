"""Pinwheel-flasher presets — the only structural parameter source exposed to
the UI. All sheets are square with a single-cell hub; gridDivisions is the
pleat grid (the classic tutorial flasher is 8, matching the reference
diagram)."""

PRESETS: list[dict] = [
    {
        "id": "simple-8",
        "name": "Simple Flasher (8×8)",
        "gridDivisions": 8,
        "wrapPerRing": 1.5,
        "layerGapRatio": 0.12,
        "heightRatio": 0.80,
        "paperColor": "#d97757",
        "roughness": 0.8,
        "metalness": 0.02,
    },
    {
        "id": "flasher-16",
        "name": "Flasher (16×16)",
        "gridDivisions": 16,
        "wrapPerRing": 1.5,
        "layerGapRatio": 0.10,
        "heightRatio": 0.55,
        "paperColor": "#7c9c8e",
        "roughness": 0.75,
        "metalness": 0.05,
    },
    {
        "id": "flasher-24",
        "name": "Flasher (24×24)",
        "gridDivisions": 24,
        "wrapPerRing": 1.5,
        "layerGapRatio": 0.08,
        "heightRatio": 0.42,
        "paperColor": "#5b7fa6",
        "roughness": 0.7,
        "metalness": 0.05,
    },
    {
        "id": "flasher-32",
        "name": "Flasher (32×32)",
        "gridDivisions": 32,
        "wrapPerRing": 1.5,
        "layerGapRatio": 0.07,
        "heightRatio": 0.35,
        "paperColor": "#c9a35b",
        "roughness": 0.65,
        "metalness": 0.08,
    },
]
