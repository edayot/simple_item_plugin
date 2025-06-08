
from beet import Context, configurable, Function, TextFile
from simple_item_plugin.crafting import ExternalItem, VanillaItem
from simple_item_plugin.types import NAMESPACE, AUTHOR
from simple_item_plugin.utils import export_translated_string, Lang, SimpleItemPluginOptions, logger
from simple_item_plugin.guide import Guide, guide
from simple_item_plugin.versioning import beet_default as versioning
from simple_item_plugin.item import Item
from mecha import beet_default as mecha
from weld_deps.main import DepsConfig as WeldDepsConfig
import json
import pathlib
from model_resolver import Render



@configurable("simple_item_plugin", validator=SimpleItemPluginOptions)
def beet_default(ctx: Context, opts: SimpleItemPluginOptions):
    NAMESPACE.set(ctx.project_id)
    AUTHOR.set(ctx.project_author)
    ctx.meta.setdefault("simple_item_plugin", {}).setdefault("stable_cache", {})
    stable_cache = ctx.directory / "stable_cache.json"
    if stable_cache.exists():
        with open(stable_cache, "r") as f:
            ctx.meta["simple_item_plugin"]["stable_cache"] = json.load(f)
    project_name = "".join([
        word.capitalize() 
        for word in ctx.project_name.split("_")
    ])
    export_translated_string(ctx, (f"{NAMESPACE}.name", {Lang.en_us: project_name, Lang.fr_fr: project_name}))
    ctx.meta.setdefault("required_deps", set())
    if opts.license_path:
        path = pathlib.Path(opts.license_path)
        ctx.data.extra[path.name] = TextFile(open(path, "r").read())
    if opts.readme_path:
        path = pathlib.Path(opts.readme_path)
        ctx.data.extra[path.name] = TextFile(open(path, "r").read())

    ctx.data.functions.setdefault(opts.load_function).prepend(f"scoreboard objectives add {NAMESPACE}.math dummy")
    

    yield
    ctx.require(guide)
    if opts.add_give_all_function:
        ctx.data.functions[f"{NAMESPACE}:impl/give_all"] = Function()
        for item in Item.iter_values(ctx):
            ctx.data.functions[f"{NAMESPACE}:impl/give_all"].append(
                f"loot give @s loot {item.loot_table_path}"
            )
    ctx.require(versioning)
    ctx.require(mecha)

    opts_weld_deps = ctx.validate("weld_deps", WeldDepsConfig)
    for dep in ctx.meta["required_deps"]:
        if not dep in [
            k for k, _ in opts_weld_deps.deps_dict()
        ]:
            logger.warning(f"Required dep {dep} not found in weld_deps")

    with open(stable_cache, "w") as f:
        json.dump(ctx.meta["simple_item_plugin"]["stable_cache"], f, indent=4)

    if opts.item_for_pack_png:
        item = Item.get(
            ctx, 
            opts.item_for_pack_png, 
            default=ExternalItem.get(
                ctx, 
                opts.item_for_pack_png, 
                default=VanillaItem.get(ctx, opts.item_for_pack_png, default=None)
            )
        )
        if item is None:
            logger.warning(f"Item {opts.item_for_pack_png} not found, using default pack.png")
            return
        path = Guide.item_to_render(item)
        if not path in ctx.assets.textures:
            render = Render(ctx)
            render.add_item_task(item.to_model_resolver(ctx), path_ctx=path)
            render.run()
        tex = ctx.assets.textures[path]
        ctx.data.extra["pack.png"] = tex
        ctx.assets.extra["pack.png"] = tex