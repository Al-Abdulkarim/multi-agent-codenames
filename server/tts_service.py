"""TTS client service for generating and storing chat audio files."""

from __future__ import annotations

import base64
import json
import logging
import time
import uuid
from pathlib import Path

import requests

from config import TTSConfig

log = logging.getLogger(__name__)


class TTSService:
    """Generate WAV audio from text and persist it for playback."""

    def __init__(self, cfg: TTSConfig) -> None:
        self.cfg = cfg
        self.endpoint = cfg.endpoint_url.strip()
        self.enabled = bool(self.endpoint)
        project_root = Path(__file__).resolve().parent.parent
        configured_dir = Path(cfg.persist_dir)
        self.persist_dir = configured_dir if configured_dir.is_absolute() else project_root / configured_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.serve_base_path = self._normalize_base_path(cfg.serve_base_path)

    @staticmethod
    def _normalize_base_path(path: str) -> str:
        clean = (path or "/media/tts").strip()
        if not clean.startswith("/"):
            clean = f"/{clean}"
        return clean.rstrip("/")

    @staticmethod
    def _decode_base64_audio(value: str) -> bytes:
        token = value.strip()
        if token.startswith("data:"):
            _, _, token = token.partition(",")
        return base64.b64decode(token, validate=False)

    def _extract_audio_bytes(self, raw: bytes, content_type: str) -> bytes:
        ctype = (content_type or "").lower()
        if "audio/wav" in ctype or "audio/x-wav" in ctype:
            return raw

        if "application/json" in ctype:
            payload = json.loads(raw.decode("utf-8"))
            for key in ("audio_base64", "wav_base64", "audio", "data"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return self._decode_base64_audio(value)
            raise ValueError("TTS JSON response did not include audio data")

        if raw.startswith(b"RIFF"):
            return raw
        raise ValueError(f"Unsupported TTS response type: {content_type or 'unknown'}")

    @staticmethod
    def _is_wav(audio_bytes: bytes) -> bool:
        return len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE"

    def cleanup_old_files(self) -> None:
        files = sorted(
            self.persist_dir.glob("*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return

        now = time.time()
        max_age_seconds = max(self.cfg.retention_days, 0) * 86400
        keep_count = max(self.cfg.max_files, 0)

        for idx, file_path in enumerate(files):
            should_delete = False
            if max_age_seconds > 0 and now - file_path.stat().st_mtime > max_age_seconds:
                should_delete = True
            if keep_count > 0 and idx >= keep_count:
                should_delete = True
            if should_delete:
                try:
                    file_path.unlink(missing_ok=True)
                except Exception:
                    log.warning("Failed to delete old TTS file: %s", file_path, exc_info=True)

    def resolve_voice(self, speaker_key: str | None, fallback_team: str | None = None) -> str:
        if speaker_key == "teammate":
            return "teammate"
        if speaker_key == "opponent_spymaster":
            return "opponent_spymaster"
        if speaker_key == "opponent_operative":
            return "opponent_operative"
        if speaker_key == "human":
            return "human"

        # Fallback if key is missing for any reason.
        if fallback_team:
            return "teammate" if fallback_team == "red" else "opponent_operative"
        return "ar"

    def synthesize_to_file(
        self,
        text: str,
        *,
        voice_name: str,
        message_id: int | None = None,
    ) -> dict | None:
        """Generate speech from text, persist WAV, and return audio metadata."""
        if not self.enabled or not text.strip():
            return None

        payload = {
            "text": text,
            "voice": voice_name or "ar",
            "exaggeration": 0.5,
            "temperature": 0.8,
            "seed": 0,
            "cfgw": 0.5,
        }

        try:
            # Match the user's working call shape exactly:
            # requests.post(url, json={...})
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=self.cfg.timeout_seconds,
            )
            if response.status_code >= 400:
                msg = response.text.strip()
                raise ValueError(f"TTS HTTP {response.status_code}: {msg[:300]}")

            raw = response.content
            content_type = response.headers.get("Content-Type", "")
            audio_bytes = self._extract_audio_bytes(raw, content_type)
            if not self._is_wav(audio_bytes):
                raise ValueError("TTS response is not a valid WAV payload")

            self.cleanup_old_files()
            token = str(message_id) if message_id is not None else uuid.uuid4().hex
            filename = f"{int(time.time() * 1000)}-{token}.wav"
            audio_path = self.persist_dir / filename
            audio_path.write_bytes(audio_bytes)

            return {
                "available": True,
                "url": f"{self.serve_base_path}/{filename}",
                "format": "wav",
                "size_bytes": len(audio_bytes),
            }
        except (requests.RequestException, TimeoutError, ValueError, json.JSONDecodeError):
            log.warning("TTS synthesis failed", exc_info=True)
            return None
