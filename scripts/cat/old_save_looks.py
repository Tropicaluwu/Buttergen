"""Buttergen: takes looks that aren't in the game anymore off cats from v0.1 and v0.2 saves."""
from random import Random

from scripts.cat.pelts import Pelt

GONE_TORTIE = "MMT_"
GONE_WHITE = "MMW_"
TORTIE_PATCHES = ("ONE", "TWO", "THREE", "FOUR", "MASK", "SMOKE", "STREAK", "DELILAH")
ACCESSORY_LISTS = ("collar_accessories", "tail_accessories", "body_accessories", "head_accessories",
                   "paw_accessories")
_known_accessories = set()


def _swap(value, rng):
    """Anything that names a look that's gone: a new patch, None for a white patch"""
    if not isinstance(value, str):
        return value
    if value.startswith(GONE_TORTIE):
        return rng.choice(TORTIE_PATCHES)
    if value.startswith(GONE_WHITE):
        return None
    return value


def _clean(value, rng):
    if isinstance(value, dict):
        for key, inner in value.items():
            value[key] = _clean(inner, rng)
        return value
    if isinstance(value, list):
        kept = [x for x in value if not (isinstance(x, str) and x.startswith(GONE_WHITE))]
        cleaned = [_clean(inner, rng) for inner in kept]
        # a list of white patches that lost its only one means no white at all
        return cleaned if cleaned or not value else "No"
    swapped = _swap(value, rng)
    return "No" if swapped is None and value is not None else swapped


def _keep_accessories(cat_dict):
    if not _known_accessories:
        for name in ACCESSORY_LISTS:
            _known_accessories.update(getattr(Pelt, name))
    for key in ("accessory", "inventory"):
        worn = cat_dict.get(key)
        if isinstance(worn, list):
            cat_dict[key] = [x for x in worn if x in _known_accessories]
        elif isinstance(worn, str) and worn not in _known_accessories:
            cat_dict[key] = None


def clean_old_looks(cat_dict):
    # the same patch every time for the same cat
    rng = Random(f"looks{cat_dict.get('ID')}")
    _clean(cat_dict, rng)
    _keep_accessories(cat_dict)
