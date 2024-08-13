
from simple_item_plugin.item import ItemGroup, Item
from simple_item_plugin.crafting import ShapedRecipe, NBTSmelting, VanillaItem, ExternalItem
from simple_item_plugin.utils import TranslatedString, ItemProtocol, NAMESPACE, Lang, export_translated_string, SimpleItemPluginOptions
from typing import Any, Protocol, Literal, Optional, NamedTuple, Iterable, TypeVar
import json
from dataclasses import dataclass, field
from beet import Context, Generator, Texture, Font, ItemModifier, configurable
from model_resolver import beet_default as model_resolver
from PIL import Image, ImageDraw, ImageFont
from itertools import islice
import pathlib


@configurable("simple_item_plugin", validator=SimpleItemPluginOptions)
def guide(ctx: Context, opts: SimpleItemPluginOptions):
    if not opts.generate_guide:
        return
    with ctx.generate.draft() as draft:
        if not opts.disable_guide_cache and False:
            draft.cache("guide", "guide")
        Guide(ctx, draft, opts).gen()



MAX_RENDER_PER_LINE = 6
MAX_LINES_PER_PAGE = 6
MAX_RENDER_PER_PAGE = MAX_RENDER_PER_LINE * MAX_LINES_PER_PAGE


MinecraftTextComponentBase = str | dict[str, Any]
MinecraftTextComponent = list[MinecraftTextComponentBase]

class DictConvertible(Protocol):
    def to_text_component(self) -> "MinecraftTextComponentPlus":
        ...

MinecraftTextComponentBasePlus = str | dict[str, Any] | DictConvertible
MinecraftTextComponentPlus = list[MinecraftTextComponentBasePlus]


T = TypeVar("T")

def batched(iterable: Iterable[T], n: int) -> Iterable[tuple[T, ...]]:
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        yield batch


def convert_text_component(text: MinecraftTextComponentPlus, already_seen: Optional[set[int]] = None, max_depht: int = 200) -> MinecraftTextComponent:
    if already_seen is None:
        already_seen = set()
    if max_depht <= 0:
        raise ValueError("Max depht reached, circular reference ?")
    res : MinecraftTextComponent = []
    for part in text:
        if isinstance(part, str) or isinstance(part, dict):
            res.append(part)
        else:
            if id(part) in already_seen:
                raise ValueError("Circular reference")
            already_seen.add(id(part))
            res.extend(convert_text_component(part.to_text_component(), already_seen, max_depht - 1))
    return res
        


def get_char(char: int) -> str:
    return f"\\u{char:04x}".encode().decode("unicode_escape")


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
class ItemRender:
    item: Optional[ItemProtocol]
    is_big: bool = False
    part: Literal["render", "count", "void"] = "render"
    row: Literal[0, 1, 2] = 0
    count: int = 1
    count_to_char: dict[int, int] = field(default_factory=dict)

    void_small = "\uf8f1"
    void_big = "\uf8f2\uf8f2"
    space_small = "\uf8f3"
    space_big = "\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3"

    @property
    def char_item(self) -> str:
        assert self.item
        assert self.item.char_index
        char_item = get_char(self.item.char_index + self.row)
        if self.is_big:
            return f"{self.space_big}{char_item}{self.space_big}"
        return f"{self.space_small}{char_item}{self.space_small}"
    
    @property
    def char_void(self) -> str:
        if self.is_big:
            return self.void_big
        return self.void_small
    
    @property
    def char_count(self) -> str:
        assert self.count > 1 and self.part == "count", f"Invalid count {self.count} or part {self.part}"
        char_count = self.count_to_char.get(self.count)
        if not char_count:
            raise ValueError(f"Count {self.count} not supported")
        return f"\uf8f0\uf8f0\uf8f0{get_char(char_count)}"
    
    @property
    def text(self) -> str:
        if self.part == "render":
            return self.char_item
        if self.part == "count":
            if self.count == 1:
                return self.char_void
            return self.char_count
        if self.part == "void":
            return self.char_void
        raise ValueError(f"Invalid part {self.part}")
        

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"
    
    def to_text_component(self) -> MinecraftTextComponentPlus:
        return [self.get_render()]

    def get_render(self) -> dict[str, Any]:
        if (not self.item) or (self.item.minimal_representation.get("id") == "minecraft:air"):
            return {
                "text": self.char_void,
                "font": self.page_font,
                "color": "white",
            }

        res = {
            "text": self.text,
            "font": self.page_font,
            "color": "white",
            "hoverEvent": {
                "action": "show_item", 
                "contents": self.item.minimal_representation
            },
        }
        if self.item.page_index:
            res["clickEvent"] = {
                "action": "change_page",
                "value": f"{self.item.page_index}",
            }
        return res
    
@dataclass
class ItemRenderWithBackground:
    item: ItemProtocol
    count_to_char: dict[int, int] 
    space: str = "\uf8f1\uf8f1"
    

    def to_text_component(self) -> list[MinecraftTextComponentBasePlus]:
        return list(self.get_render())
    
    def get_render(self) -> Iterable[MinecraftTextComponentBasePlus]:
        space_1 = {
            "text": self.space,
            "font": f"{NAMESPACE}:pages",
            "color": "white",
        }
        space_2 = {
            "text": self.space + "\uf8f3",
            "font": f"{NAMESPACE}:pages",
            "color": "white",
        }
        yield space_1
        yield {
            "text": "\uf8f6\n",
            "font": f"{NAMESPACE}:pages",
            "color": "white",
        }
        yield space_2
        yield ItemRender(item=self.item, is_big=True, part="render", count_to_char=self.count_to_char, row=2)
        yield "\n"
        yield space_2
        yield ItemRender(item=self.item, is_big=True, part="count", count=1, count_to_char=self.count_to_char, row=2)
        yield "\n\n\n"

@dataclass
class ShapedRecipeRender:
    recipe: ShapedRecipe
    count_to_char: dict[int, int]

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"
    space_before_line = "\uf8f0\uf8f0"
    space_before_result = "\uf8f0\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3\uf8f3"

    def to_text_component(self) -> MinecraftTextComponentPlus:
        return list(self.get_craft_grid())


    def get_craft_grid(self) -> Iterable[MinecraftTextComponentBasePlus]:
        yield {
            "text":f"\uf8f7 \uf8f4\n",
            "font":self.page_font,
            "color":"white"
        }
        for i in range(3):
            assert i in (0, 1, 2)
            for partPosition in ("up", "down"):
                yield {"text":self.space_before_line,"font":self.page_font,"color":"white"}
                for j in range(3):
                    item = self.recipe.items[i][j]
                    yield ItemRender(
                        item=item,
                        is_big=False,
                        part="render" if partPosition == "up" else "void",
                        row=i,
                        count_to_char=self.count_to_char,
                    )
                # result generation
                if (i == 0 and partPosition == "down") or (i == 1) or (i == 2 and partPosition == "up"):
                    yield {"text":self.space_before_result,"font":self.page_font,"color":"white"}
                # void generation
                if (i == 0 and partPosition == "down") or (i == 2 and partPosition == "up"):
                    result = self.recipe.result[0]
                    yield ItemRender(
                        item=result,
                        is_big=True,
                        part="void",
                        count_to_char=self.count_to_char,
                    )
                # render generation
                if (i == 1):
                    result = self.recipe.result[0]
                    yield ItemRender(
                        item=result,
                        is_big=True,
                        part="render" if partPosition == "up" else "count",
                        count=self.recipe.result[1],
                        count_to_char=self.count_to_char,
                    )
                yield "\n"
        yield "\n"

@dataclass
class NBTSmeltingRender:
    recipe: NBTSmelting
    count_to_char: dict[int, int]

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"
    space_before_line = "\uf8f0\uf8f0\uf8f0\uf8f0\uf8f3\uf8f3"
    space_before_line_2 = "\uf8f1\uf8f1\uf8f1\uf8f0\uf8f0\uf8f0\uf8f0\uf8f0"

    def to_text_component(self) -> MinecraftTextComponentPlus:
        return list(self.get_furnace_grid())
    
    def get_furnace_grid(self) -> Iterable[MinecraftTextComponentBasePlus]:
        yield {
            "text":f"  \uf8f5\n",
            "font":self.page_font,
            "color":"white"
        }
        for part in ("render", "void"):
            yield {"text":self.space_before_line,"font":self.page_font,"color":"white"}
            yield ItemRender(
                item=self.recipe.item,
                is_big=False,
                part=part,
                row=1,
                count_to_char=self.count_to_char,
            )
            yield "\n"
        for part in ("render", "void"):
            yield {"text":self.space_before_line_2,"font":self.page_font,"color":"white"}
            yield ItemRender(
                item=self.recipe.result[0],
                is_big=True,
                part=part,
                count=self.recipe.result[1],
                row=2,
                count_to_char=self.count_to_char,
            )
            yield "\n"
        yield "\n\n\n"
            
    

@dataclass
class Page:
    ctx: Context
    content: MinecraftTextComponentPlus
    page_index: Optional[int] = None

    def to_text_component(self) -> MinecraftTextComponentPlus:
        return self.content


@dataclass
class CategoryElement:
    ctx: Context
    icon_char: int
    minimal_representation: dict[str, Any]
    pages: list[Page]

    @property
    def page_index(self) -> Optional[int]:
        if len(self.pages) == 0:
            raise ValueError("No pages")
        return self.pages[0].page_index

    @classmethod
    def from_item(cls, ctx: Context, item: ItemProtocol, count_to_char: dict[int,int]) -> 'CategoryElement':
        pages = list(cls.from_item_content(ctx, item, count_to_char))
        icon_char = item.char_index
        minimal_representation = item.minimal_representation
        assert icon_char is not None, "Item has no char index"
        return cls(ctx=ctx, icon_char=icon_char, pages=pages, minimal_representation=minimal_representation)

    @classmethod
    def from_item_content(cls, ctx: Context, item: ItemProtocol, count_to_char: dict[int,int]) -> Iterable[Page]:
        crafts = []
        for recipe in ShapedRecipe.iter_values(ctx):
            if recipe.result[0] == item:
                crafts.append(recipe)
        furnaces = []
        for recipe in NBTSmelting.iter_values(ctx):
            if recipe.result[0] == item:
                furnaces.append(recipe)
        item_name = item.minimal_representation["components"]["minecraft:item_name"]
        item_name = json.loads(item_name)
        item_name["font"] = f"{NAMESPACE}:medium_font"
        item_name["color"] = "black"

        description = item.guide_description
        description = description if description else ("",{})
        export_translated_string(ctx, description)
        
        content : MinecraftTextComponentPlus = [""]
        content.append(item_name)
        content.append("\n")
        content.append(ItemRenderWithBackground(item=item, count_to_char=count_to_char))
        content.append({
            "translate": description[0],
            "color":"black",
            "fallback": description[1].get(Lang.en_us, "No description")
        })
        yield Page(ctx=ctx, content=content)
        
        for recipe_batch in batched(crafts, 2):
            content : MinecraftTextComponentPlus = [""]
            for recipe in recipe_batch:
                content.append(ShapedRecipeRender(recipe=recipe, count_to_char=count_to_char))
            content.append("\n")
            yield Page(ctx=ctx, content=content)
        for recipe_batch in batched(furnaces, 2):
            content : MinecraftTextComponentPlus = [""]
            for recipe in recipe_batch:
                content.append(NBTSmeltingRender(recipe=recipe, count_to_char=count_to_char))
            content.append("\n")
            yield Page(ctx=ctx, content=content)

    def to_pages(self, ctx: Context) -> Iterable[Page]:
        for page in self.pages:
            page.page_index = ctx.meta["guide_index"]()
            yield page

@dataclass
class CategoryElementRender:
    category_element: CategoryElement
    part: Literal["up", "down"] = "up"

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"

    def to_text_component(self) -> MinecraftTextComponentPlus: 
        return list(self.get_render())
    
    def get_render(self) -> Iterable[MinecraftTextComponentBasePlus]:
        assert self.category_element.pages[0].page_index
        char_item = get_char(self.category_element.icon_char)
        char_space = "\uf8f3"
        char_item = f"{char_space}{char_item}{char_space}"
        if self.part == "down":
            char_item = "\uf8f1"
        yield {
            "text": char_item,
            "font": self.page_font,
            "color": "white",
            "hoverEvent": {
                "action": "show_item",
                "contents": self.category_element.minimal_representation,
            },
            "clickEvent": {
                "action": "change_page",
                "value": f"{self.category_element.pages[0].page_index}",
            },
        }
            

@dataclass
class Category:
    """
    After the CategoriesPages in the guide, this class represents a category,
    contains a list of CategoryElement that themselves contains a list of Page (for now, only ShapedRecipe and NBTSmelting)
    """
    name: TranslatedString
    icon_char: int
    elements: list[CategoryElement]
    page_index: Optional[int] = None

    @classmethod
    def from_item_group(cls, ctx: Context, item_group: ItemGroup, count_to_char: dict[int,int]) -> 'Category':
        elements : list[CategoryElement] = []
        for item in item_group.items_list:
            elements.append(CategoryElement.from_item(ctx, item, count_to_char))
        assert item_group.item_icon
        icon_char = item_group.item_icon.char_index
        assert icon_char is not None, "Item has no char index"
        return cls(name=item_group.name, icon_char=icon_char, elements=elements)
    
    def to_pages(self, ctx: Context) -> Iterable[Page]:
        for i, elements_in_page in enumerate(batched(self.elements, MAX_RENDER_PER_PAGE)):
            content : MinecraftTextComponentPlus = [""]
            content.append({
                "translate": self.name[0],
                "font": f"{NAMESPACE}:medium_font",
            })
            if len(self.elements) > MAX_RENDER_PER_PAGE:
                content.append({
                    "text": f", {i+1}",
                    "font": f"{NAMESPACE}:medium_font",
                })
            content.append("\n\n")
            for element_line in batched(elements_in_page, MAX_RENDER_PER_LINE):
                for element in element_line:
                    content.append(CategoryElementRender(category_element=element))
                content.append("\n")
                for element in element_line:
                    content.append(CategoryElementRender(category_element=element, part="down"))
                content.append("\n")
            index = ctx.meta["guide_index"]()
            if i == 0:
                self.page_index = index
            yield Page(ctx=ctx, content=content, page_index=index)
                
        
    

@dataclass
class CategoryRender:
    category: Category
    part: Literal["up", "down"] = "up"

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"

    def to_text_component(self) -> MinecraftTextComponentPlus:
        return list(self.get_render())
    
    def get_render(self) -> Iterable[MinecraftTextComponentBasePlus]:
        assert self.category.page_index, "No pages"
        char_item = get_char(self.category.icon_char)
        char_space = "\uf8f3"
        char_item = f"{char_space}{char_item}{char_space}"
        if self.part == "down":
            char_item = "\uf8f1"
        yield {
            "text": char_item,
            "font": self.page_font,
            "color": "white",
            "hoverEvent": {
                "action": "show_text",
                "contents": {"translate": self.category.name[0]},
            },
            "clickEvent": {
                "action": "change_page",
                "value": f"{self.category.page_index}",
            },
        }


@dataclass
class CategoriesPage:
    """
    A page at the beginning of the guide, containing clickable Category
    """
    categories: list[Category]

    @classmethod
    def from_item_groups(cls, ctx: Context, item_groups: Iterable[ItemGroup], count_to_char: dict[int,int]) -> 'CategoriesPage':
        assert len(list(item_groups)) <= MAX_RENDER_PER_PAGE
        categories : list[Category] = []
        for item_group in item_groups:
            categories.append(Category.from_item_group(ctx, item_group, count_to_char))
        return cls(categories=categories)
    
    def to_page(self, ctx: Context) -> Page:
        categories = (f"{NAMESPACE}.guide.categories", {
            Lang.en_us: "Categories",
            Lang.fr_fr: "Catégories",
        })
        export_translated_string(ctx, categories)
        content : MinecraftTextComponentPlus = [""]
        content.append({
            "translate": categories[0],
            "font": f"{NAMESPACE}:medium_font",
        })
        content.append("\n\n")
        for category_line in batched(self.categories, MAX_RENDER_PER_LINE):
            for category in category_line:
                content.append(CategoryRender(category=category))
            content.append("\n")
            for category in category_line:
                content.append(CategoryRender(category=category, part="down"))      
            content.append("\n")
        return Page(ctx=ctx, content=content, page_index=ctx.meta["guide_index"]())
        

@dataclass
class CategoriesPages:
    """
    List of pages at the beginning of the guide
    """
    pages: list[CategoriesPage]

    @classmethod
    def from_item_groups(cls, ctx: Context, item_groups: Iterable[ItemGroup], count_to_char: dict[int,int]) -> 'CategoriesPages':
        pages : list[CategoriesPage] = []
        for item_groups_line in batched(item_groups, MAX_RENDER_PER_PAGE):
            pages.append(CategoriesPage.from_item_groups(ctx, item_groups_line, count_to_char))
        return cls(pages=pages)
    


@dataclass
class AutoIncrement:
    """
    A simple auto increment class
    """
    value: int = 0
    def __call__(self) -> int:
        self.value += 1
        return self.value


@dataclass
class Guide:
    """
    Class that handles font creation, rendering items
    """
    ctx: Context
    draft: Generator
    opts: SimpleItemPluginOptions
    categories: Optional[CategoriesPages] = None 

    debug_mode: bool = False

    char_index: int = 0xe000
    char_offset: int = 0x0004
    count_to_char: dict[int, int] = field(default_factory=dict)
    page_count: int = 1

    @property
    def page_font(self) -> str:
        return f"{NAMESPACE}:pages"

    def get_new_char(self, offset: Optional[int] = None) -> int:
        offset = offset or self.char_offset
        res = self.char_index
        self.char_index += offset
        assert self.char_index < 0xf8f0, "The guide generator has reached the maximum number of characters"
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
    
    def add_big_and_medium_font(self):
        big_font_path = pathlib.Path(__file__).parent / "assets" / "guide" / "font" / "big.json"
        big_font_namespace = f"{NAMESPACE}:big_font"
        medium_font_path = pathlib.Path(__fu000namespace] = Font(source_path=medium_font_path)

    def create_font(self):
        self.add_big_and_medium_font()
        font_path = f"{NAMESPACE}:pages"
        release = "_release"
        if self.debug_mode:
            release = ""
        none_2 = f"{NAMESPACE}:item/font/none_2.png"
        none_3 = f"{NAMESPACE}:item/font/none_3.png"
        none_4 = f"{NAMESPACE}:item/font/none_4.png"
        none_5 = f"{NAMESPACE}:item/font/none_5.png"
        template_craft = f"{NAMESPACE}:item/font/template_craft.png"
        template_result = f"{NAMESPACE}:item/font/template_result.png"
        furnace_craft = f"{NAMESPACE}:item/font/furnace_craft.png"

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
            furnace_craft: root_path / "furnace_craft.png",
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
        x=9
        self.draft.assets.fonts[self.page_font] = Font({
            "providers": [
            {
                "type": "reference",
                "id": "minecraft:include/space"
            },
            { "type": "bitmap", "file": none_2,				"ascent": 7, "height": 8, "chars": ["\uf8f0"] },
            { "type": "bitmap", "file": none_3,				"ascent": 7, "height": 8, "chars": ["\uf8f1"] },
            { "type": "bitmap", "file": none_4,				"ascent": 7, "height": 8, "chars": ["\uf8f2"] },
            { "type": "bitmap", "file": none_5,				"ascent": 7, "height": 8, "chars": ["\uf8f3"] },
            { "type": "bitmap", "file": template_result,	"ascent": -20+x, "height": 34, "chars": ["\uf8f4"] },
            { "type": "bitmap", "file": furnace_craft,		"ascent": -4+x, "height": 68, "chars": ["\uf8f5"] },
            { "type": "bitmap", "file": template_result,	"ascent": -3+x, "height": 34, "chars": ["\uf8f6"] },
            { "type": "bitmap", "file": template_craft,		"ascent": -3+x, "height": 68, "chars": ["\uf8f7"] },
            { "type": "bitmap", "file": github,				"ascent": 7, "height": 25, "chars": ["\u0031"] },
            { "type": "bitmap", "file": pmc,			    "ascent": 7, "height": 25, "chars": ["\u0032"] },
            { "type": "bitmap", "file": smithed,		    "ascent": 7, "height": 25, "chars": ["\u0033"] },
            { "type": "bitmap", "file": modrinth,			"ascent": 7, "height": 25, "chars": ["\u0034"] },
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

    def to_pages(self) -> Iterable[Page]:
        self.categories = CategoriesPages.from_item_groups(self.ctx, ItemGroup.iter_values(self.ctx), self.count_to_char)

        self.ctx.meta.setdefault("guide_index", AutoIncrement())
        first_page_content : MinecraftTextComponentPlus = [""]
        first_page_content.append({
            "translate": f"{NAMESPACE}.name",
            "font": f"{NAMESPACE}:big_font",
        })
        first_page_content.append("\n\n")
        first_page_content.append({
            "translate": f"{NAMESPACE}.guide.first_page",
        })
        first_page_content.append("\n")
        yield Page(ctx=self.ctx, content=first_page_content, page_index=self.ctx.meta["guide_index"]())
        
        for categories_page in self.categories.pages:
            yield categories_page.to_page(self.ctx)
        for categories_page in self.categories.pages:
            for category in categories_page.categories:
                yield from category.to_pages(self.ctx)
        for categories_page in self.categories.pages:
            for category in categories_page.categories:
                for element in category.elements:
                    yield from element.to_pages(self.ctx)

    
                
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


        content : list[str] = []
        pages = list(self.to_pages())
        for page in pages:
            text_component = convert_text_component(page.to_text_component())
            content.append(json.dumps(text_component))
        self.create_modifier(content)

    def create_modifier(self, pages: list[str]):
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
        self.draft.data.item_modifiers[f"{NAMESPACE}:impl/guide"] = item_modifier

