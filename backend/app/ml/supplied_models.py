"""Adapters for the supplied audio checkpoints.

The model files are optional. Importing this module does not import PyTorch so
the normal mock-classifier and test paths remain lightweight.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from app.core.config import get_settings

ACCIDENT_LABELS = {
    0: "glass_break",
    1: "animal",
    2: "animal",
}


def _model_path() -> Path:
    configured = get_settings().model_path
    if not configured:
        raise RuntimeError("MODEL_PATH is required when using the supplied audio model")
    return Path(configured).expanduser()


def _audio_to_melspec(clip: bytes) -> Any:
    import librosa
    import numpy as np

    audio, sample_rate = librosa.load(io.BytesIO(clip), sr=16000)
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=sample_rate,
        n_mels=128,
        n_fft=2048,
        hop_length=512,
    )
    mel_db = librosa.power_to_db(mel, ref=np.max, top_db=None)
    mel_db = mel_db[:, :128]
    if mel_db.shape[1] < 128:
        mel_db = np.pad(mel_db, ((0, 0), (0, 128 - mel_db.shape[1])), mode="constant")
    value_range = float(np.max(mel_db) - np.min(mel_db))
    if value_range == 0:
        return np.zeros_like(mel_db, dtype=np.float32)
    return ((mel_db - np.min(mel_db)) / value_range).astype(np.float32)


def _build_accident_model(torch: Any) -> Any:
    import torch.nn as nn

    class AudioCRNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv1 = nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1)
            self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1)
            self.conv3 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
            self.pool = nn.MaxPool2d(kernel_size=2, stride=2)
            self.relu = nn.ReLU()
            self.bn1 = nn.BatchNorm2d(16)
            self.bn2 = nn.BatchNorm2d(32)
            self.bn3 = nn.BatchNorm2d(64)
            self.gru = nn.GRU(64 * 16, 128, num_layers=1, batch_first=True)
            self.fc1 = nn.Linear(128, 128)
            self.fc2 = nn.Linear(128, 3)
            self.dropout = nn.Dropout(0.5)

        def forward(self, x: Any) -> Any:
            x = self.pool(self.relu(self.bn1(self.conv1(x))))
            x = self.pool(self.relu(self.bn2(self.conv2(x))))
            x = self.pool(self.relu(self.bn3(self.conv3(x))))
            batch, channels, height, width = x.size()
            x = x.permute(0, 3, 1, 2).contiguous().view(batch, width, channels * height)
            x, _ = self.gru(x)
            x = self.relu(self.fc1(x[:, -1, :]))
            return self.fc2(self.dropout(x))

    return AudioCRNN()


class AccidentAudioModel:
    """Load the supplied three-class checkpoint and expose project predictions.

    The checkpoint's non-glass classes are intentionally mapped to ``animal``:
    they are traffic and car-crash classes, which are outside the alert catalog.
    """

    model_name = "accident-audio-crnn"
    model_version = "supplied-accident-model"

    def __init__(self) -> None:
        import torch

        path = _model_path()
        if not path.is_file():
            raise FileNotFoundError(f"MODEL_PATH does not exist: {path}")
        self._torch = torch
        self._model = _build_accident_model(torch)
        state = torch.load(path, map_location=torch.device("cpu"), weights_only=True)
        self._model.load_state_dict(state)
        self._model.eval()

    def classify(self, clip: bytes, *, filename: str = "") -> list[dict[str, float | str]]:
        del filename
        import numpy as np

        spec = _audio_to_melspec(clip)
        tensor = self._torch.from_numpy(np.asarray(spec)).unsqueeze(0).unsqueeze(0)
        with self._torch.no_grad():
            probabilities = self._torch.softmax(self._model(tensor), dim=1)[0].tolist()
        predictions: list[dict[str, float | str]] = [
            {"label": ACCIDENT_LABELS[index], "confidence": float(confidence)}
            for index, confidence in enumerate(probabilities)
        ]
        return sorted(predictions, key=lambda item: float(item["confidence"]), reverse=True)

