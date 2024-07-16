from enum import Enum

NAMESPACE = "technicalutils"


class Lang(Enum):
    en_us = "en_us"
    fr_fr = "fr_fr"

    @property
    def namespaced(self):
        return f"{NAMESPACE}:{self.value}"


class Rarity(Enum):
    common = "white"
    uncommon = "yellow"
    rare = "aqua"
    epic = "magenta"


TranslatedString = tuple[str, dict[Lang, str]]

TextComponent_base = str | dict
TextComponent = TextComponent_base | list[TextComponent_base]
