from simple_item_plugin.item import Item, ItemGroup
from simple_item_plugin.crafting import VanillaItem, ExternalItem, ShapedRecipe
from beet import (
    Context,
    Texture,
    Font,
    ItemModifier,
    LootTable,
    Generator,
    configurable,
)
from model_resolver import beet_default as model_resolver
from PIL import Image, ImageDraw, ImageFont
from simple_item_plugin.utils import (
    NAMESPACE,
    Lang,
    SimpleItemPluginOptions,
    export_translated_string,
    ItemProtocol,
)
import json
import pathlib
from dataclasses import dataclass, field
from typing import Iterable, TypeVar, Any, Optional, Literal
from itertools import islice
from pydantic import BaseModel

T = TypeVar("T")


def batched(iterable: Iterable[T], n: int) -> Iterable[tuple[T, ...]]:
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        yield batch


@configurable("simple_item_plugin", validator=SimpleItemPluginOptions)
def guide(ctx: Context, opts: SimpleItemPluginOptions):
    if not opts.generate_guide:
        return
    with ctx.generate.draft() as draft:
        if not opts.disable_guide_cache and False:
            draft.cache("guide", "guide")
        Guide(ctx, draft, opts).gen()


def image_count(count: int) -> Image.Image:
    """Generate an image showing the result count
    Args:
        count (int): The count to show
    Returns:
        Image: The image with the count
    """
    # Create the image
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_size = 24
    ttf_path = pathlib.Path(__file__).parent / "assets" / "minecraft_font.ttf"
    font = ImageFont.truetype(ttf_path, size=font_size)

    # Calculate text size and positions of the two texts
    text_width = draw.textlength(str(count), font=font)
    text_height = font_size + 6
    pos_1 = (45 - text_width), (0)
    pos_2 = (pos_1[0] - 2, pos_1[1] - 2)

    # Draw the count
    draw.text(pos_1, str(count), (50, 50, 50), font=font)
    draw.text(pos_2, str(count), (255, 255, 255), font=font)
    return img


@dataclass
class Guide:
    ctx: Context
    draft: Generator
    opts: SimpleItemPluginOptions

    char_index: int = 0x00ff
    char_offset: int = 0x0004
    count_to_char: dict[int, int] = field(default_factory=dict)
    page_count: int = 1

    max_group_lines_per_page: int = 6
    max_group_per_line: int = 6
    max_item_per_line: int = 6
    max_item_lines_per_page: int = 6
    @property
    def max_item_per_page(self) -> int:
        return self.max_item_per_line * self.max_item_lines_per_page
    @property
    def max_item_per_group(self) -> int:
        return self.max_item_per_line * self.max_group_per_line

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"

    def get_new_char(self, offset: Optional[int] = None) -> int:
        offset = offset or self.char_offset
        res = self.char_index
        self.char_index += offset
        return res

    def get_model_list(self) -> Iterable[str]:
        for recipe in ShapedRecipe.iter_values(self.ctx):
            for row in recipe.items:
                for item in row:
                    if item:
                        yield item.model_path
            yield recipe.result[0].model_path
        for item in Item.iter_values(self.ctx):
            yield item.model_path

    def model_path_to_render_path(self, model_path: str) -> str:
        return f"{NAMESPACE}:render/{model_path.replace(':', '/')}"

    def create_font(self):
        self.add_big_and_medium_font()
        font_path = f"{NAMESPACE}:pages"
        release = "_release"
        if False:
            release = ""
        none_2 = f"{NAMESPACE}:item/font/none_2.png"
        none_3 = f"{NAMESPACE}:item/font/none_3.png"
        none_4 = f"{NAMESPACE}:item/font/none_4.png"
        none_5 = f"{NAMESPACE}:item/font/none_5.png"
        template_craft = f"{NAMESPACE}:item/font/template_craft.png"
        template_result = f"{NAMESPACE}:item/font/template_result.png"

        github = f"{NAMESPACE}:item/logo/github.png"
        pmc = f"{NAMESPACE}:item/logo/pmc.png"
        smithed = f"{NAMESPACE}:item/logo/smithed.png"
        modrinth = f"{NAMESPACE}:item/logo/modrinth.png"

        root_path = pathlib.Path(__file__).parent / "assets" / "guide"

        namespace_path_to_real_path: dict[str, pathlib.Path] = {
            none_2: root_path / f"none_2{release}.png",
            none_3: root_path / f"none_3{release}.png",
            none_4: root_path / f"none_4{release}.png",
            none_5: root_path / f"none_5{release}.png",
            template_craft: root_path / "template_craft.png",
            template_result: root_path / "template_result.png",
            github: root_path / "logo" / "github.png",
            pmc: root_path / "logo" / "pmc.png",
            smithed: root_path / "logo" / "smithed.png",
            modrinth: root_path / "logo" / "modrinth.png",
        }
        for namespace_path, real_path in namespace_path_to_real_path.items():
            self.draft.assets.textures[namespace_path.removesuffix(".png")] = Texture(
                source_path=real_path
            )

        # fmt: off
        self.draft.assets.fonts[self.page_font] = Font({
            "providers": [
            {
                "type": "reference",
                "id": "minecraft:include/space"
            },
            { "type": "bitmap", "file": none_2,				"ascent": 7, "height": 8, "chars": ["\uef00"] },
            { "type": "bitmap", "file": none_3,				"ascent": 7, "height": 8, "chars": ["\uef01"] },
            { "type": "bitmap", "file": none_4,				"ascent": 7, "height": 8, "chars": ["\uef02"] },
            { "type": "bitmap", "file": none_5,				"ascent": 7, "height": 8, "chars": ["\uef03"] },
            { "type": "bitmap", "file": template_craft,		"ascent": -3, "height": 68, "chars": ["\uef13"] },
            { "type": "bitmap", "file": template_result,	"ascent": -20, "height": 34, "chars": ["\uef14"] },
            { "type": "bitmap", "file": github,				"ascent": 7, "height": 25, "chars": ["\uee01"] },
            { "type": "bitmap", "file": pmc,			    "ascent": 7, "height": 25, "chars": ["\uee02"] },
            { "type": "bitmap", "file": smithed,		    "ascent": 7, "height": 25, "chars": ["\uee03"] },
            { "type": "bitmap", "file": modrinth,			"ascent": 7, "height": 25, "chars": ["\uee04"] },
            ],
        })
        # fmt: on
        for count in range(2, 100):
            # Create the image
            img = image_count(count)
            img.putpixel((0, 0), (137, 137, 137, 255))
            img.putpixel((img.width - 1, img.height - 1), (137, 137, 137, 255))
            tex_path = f"{NAMESPACE}:item/font/number/{count}"
            self.draft.assets.textures[tex_path] = Texture(img)
            char_count = self.get_new_char(offset=1)
            char_index = f"\\u{char_count:04x}".encode().decode("unicode_escape")
            self.draft.assets.fonts[font_path].data["providers"].append(
                {
                    "type": "bitmap",
                    "file": tex_path + ".png",
                    "ascent": 10,
                    "height": 24,
                    "chars": [char_index],
                }
            )
            self.count_to_char[count] = char_count

    def add_items_to_font(self, *items: ItemProtocol):
        for item in items:
            if item.char_index:
                continue
            render_path = self.model_path_to_render_path(item.model_path)
            if not render_path in self.draft.assets.textures:
                raise Exception(f"Texture {render_path} not found")
            item.char_index = self.get_new_char()
            for i in range(3):
                char_item = f"\\u{item.char_index+i:04x}".encode().decode(
                    "unicode_escape"
                )
                self.draft.assets.fonts[self.page_font].data["providers"].append(
                    {
                        "type": "bitmap",
                        "file": f"{render_path}.png",
                        "ascent": {0: 8, 1: 7, 2: 6}.get(i),
                        "height": 16,
                        "chars": [char_item],
                    }
                )

    def get_item_json(
        self,
        item: Optional[ItemProtocol] = None,
        count: int = 1,
        row: Literal[0, 1, 2] = 0,
        part: Literal["up", "down"] = "up",
        is_result: bool = False,
    ) -> dict[str, Any]:
        if not item:
            return {
                "text": "\uef01",
                "font": self.page_font,
                "color": "white",
            }

        assert item.char_index
        char_item = f"\\u{item.char_index+row:04x}".encode().decode("unicode_escape")
        char_void = "\uef01"
        if item.minimal_representation.get("id") == "minecraft:air":
            return {"text": char_void, "font": self.page_font, "color": "white"}
            
        if is_result:
            char_void = "\uef02\uef02"
            char_space = "\uef00\uef00\uef03"
            char_item = f"{char_space}{char_item}{char_space}\uef00"
        else:
            char_space = "\uef03"
            char_item = f"{char_space}{char_item}{char_space}"
        if count > 1:
            char_count = self.count_to_char.get(count)
            char_count = f"\\u{char_count:04x}".encode().decode("unicode_escape")
            if is_result:
                char_void = f"\uef00\uef00\uef00{char_count}"
            else:
                char_void = f"\uef00\uef00\uef00{char_count}"

        text = char_item if part == "up" else char_void
        res = {
            "text": text,
            "font": self.page_font,
            "color": "white",
            "hoverEvent": {
                "action": "show_item", 
                "contents": item.minimal_representation
            },
        }
        if item.page_index:
            res["clickEvent"] = {
                "action": "change_page",
                "value": f"{item.page_index}",
            }
        return res
    
    def get_item_group_json(self, group: ItemGroup, part: Literal["up", "down"] = "up") -> dict[str, Any]:
        assert group.item_icon and group.page_index and group.item_icon.char_index
        char_item = f"\\u{group.item_icon.char_index+0:04x}".encode().decode("unicode_escape")
        char_space = "\uef03"
        char_item = f"{char_space}{char_item}{char_space}"
        if part == "down":
            char_item = "\uef01"
        return {
            "text": char_item,
            "font": self.page_font,
            "color": "white",
            "hoverEvent": {
                "action": "show_text",
                "contents": {"translate": group.name[0]},
            },
            "clickEvent": {
                "action": "change_page",
                "value": f"{group.page_index}",
            },
        }
    
    def add_big_and_medium_font(self):
        big_font_path = pathlib.Path(__file__).parent / "assets" / "guide" / "font" / "big.json"
        big_font_namespace = f"{NAMESPACE}:big_font"
        medium_font_path = pathlib.Path(__file__).parent / "assets" / "guide" / "font" / "medium.json"
        medium_font_namespace = f"{NAMESPACE}:medium_font"
        self.draft.assets.fonts[big_font_namespace] = Font(source_path=big_font_path)
        self.draft.assets.fonts[medium_font_namespace] = Font(source_path=medium_font_path)

    def create_pages(self) -> Iterable[str]:
        first_page : list[str | dict[str, Any]] = [""]
        first_page.append({
            "translate": f"{NAMESPACE}.name",
            "font": f"{NAMESPACE}:big_font",
        })
        first_page.append("\n\n")
        first_page.append({
            "translate": f"{NAMESPACE}.guide.first_page",
        })
        first_page.append("\n")
        yield json.dumps(first_page) 
        max_group_lines_per_page = 6
        max_group_per_line = 6
        n = 1
        nb_item_groups = len(list(ItemGroup.iter_values(self.ctx)))
        nb_categories_pages = nb_item_groups // (max_group_lines_per_page * max_group_per_line) + 1
        categories = (f"{NAMESPACE}.guide.categories", {
            Lang.en_us: "Categories",
            Lang.fr_fr: "Catégories",
        })
        export_translated_string(self.draft, categories)
        for groups_in_page in batched(ItemGroup.iter_values(self.ctx), max_group_lines_per_page * max_group_per_line):
            page : list[str | dict[str, Any]] = [""]
            page.append({
                "translate": categories[0],
                "font": f"{NAMESPACE}:medium_font",
            })
            page.append("\n\n")
            for group_line in batched(groups_in_page, max_group_per_line):
                for item_group in group_line:
                    item_group.page_index = 1 + nb_categories_pages + n
                    n += len(item_group.items_list) // self.max_item_per_page + 1
                    page.append(self.get_item_group_json(item_group))
                page.append("\n")
                for item_group in group_line:
                    page.append(self.get_item_group_json(item_group, part="down"))
                page.append("\n")
            yield json.dumps(page)

    def get_item_page_length(self, item: ItemProtocol) -> int:
        n = 0
        for recipe in ShapedRecipe.iter_values(self.ctx):
            if recipe.result[0] == item:
                n += 1
        return max(1, n)
    
    def create_craft_grid(self, recipe: ShapedRecipe) -> Iterable[str | dict[str, Any]]:
        yield {
            "text":f"\n\uef13 \uef14\n",
            "font":self.page_font,
            "color":"white"
        }
        yield "\n"

        for i in range(3):
            for part in ("up", "down"):
                yield {"text":"\uef00\uef00","font":self.page_font,"color":"white"}
                for j in range(3):
                    item = recipe.items[i][j]
                    yield self.get_item_json(item, row=i, part=part)
                # result generation
                if (i == 0 and part == "down") or (i == 1) or (i == 2 and part == "up"):
                    yield {"text":"\uef00\uef00\uef00\uef00","font":self.page_font,"color":"white"}
                # void generation
                if (i == 0 and part == "down") or (i == 2 and part == "up"):
                    yield self.get_item_json(recipe.result[0], is_result=True, part="down")
                # render generation
                if (i == 1):
                    yield self.get_item_json(recipe.result[0], is_result=True, part=part, count=recipe.result[1])
                yield "\n"
        yield "\n"

                
    
    def create_item_page(self, item: ItemProtocol) -> Iterable[str]:
        crafts = []
        for recipe in ShapedRecipe.iter_values(self.ctx):
            if recipe.result[0] == item:
                crafts.append(recipe)
        item_name = item.minimal_representation["components"]["minecraft:item_name"]
        item_name = json.loads(item_name)
        item_name["font"] = f"{NAMESPACE}:medium_font"
        item_name["color"] = "black"

        description = item.guide_description
        description = description if description else ("",{})
        export_translated_string(self.draft, description)

        n=0
        for recipe in crafts:
            page : list[str | dict[str, Any]] = [""]
            page.append(item_name)
            craft = self.create_craft_grid(recipe)
            page.extend(craft)
            page.append({
                "translate": description[0],
                "color":"black",
                "fallback": description[1].get(Lang.en_us, "")
            })

            page.append("\n")
            n += 1
            yield json.dumps(page)
        
        if len(crafts) == 0:
            page : list[str | dict[str, Any]] = [""]
            page.append(item_name)
            page.append("\n\n")
            page.append("No recipe")
            yield json.dumps(page)
    
    def create_group_pages(self, group: ItemGroup) -> Iterable[str]:
        max_item_per_line = 6
        max_item_lines_per_page = 6
        max_item_per_page = max_item_per_line * max_item_lines_per_page
        for item_page in batched(group.items_list, max_item_per_page):
            page : list[str | dict[str, Any]] = [""]
            page.append({
                "translate": group.name[0],
                "font": f"{NAMESPACE}:medium_font",
            })
            page.append("\n\n")
            for item_line in batched(item_page, max_item_per_line):
                for item in item_line:
                    page.append(self.get_item_json(item))
                page.append("\n")
                for item in item_line:
                    page.append(self.get_item_json(item, part="down"))
                page.append("\n")
            yield json.dumps(page)
        
        
    def gen(self):
        guide = Item.get(self.ctx, "guide")
        if not guide:
            raise Exception("Guide item not found")
        VanillaItem(id="minecraft:air").export(self.ctx)
        self.ctx.meta["model_resolver"]["filter"] = set(self.get_model_list())
        self.ctx.require(model_resolver)
        for texture_path in self.ctx.assets.textures.match(f"{NAMESPACE}:render/**"):
            img: Image.Image = self.ctx.assets.textures[texture_path].image
            img.putpixel((0, 0), (137, 137, 137, 255))
            img.putpixel((img.width - 1, img.height - 1), (137, 137, 137, 255))
            self.draft.assets.textures[texture_path] = Texture(img)
        self.create_font()
        self.add_items_to_font(*Item.iter_values(self.ctx))
        self.add_items_to_font(*ExternalItem.iter_values(self.ctx))
        self.add_items_to_font(*[i for i in VanillaItem.iter_values(self.ctx) if i.id != "minecraft:air"])
        pages = []
        pages.extend(self.create_pages())
        self.page_count = len(pages)
        groups = list(ItemGroup.iter_values(self.ctx))
        groups.sort(key=lambda x: x.page_index or 0)
        page_count_after = self.page_count + sum(len(group.items_list) // self.max_item_per_page + 1 for group in groups)
        for group in groups:
            for item in group.items_list:
                item.page_index = page_count_after + 1
                page_count_after += self.get_item_page_length(item)
        for group in groups:
            self.page_count += 1
            assert group.page_index == self.page_count, f"{group.page_index} != {self.page_count}"
            group_pages = list(self.create_group_pages(group))

            self.page_count += len(group_pages) - 1
            pages.extend(group_pages)
        for group in groups:
            for item in group.items_list:
                assert item.page_index
                item_pages = list(self.create_item_page(item))
                self.page_count += len(item_pages)
                pages.extend(item_pages)
        
        create_modifier(self.draft, pages)



def create_modifier(draft: Generator, pages: Iterable[str]):
    item_modifier = ItemModifier({
        "function": "minecraft:set_components",
        "components": {
            "minecraft:written_book_content": {
                "title": "Guide",
                "author": "AirDox_",
                "pages": pages,
                "resolved": True
            }
        }
    })
    draft.data.item_modifiers[f"{NAMESPACE}:impl/guide"] = item_modifier