import random
from beet import Context, Language, Generator
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from typing import Union
from pydantic import BaseModel


def generate_uuid() -> list[int]:
    return [
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
        random.randint(0, 0xFFFFFFFF),
    ]


def export_translated_string(ctx: Union[Context, Generator], translation: TranslatedString):
    # create default languages files if they don't exist
    for lang in Lang:
        if lang.namespaced not in ctx.assets.languages:
            ctx.assets.languages[lang.namespaced] = Language({})

    for lang, translate in translation[1].items():
        ctx.assets.languages[f"{NAMESPACE}:{lang.value}"].data[
            translation[0]
        ] = translate


class SimpleItemPluginOptions(BaseModel):
    custom_model_data: int
    generate_guide: bool = True