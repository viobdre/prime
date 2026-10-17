"""Model catalogue shown in the app. Add entries here to expose more Demucs models."""

MODELS = [
    {
        "id": "htdemucs",
        "label": "HTDemucs — balanced (4 stems)",
        "description": "Vocals, drums, bass, other. Best speed/quality balance. Good default.",
    },
    {
        "id": "htdemucs_ft",
        "label": "HTDemucs Fine-tuned (4 stems)",
        "description": "Same four stems, usually cleaner, but slower and a much larger download.",
    },
    {
        "id": "htdemucs_6s",
        "label": "HTDemucs 6-stem",
        "description": "Adds guitar and piano stems. The piano stem is experimental and can be weaker.",
    },
]
