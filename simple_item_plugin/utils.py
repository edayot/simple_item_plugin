import random
from beet import Context, Language, Generator
from simple_item_plugin.types import Lang, TranslatedString, NAMESPACE
from typing import Union, Optional, Self, Iterable
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
    add_give_all_function: bool = True
    render_path_for_pack_png: Optional[str] = None





class Registry(BaseModel):
    id: str
    def export(self, ctx: Union[Context, Generator]) -> Self:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        assert self.id not in real_ctx.meta.setdefault("registry", {}).setdefault(self.__class__.__name__, {}), f"Registry {self.id} already exists"
        real_ctx.meta["registry"][self.__class__.__name__][self.id] = self
        return self
    
    @classmethod
    def get(cls, ctx: Union[Context, Generator], id: str) -> Self:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__][id]
    
    @classmethod
    def iter_items(cls, ctx: Union[Context, Generator]) -> Iterable[tuple[str, Self]]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].items()
    
    @classmethod
    def iter_values(cls, ctx: Union[Context, Generator]) -> Iterable[Self]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].values()
    
    @classmethod
    def iter_keys(cls, ctx: Union[Context, Generator]) -> Iterable[str]:
        real_ctx = ctx.ctx if isinstance(ctx, Generator) else ctx
        real_ctx.meta.setdefault("registry", {}).setdefault(cls.__name__, {})
        return real_ctx.meta["registry"][cls.__name__].keys()
        

        
