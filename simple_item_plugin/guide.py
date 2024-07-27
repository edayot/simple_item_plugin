from simple_item_plugin.item import Item
from simple_item_plugin.crafting import VanillaItem
from beet import Context, Texture, Font, ItemModifier, LootTable, Generator, configurable
from model_resolver import beet_default as model_resolver
from PIL import Image, ImageDraw, ImageFont
from simple_item_plugin.utils import NAMESPACE, Lang, SimpleItemPluginOptions, export_translated_string
import json
import pathlib
from dataclasses import dataclass
from typing import Iterable

@dataclass
class GuideItem:
    item : Item | VanillaItem
    char_index : int = 0
    page_index : int = -1

    def __hash__(self):
        return hash(self.item)


def get_item_list(ctx: Context) -> dict[str, GuideItem]:
    items = dict()
    items["minecraft:air"] = GuideItem(VanillaItem("minecraft:air"))
    for recipe in ctx.meta["registry"].get("recipes", []):
        for row in recipe.items:
            for item in row:
                if item:
                    items[item.id] = GuideItem(item)
        items[recipe.result[0].id] = GuideItem(recipe.result[0])
    return items

def search_item(ctx: Context, item: GuideItem):
    for recipe in ctx.meta["registry"].get("recipes", []):
        if recipe.result[0].id == item.item.id:
            return recipe
    return None



CHAR_OFFSET = 0x4
def char_index_number():
    global CHAR_INDEX_NUMBER
    CHAR_INDEX_NUMBER += CHAR_OFFSET
    return CHAR_INDEX_NUMBER

@configurable("simple_item_plugin", validator=SimpleItemPluginOptions)
def guide(ctx: Context, opts: SimpleItemPluginOptions):
    global CHAR_INDEX_NUMBER, COUNT_TO_CHAR
    CHAR_INDEX_NUMBER = 0x0030
    COUNT_TO_CHAR = {}

    if not opts.generate_guide:
        return
    with ctx.generate.draft() as draft:
        # draft.cache("guide", "guide")
        generate_guide(ctx, draft)

def generate_first_page(draft: Generator, items: Iterable[GuideItem]):
    big_font_path = pathlib.Path(__file__).parent / "assets" / "guide" / "font" / "big.json"
    big_font_namespace = f"{NAMESPACE}:big_font"

    medium_font_path = pathlib.Path(__file__).parent / "assets" / "guide" / "font" / "medium.json"
    medium_font_namespace = f"{NAMESPACE}:medium_font"

    draft.assets.fonts[big_font_namespace] = Font(source_path=big_font_path)
    draft.assets.fonts[medium_font_namespace] = Font(source_path=medium_font_path)

    first_page : list[str | dict] = [""]
    first_page.append({
        "translate": f"{NAMESPACE}.name",
        "font": big_font_namespace,
    })
    first_page.append("\n\n")
    first_page.append({
        "translate": f"{NAMESPACE}.guide.first_page",
    })
    first_page.append("\n")

    for item in items:
        if isinstance(item.item, VanillaItem):
            continue
        char_item = f"\\u{item.char_index:04x}".encode().decode("unicode_escape")
        first_page.append(get_item_json(item, f"{NAMESPACE}:pages", f"\uef03{char_item}\uef03"))
    first_page.append("\n")
    for item in items:
        if isinstance(item.item, VanillaItem):
            continue
        char_space = "\uef01"
        first_page.append(get_item_json(item, f"{NAMESPACE}:pages", char_space))

    return json.dumps(first_page)

    
def generate_guide(ctx: Context, draft: Generator):
    guide = Item.get_from_id(ctx, "guide")
    if not guide:
        raise ValueError("The guide item is not present in the registry")
    air = VanillaItem("minecraft:air")
    # Render the registry
    all_items= get_item_list(ctx)
    ctx.meta["model_resolver"]["filter"] = [i.item.model_path for i in all_items.values()]
    ctx.require(model_resolver)
    for item in all_items.values():
        model_path = item.item.model_path
        path = f"{NAMESPACE}:render/{model_path.replace(':', '/')}"
        if not path in ctx.assets.textures:
            img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        else:
            img : Image.Image = ctx.assets.textures[path].image
        img = img.copy()
        img.putpixel((0,0),(137,137,137,255))
        img.putpixel((img.width-1,img.height-1),(137,137,137,255))
        draft.assets.textures[path] = Texture(img.copy())
    create_font(draft, all_items.values())
    pages = []
    page_index = len(pages) + 2
    for id, item in all_items.items():
        if not (craft := search_item(ctx, item)):
            continue
        item.page_index = page_index
        page_index += 1
        items_craft = [
            [
                all_items[i.id] if i else all_items["minecraft:air"]
                for i in row
            ]
            for row in craft.items
        ]
        if (n := len(items_craft)) < 3:
            for i in range(3-n):
                items_craft.append([all_items["minecraft:air"]]*3)
        item_result = all_items[craft.result[0].id]
        pages.append(generate_craft(
            items_craft,
            item_result,
            craft.result[1],
            draft
        ))
    pages.insert(0,generate_first_page(draft, all_items.values()))
    create_modifier(draft, pages)




def create_font(draft: Generator, items: Iterable[GuideItem]):
    global CHAR_INDEX_NUMBER
    font_path = f"{NAMESPACE}:pages"
    release = '_release'
    if False:
        release = ''
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

    namespace_path_to_real_path : dict[str, pathlib.Path] = {
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
        draft.assets.textures[namespace_path.removesuffix(".png")] = Texture(source_path=real_path)

    

    draft.assets.fonts[font_path] = Font({
        "providers": [
        {
            "type": "reference",
            "id": "minecraft:include/space"
        },
        { "type": "bitmap", "file": none_2,				"ascent": 7, "height": 8, "chars": ["\uef00"] },
        { "type": "bitmap", "file": none_3,				"ascent": 7, "height": 8, "chars": ["\uef01"] },
        { "type": "bitmap", "file": none_4,				"ascent": 7, "height": 8, "chars": ["\uef02"] },
        { "type": "bitmap", "file": none_5,				"ascent": 7, "height": 8, "chars": ["\uef03"] },
        { "type": "bitmap", "file": template_craft,				"ascent": -3, "height": 68, "chars": ["\uef13"] },
        { "type": "bitmap", "file": template_result,				"ascent": -20, "height": 34, "chars": ["\uef14"] },

        { "type": "bitmap", "file": github,				        "ascent": 7, "height": 25, "chars": ["\uee01"] },
        { "type": "bitmap", "file": pmc,				            "ascent": 7, "height": 25, "chars": ["\uee02"] },
        { "type": "bitmap", "file": smithed,				        "ascent": 7, "height": 25, "chars": ["\uee03"] },
        { "type": "bitmap", "file": modrinth,				        "ascent": 7, "height": 25, "chars": ["\uee04"] },
        ],
    })
    for item in items:
        if not item.char_index:
            item.char_index = char_index_number()
        render = f"{NAMESPACE}:render/{item.item.model_path.replace(':','/')}"
        for i in range(3):
            char_item = f"\\u{item.char_index+i:04x}".encode().decode("unicode_escape")
            draft.assets.fonts[font_path].data["providers"].append(
                {
                    "type": "bitmap",
                    "file": f"{render}.png",
                    "ascent": {0: 8, 1: 7, 2: 6}.get(i),
                    "height": 16,
                    "chars": [char_item]
                }
            )
    for count in range(2,100):
        # Create the image
        img = image_count(count)
        img.putpixel((0,0),(137,137,137,255))
        img.putpixel((img.width-1,img.height-1),(137,137,137,255))
        tex_path = f"{NAMESPACE}:item/font/number/{count}"
        draft.assets.textures[tex_path] = Texture(img)
        char_count = CHAR_INDEX_NUMBER
        CHAR_INDEX_NUMBER += 1
        char_index = f"\\u{char_count:04x}".encode().decode("unicode_escape")
        draft.assets.fonts[font_path].data["providers"].append(
            {
                "type": "bitmap",
                "file": tex_path + ".png",
                "ascent": 10,
                "height": 24,
                "chars": [char_index]
            }
        )
        COUNT_TO_CHAR[count] = char_index

        




def get_item_json(item: GuideItem, font_path: str, char : str = "\uef01"):
    if item.item.minimal_representation.get("id") == "minecraft:air":
        return {
            "text":char,
            "font":font_path,
            "color":"white"
        }
    if item.page_index == -1:
        return {
            "text":char,
            "font":font_path,
            "color":"white",
            "hoverEvent":{"action":"show_item","contents": item.item.minimal_representation}
        }
    return {
        "text":char,
        "font":font_path,
        "color":"white",
        "hoverEvent":{"action":"show_item","contents": item.item.minimal_representation},
        "clickEvent":{"action":"change_page","value":f"{item.page_index}"}
    }

def generate_craft(craft: list[list[GuideItem]], result: GuideItem, count: int, draft: Generator) -> str:
    # Create a font for the page
    font_path = f'{NAMESPACE}:pages'
    page : list[str | dict] = [""]
    item_name = result.item.get_item_name() if isinstance(result.item, Item) else result.item.id
    description = result.item.guide_description if isinstance(result.item, Item) else None
    description = description if description else ("", {})
    export_translated_string(draft, description)
    if isinstance(item_name, str):
        item_name = {"text":item_name}
    item_name["font"] = f"{NAMESPACE}:medium_font"
    item_name["color"] = "black"
    page.append(item_name)
    page.append({
        "text":f"\n\uef13 \uef14\n",
        "font":font_path,
        "color":"white"
    })
    page.append("\n")
    for i in range(3):
        for e in range(2):
            page.append({"text":"\uef00\uef00","font":font_path,"color":"white"})
            for j in range(3):
                # normal item lines
                item = craft[i][j]
                char_item = f"\\u{item.char_index + i:04x}".encode().decode("unicode_escape")
                page.append(get_item_json(item, font_path, f'\uef03{char_item}\uef03' if e == 0 else "\uef01"))
            if (i == 0 and e == 1) or (i == 2 and e == 0):
                # result generation : void
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_space = "\uef02\uef02"
                page.append(get_item_json(result, font_path, char_space))
            if i == 1 and e == 0:
                # result generation : render
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_result = f"\\u{result.char_index:04x}".encode().decode("unicode_escape")
                char_space = "\uef00\uef00\uef03"
                page.append(get_item_json(result, font_path, f'{char_space}{char_result}{char_space}\uef00'))
            if i == 1 and e == 1:
                # result generation : count
                page.append({"text":"\uef00\uef00\uef00\uef00","font":font_path,"color":"white"})
                char_space = "\uef02\uef02"
                if count > 1:
                    char_count = COUNT_TO_CHAR[count]
                    char_space = f"\uef00\uef00\uef00{char_count}"
                page.append(get_item_json(result, font_path, char_space))
            page.append("\n")
    page.append("\n")
    page.append({
        "translate": description[0],
        "color":"black",
        "fallback": description[1].get(Lang.en_us, "")
    })
    return json.dumps(page)


def image_count(count: int) -> Image.Image:
    """ Generate an image showing the result count
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
    font = ImageFont.truetype(ttf_path, size = font_size)

    # Calculate text size and positions of the two texts
    text_width = draw.textlength(str(count), font = font)
    text_height = font_size + 6
    pos_1 = (45-text_width), (0)
    pos_2 = (pos_1[0]-2, pos_1[1]-2)
    
    # Draw the count
    draw.text(pos_1, str(count), (50, 50, 50), font = font)
    draw.text(pos_2, str(count), (255, 255, 255), font = font)
    return img



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