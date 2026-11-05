"""Pure-stdlib geometry for clear, physically consistent gravity arrows."""

import math
from collections.abc import Sequence


def inward_arrow(earth_center: Sequence[float], moon_center: Sequence[float],
                 *, clearance: float = 0.34, length: float = 0.61
                 ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return arrow endpoints, always pointing from the Moon toward Earth."""
    offset = [float(earth_center[i]) - float(moon_center[i]) for i in range(3)]
    distance = math.sqrt(sum(value * value for value in offset))
    if distance <= clearance + length:
        raise ValueError("gravity arrow requires separated celestial bodies")
    direction = [value / distance for value in offset]
    start = tuple(float(moon_center[i]) + direction[i] * clearance for i in range(3))
    end = tuple(start[i] + direction[i] * length for i in range(3))
    return start, end
