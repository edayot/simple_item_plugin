
from beet import Context
from simple_item_plugin.types import NAMESPACE, AUTHOR
from simple_item_plugin.export import export
from simple_item_plugin.guide import guide
from simple_item_plugin.versioning import beet_default as versioning
from mecha import beet_default as mecha


def beet_default(ctx: Context):
    NAMESPACE.set(ctx.project_id)
    AUTHOR.set(ctx.project_author)
    yield
    export(ctx)
    guide(ctx)
    versioning(ctx)
    mecha(ctx)