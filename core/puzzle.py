"""
Generic Image Puzzle Slicing & Reassembly Engine using Pillow (PIL).

Provides:
- `reassemble_image`: Rebuilds an unscrambled image from a scrambled image and coordinate mapping table.
- `scramble_image`: Inverts the process, cutting an original image and scattering it according to mapping.
- `generate_grid_mapping`: Utility to generate random or seeded grid scramble mappings.
"""
import io
import random
from typing import List, Tuple, Union, Optional, Dict, Any
from PIL import Image

from .coordinate_map import SliceCoord, PageMapping


def _ensure_image(img_input: Union[Image.Image, bytes, bytearray, str]) -> Image.Image:
    """Load PIL Image from PIL Image, file path, or bytes."""
    if isinstance(img_input, Image.Image):
        return img_input
    elif isinstance(img_input, (bytes, bytearray)):
        return Image.open(io.BytesIO(img_input))
    elif isinstance(img_input, str):
        return Image.open(img_input)
    else:
        raise ValueError(f"Unsupported image input type: {type(img_input)}")


def reassemble_image(
    scrambled: Union[Image.Image, bytes, bytearray, str],
    mapping: Union[PageMapping, List[SliceCoord], List[Dict[str, int]]],
    canvas_size: Optional[Tuple[int, int]] = None,
    background_color: Union[Tuple[int, int, int], Tuple[int, int, int, int], int] = (255, 255, 255)
) -> Image.Image:
    """
    Reassembles an unscrambled image from a scrambled source image using the coordinate mapping.

    Args:
        scrambled: The scrambled source image (Image, bytes, or file path).
        mapping: PageMapping or list of SliceCoord / coordinate dicts.
        canvas_size: (width, height) of restored image. If omitted, deduced from mapping.
        background_color: Background fill color for empty areas.

    Returns:
        Restored PIL Image.
    """
    src_img = _ensure_image(scrambled)
    mode = src_img.mode

    # Extract slice list and canvas size
    if isinstance(mapping, PageMapping):
        slices = mapping.slices
        if canvas_size is None:
            canvas_size = mapping.canvas_size
    elif isinstance(mapping, list):
        slices = [s if isinstance(s, SliceCoord) else SliceCoord.from_dict(s) for s in mapping]
    else:
        raise TypeError(f"Unsupported mapping type: {type(mapping)}")

    if canvas_size is None:
        # Calculate canvas size from maximum destination coordinates
        max_x = max(s.dx + s.dw for s in slices) if slices else src_img.width
        max_y = max(s.dy + s.dh for s in slices) if slices else src_img.height
        canvas_size = (max_x, max_y)

    # Initialize restored canvas
    restored = Image.new(mode, canvas_size, background_color)

    # Crop each slice from source and paste to destination
    for s in slices:
        box = (s.sx, s.sy, s.sx + s.sw, s.sy + s.sh)
        tile = src_img.crop(box)

        # In case slice was scaled (usually 1:1)
        if (s.dw != s.sw) or (s.dh != s.sh):
            tile = tile.resize((s.dw, s.dh), Image.Resampling.BILINEAR)

        restored.paste(tile, (s.dx, s.dy))

    return restored


def scramble_image(
    original: Union[Image.Image, bytes, bytearray, str],
    mapping: Union[PageMapping, List[SliceCoord], List[Dict[str, int]]],
    scrambled_size: Optional[Tuple[int, int]] = None,
    background_color: Union[Tuple[int, int, int], Tuple[int, int, int, int], int] = (255, 255, 255)
) -> Image.Image:
    """
    Inverses the reassembly process: chops an original clean image and scrambles it
    according to the coordinate mapping table.

    Args:
        original: The clean source image.
        mapping: PageMapping or list of SliceCoord / dicts.
        scrambled_size: (width, height) of the resulting scrambled image.
        background_color: Background fill color.

    Returns:
        Scrambled PIL Image.
    """
    src_img = _ensure_image(original)
    mode = src_img.mode

    if isinstance(mapping, PageMapping):
        slices = mapping.slices
        if scrambled_size is None:
            scrambled_size = mapping.scrambled_size
    elif isinstance(mapping, list):
        slices = [s if isinstance(s, SliceCoord) else SliceCoord.from_dict(s) for s in mapping]
    else:
        raise TypeError(f"Unsupported mapping type: {type(mapping)}")

    if scrambled_size is None:
        max_sx = max(s.sx + s.sw for s in slices) if slices else src_img.width
        max_sy = max(s.sy + s.sh for s in slices) if slices else src_img.height
        scrambled_size = (max_sx, max_sy)

    scrambled_img = Image.new(mode, scrambled_size, background_color)

    for s in slices:
        # Crop from destination position in clean image
        clean_box = (s.dx, s.dy, s.dx + s.dw, s.dy + s.dh)
        tile = src_img.crop(clean_box)

        if (s.sw != s.dw) or (s.sh != s.dh):
            tile = tile.resize((s.sw, s.sh), Image.Resampling.BILINEAR)

        # Paste to scrambled position
        scrambled_img.paste(tile, (s.sx, s.sy))

    return scrambled_img


def generate_grid_mapping(
    width: int,
    height: int,
    block_width: int = 32,
    block_height: int = 32,
    seed: Optional[int] = None
) -> PageMapping:
    """
    Generates a generic grid slice & shuffle mapping table for testing or obfuscation.
    """
    cols = (width + block_width - 1) // block_width
    rows = (height + block_height - 1) // block_height

    dest_blocks = []
    for r in range(rows):
        for c in range(cols):
            dx = c * block_width
            dy = r * block_height
            dw = min(block_width, width - dx)
            dh = min(block_height, height - dy)
            dest_blocks.append((dx, dy, dw, dh))

    # Permute source positions
    shuffled_indices = list(range(len(dest_blocks)))
    rng = random.Random(seed)
    rng.shuffle(shuffled_indices)

    slices: List[SliceCoord] = []
    scrambled_w = cols * block_width
    scrambled_h = rows * block_height

    for idx, (dx, dy, dw, dh) in enumerate(dest_blocks):
        src_idx = shuffled_indices[idx]
        sc = src_idx % cols
        sr = src_idx // cols
        sx = sc * block_width
        sy = sr * block_height
        slices.append(SliceCoord(sx=sx, sy=sy, sw=dw, sh=dh, dx=dx, dy=dy, dw=dw, dh=dh))

    return PageMapping(
        canvas_size=(width, height),
        scrambled_size=(scrambled_w, scrambled_h),
        slices=slices
    )
