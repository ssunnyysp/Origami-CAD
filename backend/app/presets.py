"""Square-flasher presets — the only structural parameter source exposed to
the UI. All sheets are square; gridDivisions is the pleat grid (Shafer's Big
Bang uses 32)."""

PRESETS: list[dict] = [
    {
        "id": "classic-16",
        "name": "Classic Flasher (16×16)",
        "gridDivisions": 16,
        "wrapPerRing": 1.0,
        "layerGapRatio": 0.10,
        "heightRatio": 0.30,
        "paperColor": "#e8dcc8",
        "roughness": 0.8,
        "metalness": 0.05,
    },
    {
        "id": "fine-24",
        "name": "Fine Flasher (24×24)",
        "gridDivisions": 24,
        "wrapPerRing": 1.0,
        "layerGapRatio": 0.08,
        "heightRatio": 0.25,
        "paperColor": "#cde0d8",
        "roughness": 0.7,
        "metalness": 0.05,
    },
    {
        "id": "big-bang-32",
        "name": "Big Bang (32×32)",
        "gridDivisions": 32,
        "wrapPerRing": 1.0,
        "layerGapRatio": 0.07,
        "heightRatio": 0.22,
        "paperColor": "#c8d4e8",
        "roughness": 0.6,
        "metalness": 0.10,
    },
]
