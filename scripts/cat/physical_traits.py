"""BUTTERGEN: physical traits as inherited genes, from Inheritable Physical Traits by Snow."""
from random import random

import ujson

with open("resources/dicts/physical_traits.json", "r", encoding="utf-8") as read_file:
    TRAITS = ujson.loads(read_file.read())["traits"]


def config():
    from scripts.game_structure import constants

    return constants.CONFIG.get("buttergen", {}).get("traits", {})


def _traits_of(genes):
    traits = getattr(genes, "physical_traits", None)
    return traits if isinstance(traits, dict) else {}


def founder_traits():
    """Traits for a cat with no known parents"""
    if not config().get("enabled", True):
        return {}
    chances = {
        "dominant": config().get("dominant_chance", 0),
        "recessive": config().get("recessive_chance", 0),
        "acquired": config().get("acquired_chance", 0),
    }
    rare_weight = config().get("rare_weight", 1)

    traits = {}
    for name, trait in TRAITS.items():
        chance = chances.get(trait["inherit"], 0)
        # rare traits (saber teeth, manes...) show up less often: a recessive one needs two
        # copies to show, so each copy gets the square root
        rarity = rare_weight if trait.get("rare") else 1
        chance *= rarity ** 0.5 if trait["inherit"] == "recessive" else rarity
        copies = 1 if random() < chance else 0
        if trait["inherit"] != "acquired" and random() < chance:
            copies += 1
        if copies:
            traits[name] = copies
    return traits


def _passes(copies):
    return copies >= 2 or (copies == 1 and random() < 0.5)


def kit_traits(par1, par2):
    """Each parent passes one of their two copies of each trait, like any other gene"""
    parents = [_traits_of(par) for par in (par1, par2)]
    traits = {}
    for name in set(parents[0]) | set(parents[1]):
        if TRAITS.get(name, {}).get("inherit") == "acquired":
            continue
        copies = sum(1 for par in parents if _passes(par.get(name, 0)))
        if copies:
            traits[name] = copies
    return traits


def shown(genes):
    """The traits a cat shows, in the order they're listed in physical_traits.json"""
    traits = _traits_of(genes)
    shown_traits, groups = [], set()
    for name, trait in TRAITS.items():
        copies = traits.get(name, 0)
        if not copies or (trait["inherit"] == "recessive" and copies < 2):
            continue
        group = trait.get("group")
        if group in groups:
            continue
        if group:
            groups.add(group)
        shown_traits.append(name)
    return shown_traits


def describe(genes):
    return ", ".join(TRAITS[name]["text"] for name in shown(genes))


def gene_list(genes):
    """For the genes tooltip: every trait carried, with how many copies"""
    traits = _traits_of(genes)
    return [f"{name} ({copies}/2)" for name, copies in sorted(traits.items())]


def match_parents(kit_genes, parent_genes):
    """Made-up parents for your cat's birth get the trait copies your cat needed from them"""
    kit = _traits_of(kit_genes)
    parents = [_traits_of(genes) for genes in parent_genes]
    for genes, traits in zip(parent_genes, parents):
        genes.physical_traits = traits
    for name, copies in kit.items():
        if TRAITS.get(name, {}).get("inherit") == "acquired":
            continue
        have = [i for i, par in enumerate(parents) if par.get(name, 0)]
        for i, par in enumerate(parents):
            if len(have) >= min(copies, len(parents)):
                break
            if i not in have:
                par[name] = 1
                have.append(i)
