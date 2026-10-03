import logging
import re

from beet import Context, Function, FunctionTag, LootTable, LootTableTag

from .models import Versioning, VersioningOptions
from .utils import call_if_version_match


logger = logging.getLogger(__name__)

PUBLIC_PAT = re.compile("^#>? @public")


def generate_call(ctx: Context, opts: VersioningOptions, path: str):
    """Generates the actual call function that checks the version"""

    base_path = path.replace(opts.api.implementation_prefix, "")

    version_check = ctx.generate[opts.api.version_check_path](
        base_path, Function(call_if_version_match(opts.scoreholder, opts.version, path))
    )
    api_path = ctx.generate[opts.api.tag_path](
        base_path, FunctionTag({"values": [{
            "id": version_check,
            "required": False,
        }]})
    )

    logger.info(api_path)


def generate_api(ctx: Context):
    """Generates API calls based on `@public` listed inside of function files

    Note: Must be the very first line of the file

    TODO: Support @public on any line of the function doc comment
            https://github.com/SpyglassMC/Spyglass/wiki/IMP-Doc
    """

    opts = ctx.inject(Versioning).opts

    query = ctx.query(match=opts.api.match, extend=Function)
    if Function in query:
        for path, func in query[Function].keys():
            if func.lines and path is not None and PUBLIC_PAT.match(func.lines[0]):
                generate_call(ctx, opts, path)
    
    query = ctx.query(match=opts.refactor.match, extend=LootTable)
    if LootTable in query:
        for path, advancement in query[LootTable].keys():
            base_path = path.replace(opts.api.implementation_prefix, "")
            api_path = ctx.generate[opts.api.loot_table_tag_path](
                base_path, LootTableTag({"values": [path]})
            )
            logger.info(api_path)
        
