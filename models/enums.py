from enum import Enum


class Language(str, Enum):
    ARABIC = "ar"
    ENGLISH = "en"


class TeamColor(str, Enum):
    RED = "red"
    BLUE = "blue"


class PlayerRole(str, Enum):
    SPYMASTER = "spymaster"
    OPERATIVE = "operative"  # a.k.a. "Spy"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class BoardSize(int, Enum):
    SMALL = 15
    CLASSIC = 25
    LARGE = 35


class CardType(str, Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"
