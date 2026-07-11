"""Flasher presets — the only structural parameter source exposed to the UI.

`gridDivisions` must be ODD, so the sheet has a single, well-centered hub
cell (an even count splits the center between four cells with no true
middle). Preset names show gridDivisions directly.

The coil (how many times a ring winds around before it fits its wrapped
layer) is no longer a tunable parameter — it falls straight out of paper-
length conservation in fold_engine.py, so it's always exactly right for the
given layerGapRatio.
"""

PRESETS: list[dict] = [
    {
        "id": "simple-7",
        "name": "Simple Flasher (7×7)",
        "gridDivisions": 7,
        "layerGapRatio": 0.14,
        "heightRatio": 0.90,
        "paperColor": "#d97757",
        "roughness": 0.8,
        "metalness": 0.02,
    },
    {
        "id": "flasher-15",
        "name": "Flasher (15×15)",
        "gridDivisions": 15,
        "layerGapRatio": 0.10,
        "heightRatio": 0.90,
        "paperColor": "#7c9c8e",
        "roughness": 0.75,
        "metalness": 0.05,
    },
    {
        "id": "flasher-23",
        "name": "Flasher (23×23)",
        "gridDivisions": 23,
        "layerGapRatio": 0.08,
        "heightRatio": 0.90,
        "paperColor": "#5b7fa6",
        "roughness": 0.7,
        "metalness": 0.05,
    },
    {
        "id": "flasher-31",
        "name": "Flasher Big Bang (31×31)",
        "gridDivisions": 31,
        "layerGapRatio": 0.07,
        "heightRatio": 0.90,
        "paperColor": "#c9a35b",
        "roughness": 0.65,
        "metalness": 0.08,
    },
]
