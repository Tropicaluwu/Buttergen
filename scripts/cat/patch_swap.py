"""BUTTERGEN: Mink's Torties, white patch shapes as tortie patches and the other way around."""
from random import choice, random

import ujson

from scripts.cat import patch_genes
from scripts.cat.sprites.sprite_names import sprite_names


def _names(sheet):
    with open(f"sprites/dicts/{sheet}_sprite_data.json", "r", encoding="utf-8") as read_file:
        return sprite_names(ujson.loads(read_file.read())["sprite_list"])


def _with_combos(sizes):
    with open("sprites/dicts/white_patches_combos.json", "r", encoding="utf-8") as read_file:
        combos = ujson.loads(read_file.read())
    names = []
    for size in sizes:
        names += _names(f"white_patches_{size}") + list(combos.get(size, {}))
    return names


WHITE_LOW = _with_combos(["little"])
WHITE_MID = _with_combos(["mid"])
WHITE_HIGH = _with_combos(["high", "mostly"])
TORTIE = _names("tortie_patches")


def tortie_pools(genes):
    """The white patch pools (low, mid, high) if this tortie patch rolls as a white shape, or None"""
    if (patch_genes.copies(genes, "white_shape_torties")
            and random() < patch_genes.config().get("white_shape_patch_chance", 0)):
        return WHITE_LOW, WHITE_MID, WHITE_HIGH
    return None


def maybe_white(white_pattern, genes):
    """A cat with the gene and white patches gets a tortie patch shape in white too"""
    if isinstance(white_pattern, list) and white_pattern and patch_genes.copies(genes, "tortie_shape_white"):
        return white_pattern + [choice(TORTIE)]
    return white_pattern
