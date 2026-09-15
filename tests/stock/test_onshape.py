import io
import json
from dataclasses import replace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

from scripts.make_fixtures import stl
from slicer_link.model import LinkError, Source
from slicer_link.onshape import Client

SOURCE = Source("a" * 24, "b" * 24, "c" * 24, "d" * 24, "JLD", "length=500+mm;label=A%26B")
# A closed faceted solid with the same bounds as the live drill-bit reproduction.
MESH = stl(
    [(6, 0, 250), (0, 6, 250), (-6, 0, 250), (0, -6, 250), (0, 0, 0), (0, 0, 500)],
    [(i, (i + 1) % 4, 5) for i in range(4)] + [((i + 1) % 4, i, 4) for i in range(4)],
)


class Response(io.BytesIO):
    status = 200


class ExportOpener:
    def __init__(self, source=SOURCE, *, changes=None, origin="https://cad-usw2.onshape.com", data=MESH):
        self.requests = []
        self.data = data
        query = {
            "documentId": source.document_id,
            "elementId": source.element_id,
            "microversion": source.microversion,
            "partIds": source.part_id,
            "configuration": source.configuration,
            "mode": "binary",
            "units": "millimeter",
            "scale": "1.0",
        }
        query.update(changes or {})
        self.location = origin + "/modelexport?" + urlencode(query, doseq=True)

    def open(self, request, timeout):
        self.requests.append(request)
        if "/boundingboxes?" in request.full_url:
            # Actual conservative CAD bounds from Onshape's configured drill example.
            return Response(json.dumps({
                "lowX": -0.006137523190177717, "highX": 0.006137523190177716,
                "lowY": -0.006232217234123498, "highY": 0.0062322172341234975,
                "lowZ": 0, "highZ": 0.5,
            }).encode())
        if "/stl?" in request.full_url:
            raise HTTPError(request.full_url, 307, "Redirect", {"Location": self.location}, io.BytesIO())
        return Response(self.data)


@pytest.mark.parametrize("configuration", ["", SOURCE.configuration])
def test_export_measures_mesh_without_rejecting_conservative_cad_bounds(configuration):
    source = replace(SOURCE, configuration=configuration)
    opener = ExportOpener(source)
    data, metrics = Client("test-token", opener=opener).export(source)
    assert data == MESH
    assert metrics["bounds_mm"] == [[-6, -6, 0], [6, 6, 500]]
    assert len(opener.requests) == 2  # STL request and its download, no bounding-box API call.
    request = urlsplit(opener.requests[0].full_url)
    assert f"/m/{source.microversion}/e/{source.element_id}/partid/{source.part_id}/stl" in request.path
    assert parse_qs(request.query, keep_blank_values=True) == {
        "configuration": [configuration], "mode": ["binary"], "grouping": ["false"],
        "scale": ["1"], "units": ["millimeter"],
    }


@pytest.mark.parametrize("changes", [
    {"units": "inch"}, {"units": "meter"}, {"units": ["millimeter", "inch"]},
    {"scale": "25.4"}, {"scale": "0.001"}, {"scale": "nan"}, {"scale": []},
    {"documentId": "f" * 24}, {"elementId": "f" * 24}, {"microversion": "f" * 24},
    {"partIds": "OTHER"}, {"configuration": "length=250+mm"}, {"mode": "text"},
])
def test_export_rejects_changed_units_scale_or_source_before_download(changes):
    opener = ExportOpener(changes=changes)
    with pytest.raises(LinkError, match="selected source or units"):
        Client("test-token", opener=opener).export(SOURCE)
    assert len(opener.requests) == 1


@pytest.mark.parametrize("origin", ["https://attacker.example", "http://cad.onshape.com"])
def test_export_does_not_forward_credentials_to_an_untrusted_download(origin):
    opener = ExportOpener(origin=origin)
    with pytest.raises(LinkError, match="unexpected download address"):
        Client("test-token", opener=opener).export(SOURCE)
    assert len(opener.requests) == 1


def test_export_still_rejects_damaged_mesh():
    with pytest.raises(LinkError, match="Incomplete or unsupported STL"):
        Client("test-token", opener=ExportOpener(data=MESH[:-1])).export(SOURCE)
