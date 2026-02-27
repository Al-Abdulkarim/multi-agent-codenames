"""
التكوين المركزي للنظام
Central Configuration Module
"""

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from enum import Enum

load_dotenv()


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BoardSize(int, Enum):
    SMALL = 8
    MEDIUM = 16
    LARGE = 25


class TeamColor(str, Enum):
    RED = "red"
    BLUE = "blue"


class CardType(str, Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"


class PlayerRole(str, Enum):
    SPYMASTER = "spymaster"
    OPERATIVE = "operative"


class GameConfig(BaseModel):
    """إعدادات اللعبة"""

    board_size: BoardSize = BoardSize.LARGE
    ai_difficulty: Difficulty = Difficulty.MEDIUM
    human_team: TeamColor = TeamColor.RED
    human_role: PlayerRole = PlayerRole.OPERATIVE
    google_api_key: str = Field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_model: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )

    def get_card_distribution(self, starting_team: TeamColor = TeamColor.RED) -> dict:
        """توزيع البطاقات حسب حجم اللوحة"""
        distributions = {
            8: {"red": 2, "blue": 2, "neutral": 2, "assassin": 1},
            16: {"red": 5, "blue": 5, "neutral": 4, "assassin": 1},
            25: {"red": 8, "blue": 8, "neutral": 7, "assassin": 1},
        }
        dist = distributions[self.board_size.value].copy()
        # الفريق البادئ يحصل على بطاقة إضافية
        dist[starting_team.value] += 1
        return dist


class AppConfig(BaseModel):
    """إعدادات التطبيق"""

    host: str = Field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = Field(
        default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true"
    )
