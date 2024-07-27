
from beet import Context
from simple_item_plugin.types import NAMESPACE, AUTHOR
from simple_item_plugin.utils import export_translated_string, Lang
from simple_item_plugin.guide import guide
from simple_item_plugin.versioning import beet_default as versioning
from mecha import beet_default as mecha
import json


def beet_default(ctx: Context):
    NAMESPACE.set(ctx.project_id)
    AUTHOR.set(ctx.project_author)
    ctx.meta.setdefault("simple_item_plugin", {}).setdefault("stable_cache", {})
    stable_cache = ctx.directory / "stable_cache.json"
    if stable_cache.exists():
        with open(stable_cache, "r") as f:
            ctx.meta["simple_item_plugin"]["stable_cache"] = json.load(f)
    project_name = ctx.project_name.split("_")
    project_name = "".join([word.capitalize() for word in project_name])
    export_translated_string(ctx, (f"{NAMESPACE}.name", {Lang.en_us: ctx.project_name, Lang.fr_fr: ctx.project_name}))
    yield
    ctx.require(guide)
    ctx.require(versioning)
    ctx.require(mecha)

    with open(stable_cache, "w") as f:
        json.dump(ctx.meta["simple_item_plugin"]["stable_cache"], f, indent=4)