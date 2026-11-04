"""BUTTERGEN: the base of the honor system.

- honor: how well the cat really follows the warrior code, -100 to 100. Only StarClan and the
  Dark Forest see it.
- reputation: what the Clan knows about it, -100 to 100. Breaking the code unseen costs honor
  but not reputation.
- clan_trust: how much the Clan trusts its leader, deputy and healers in that role, -100 to 100.

Everyone starts at 0. Old saves start at 0 too.
"""

from scripts.cat.enums import CatRank
from scripts.clan_package.settings import get_clan_setting
from scripts.game_structure.localization import load_lang_resource

LOW, HIGH = -100, 100

# the ranks whose Clan trust matters
TRUST_RANKS = (CatRank.LEADER, CatRank.DEPUTY, CatRank.MEDICINE_CAT)

# label cutoffs, highest first: at or above the number gets the label
HONOR_LABELS = ((40, "honorable"), (10, "trustworthy"), (-9, "unremarkable"), (-39, "questionable"))
HONOR_LOWEST = "dishonored"
REPUTATION_LABELS = ((40, "respected"), (10, "trusted"), (-9, "unremarkable"), (-39, "doubted"))
REPUTATION_LOWEST = "disgraced"
TRUST_LABELS = ((40, "unwavering"), (10, "firm"), (-9, "steady"), (-39, "shaken"))
TRUST_LOWEST = "broken"


def texts() -> dict:
    return load_lang_resource("events/honor.json")


def clamp(value) -> int:
    return max(LOW, min(HIGH, int(round(value))))


def change_honor(cat, amount):
    cat.honor = clamp(cat.honor + amount)


def change_reputation(cat, amount):
    cat.reputation = clamp(cat.reputation + amount)


def change_clan_trust(cat, amount):
    cat.clan_trust = clamp(cat.clan_trust + amount)


def has_clan_trust(cat) -> bool:
    return cat.status.rank in TRUST_RANKS


def has_honor(cat) -> bool:
    """living Clan cats past the newborn stage. Outsiders and the dead don't show it"""
    if cat.dead or cat.status.is_outsider:
        return False
    return cat.status.rank != CatRank.NEWBORN


def _label(value, cutoffs, lowest, group) -> str:
    key = lowest
    for cutoff, name in cutoffs:
        if value >= cutoff:
            key = name
            break
    return texts()[group][key]


def honor_label(cat) -> str:
    return _label(cat.honor, HONOR_LABELS, HONOR_LOWEST, "honor")


def reputation_label(cat) -> str:
    return _label(cat.reputation, REPUTATION_LABELS, REPUTATION_LOWEST, "reputation")


def trust_label(cat) -> str:
    return _label(cat.clan_trust, TRUST_LABELS, TRUST_LOWEST, "clan_trust")


def profile_lines(cat) -> str:
    """the lines for the profile, each ending in a newline, or "" when the cat shows none"""
    if not has_honor(cat):
        return ""
    profile = texts()["profile"]
    from scripts.honor.judgment import profile_note

    out = profile["honor_line"].replace("%{honor}", honor_label(cat)).replace(
        "%{reputation}", reputation_label(cat)
    ) + profile_note(cat) + "\n"
    if has_clan_trust(cat):
        out += profile["trust_line"].replace("%{trust}", trust_label(cat)) + "\n"
    return out


# ------------------------------------------------------------------ Clan settings

def code_frequency() -> str:
    """"rare", "normal" or "often", from the two linked Clan settings"""
    if get_clan_setting("rare code events"):
        return "rare"
    if get_clan_setting("frequent code events"):
        return "often"
    return "normal"


def healer_mates_break_code() -> bool:
    return bool(get_clan_setting("healer mates break the code"))
