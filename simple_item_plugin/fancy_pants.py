from typing import Generator
from beet import Context, Texture, ResourcePack
from dataclasses import dataclass
from PIL import Image


def beet_default(ctx: Context):
    ctx.assets.merge_policy.extend_namespace(Texture, FancyPants())


@dataclass
class FancyPants:
    def __call__(
        self,
        pack: ResourcePack,
        path: str,
        current_texture: Texture,
        conflict_texture: Texture,
    ) -> bool:
        if not path in {
            "minecraft:models/armor/leather_layer_1",
            "minecraft:models/armor/leather_layer_2",
        }:
            return False

        current: Image.Image = current_texture.image
        conflict: Image.Image = conflict_texture.image
        current = current.copy().convert("RGBA")
        current = current.crop((64, 0, current.width, current.height))
        conflict = conflict.copy().convert("RGBA")
        conflict_first = conflict.crop((0, 0, 64, conflict.height))
        conflict = conflict.crop((64, 0, conflict.width, conflict.height))

        new_size = (
            current.width + conflict.width + 64,
            max(current.height, conflict.height),
        )
        new_image = Image.new("RGBA", new_size)
        new_image.paste(conflict_first, (0, 0))

        layer_dict: dict[int, Image.Image] = {}
        self.fill_layer_dict(conflict, layer_dict)
        self.fill_layer_dict(current, layer_dict)

        for i, layer in enumerate(layer_dict.values()):
            new_image.paste(layer, (64 + i * 64, 0))

        current_texture.image = new_image

        return True

    @staticmethod
    def iterate_layer(image: Image.Image) -> Generator[Image.Image, None, None]:
        for i in range(0, image.width, 64):
            yield image.crop((i, 0, i + 64, image.height)).convert("RGBA")

    def fill_layer_dict(self, image: Image.Image, layer_dict: dict[int, Image.Image]):
        for layer in self.iterate_layer(image):
            color = layer.getpixel((0, 0))
            if not isinstance(color, tuple):
                raise ValueError("Expected color to be a tuple but got " + str(color))
            color_int = 256 * 256 * color[0] + 256 * color[1] + color[2]
            layer_dict[color_int] = layer
