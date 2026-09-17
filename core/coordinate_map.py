"""
Slice coordinate data structures and serialization for Puzzle Slicing & Reassembly.
"""
from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Any

@dataclass
class SliceCoord:
    """
    Represents a single slice mapping:
    Source rectangle (sx, sy, sw, sh) -> Destination rectangle (dx, dy, dw, dh).
    """
    sx: int
    sy: int
    sw: int
    sh: int
    dx: int
    dy: int
    dw: int
    dh: int

    def to_dict(self) -> Dict[str, int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "SliceCoord":
        return cls(
            sx=int(data["sx"]),
            sy=int(data["sy"]),
            sw=int(data["sw"]),
            sh=int(data["sh"]),
            dx=int(data["dx"]),
            dy=int(data["dy"]),
            dw=int(data["dw"]),
            dh=int(data["dh"]),
        )


@dataclass
class PageMapping:
    """
    Complete mapping information for a scrambled image page.
    """
    canvas_size: Tuple[int, int]      # (width, height) of restored image
    scrambled_size: Tuple[int, int]   # (width, height) of scrambled image
    slices: List[SliceCoord]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canvas_size": list(self.canvas_size),
            "scrambled_size": list(self.scrambled_size),
            "slices": [s.to_dict() for s in self.slices],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PageMapping":
        return cls(
            canvas_size=(data["canvas_size"][0], data["canvas_size"][1]),
            scrambled_size=(data["scrambled_size"][0], data["scrambled_size"][1]),
            slices=[SliceCoord.from_dict(s) for s in data["slices"]],
        )
