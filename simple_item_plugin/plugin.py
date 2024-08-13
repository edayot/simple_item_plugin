
from beet import Context, configurable, Function, TextFile
from simple_item_plugin.types import NAMESPACE, AUTHOR
from simple_item_plugin.utils import export_translated_string, Lang, SimpleItemPluginOptions
from simple_item_plugin.guide import guide
from simple_item_plugin.versioning import beet_default as versioning
from simple_item_plugin.item import Item
from mecha import beet_default as mecha
from weld_deps.main import DepsConfig as WeldDepsConfig
import json
import pathlib



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
        assert dep in [
            k for k, _ in opts_weld_deps.deps_dict()
        ], f"Required dep {dep} not found in weld_deps"

    with open(stable_cache, "w") as f:
        json.dump(ctx.meta["simple_item_plugin"]["stable_cache"], f, indent=4)

    if opts.render_path_for_pack_png:
        tex = ctx.assets.textures[opts.render_path_for_pack_png]
        ctx.data.extra["pack.png"] = tex
        ctx.assets.extra["pack.png"] = tex