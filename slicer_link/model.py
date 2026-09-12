"""Portable source identities and geometry validation. No platform or web dependencies."""

import hashlib
import json
import math
import re
import struct
from collections import Counter
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

MAX_MESH_BYTES = 32 * 1024 * 1024


class LinkError(Exception):
    """An actionable error safe to display to the user."""


def require(condition, message):
    if not condition:
        raise LinkError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def object_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{24}", value), "Invalid Onshape identifier.")
    return value


def service_origin(value, *, development=False):
    parsed = urlsplit(value)
    valid_scheme = parsed.scheme == "https" or (
        development and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    )
    require(
        valid_scheme
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment,
        "Use the application's HTTPS address without a path.",
    )
    return value.rstrip("/")


@dataclass(frozen=True)
class Source:
    document_id: str
    workspace_id: str
    element_id: str
    microversion: str
    part_id: str
    configuration: str = ""

    def __post_init__(self):
        for value in (self.document_id, self.workspace_id, self.element_id, self.microversion):
            object_id(value)
        require(
            isinstance(self.part_id, str)
            and 0 < len(self.part_id) <= 4096
            and not any(ord(c) < 32 for c in self.part_id),
            "Invalid part identity.",
        )
        require(
            isinstance(self.configuration, str)
            and len(self.configuration) <= 8192
            and not any(ord(c) < 32 for c in self.configuration),
            "Invalid configuration.",
        )

    def to_dict(self):
        return asdict(self)

    @property
    def key(self):
        return digest(canonical(self.to_dict()).encode())


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def validate_stl(data: bytes):
    require(84 <= len(data) <= MAX_MESH_BYTES, "Model file is empty or too large.")
    count = struct.unpack_from("<I", data, 80)[0]
    require(4 <= count and len(data) == 84 + count * 50, "Incomplete or unsupported STL file.")
    edges = Counter()
    low, high = [math.inf] * 3, [-math.inf] * 3
    volume6 = 0.0
    for values in struct.iter_unpack("<12fH", data[84:]):
        a, b, c = (tuple(values[i : i + 3]) for i in (3, 6, 9))
        for vertex in (a, b, c):
            require(
                all(math.isfinite(x) and abs(x) <= 100_000 for x in vertex),
                "Model contains invalid coordinates.",
            )
            for i in range(3):
                low[i], high[i] = min(low[i], vertex[i]), max(high[i], vertex[i])
        area = cross(tuple(b[i] - a[i] for i in range(3)), tuple(c[i] - a[i] for i in range(3)))
        require(sum(v * v for v in area) > 1e-16, "Model contains a degenerate triangle.")
        volume6 += sum(x * y for x, y in zip(a, cross(b, c)))
        edges[a, b] += 1
        edges[b, c] += 1
        edges[c, a] += 1
    require(
        all(n == 1 and edges[b, a] == 1 for (a, b), n in edges.items()),
        "Model must be a closed, consistently oriented solid.",
    )
    require(math.isfinite(volume6) and volume6 > 1e-6, "Model has no positive solid volume.")
    return {"bounds_mm": [low, high], "triangles": count, "sha256": digest(data)}


def link_filename(name, link_id):
    require(re.fullmatch(r"[a-f0-9]{32}", link_id), "Invalid link identifier.")
    # An immutable ASCII filename works across Windows and Linux. IDs prevent
    # collisions after case folding, renames, and same-name Part Studios.
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", name).strip("-_")[:48] or "part"
    return f"{label}-{link_id}.stl"
