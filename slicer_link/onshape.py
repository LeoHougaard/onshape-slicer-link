"""On-demand, snapshot-pinned exports. No timers, polling, or per-slicer state."""

import json
import math
import threading
from collections import defaultdict
from dataclasses import replace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .files import atomic_write
from .model import MAX_MESH_BYTES, LinkError, Source, canonical, digest, object_id, require, validate_stl

CAD = "https://cad.onshape.com"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token, record=lambda status: None, opener=None):
        self.token, self.record = token, record
        self.opener = opener or build_opener(NoRedirect)

    def request(self, path, body=None, *, binary=False, expected=None):
        require(path.startswith("/api/"), "Invalid Onshape endpoint.")
        url = CAD + path
        payload = None if body is None else canonical(body).encode()
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/octet-stream" if binary else "application/json",
        }
        if payload:
            headers["Content-Type"] = "application/json"
        for _ in range(3):
            try:
                with self.opener.open(Request(url, data=payload, headers=headers), timeout=45) as response:
                    self.record(response.status)
                    require(response.status == 200, "Unexpected Onshape response.")
                    limit = MAX_MESH_BYTES if binary else 4 * 1024 * 1024
                    data = response.read(limit + 1)
                    require(len(data) <= limit, "Onshape response is too large.")
                    return data if binary else json.loads(data)
            except HTTPError as error:
                self.record(error.code)
                location = error.headers.get("Location", "")
                status = error.code
                error.close()
                if status == 402:
                    raise LinkError(
                        "Onshape's annual API allowance is exhausted. Existing files were retained."
                    ) from None
                if status == 429:
                    raise LinkError("Onshape is rate limiting requests. Wait before trying again.") from None
                if status in {401, 403}:
                    raise LinkError(
                        "Onshape access expired or was revoked. Reconnect your account."
                    ) from None
                if status == 404:
                    raise LinkError("The Onshape source is missing or no longer accessible.") from None
                require(binary and status == 307 and expected, f"Onshape returned HTTP {status}.")
                url = urljoin(url, location)
                parsed = urlsplit(url)
                import re

                require(
                    parsed.scheme == "https"
                    and parsed.hostname
                    and re.fullmatch(r"cad(?:-[a-z0-9]+)?\.onshape\.com", parsed.hostname)
                    and parsed.port in {None, 443}
                    and not parsed.username
                    and not parsed.password
                    and parsed.path == "/modelexport"
                    and not parsed.fragment,
                    "Onshape returned an unexpected download address.",
                )
                query = parse_qs(parsed.query, keep_blank_values=True)
                require(
                    all(query.get(k) == [v] for k, v in expected.items())
                    and query.get("mode") == ["binary"]
                    and query.get("units") == ["millimeter"]
                    and len(query.get("scale", [])) == 1
                    and float(query["scale"][0]) == 1,
                    "Export redirect changed the selected source or units.",
                )
            except (OSError, URLError, TimeoutError, ValueError):
                raise LinkError(
                    "Onshape could not complete the request. Existing files were retained."
                ) from None
        raise LinkError("Onshape redirected the download too many times.")

    def microversion(self, document, workspace):
        result = self.request(
            f"/api/v16/documents/d/{object_id(document)}/w/{object_id(workspace)}/currentmicroversion"
        )
        return object_id(result.get("microversion"))

    def parts(self, source):
        path = f"/api/v16/parts/d/{source.document_id}/m/{source.microversion}/e/{source.element_id}"
        result = self.request(path + "?" + urlencode({"configuration": source.configuration}))
        require(isinstance(result, list), "Onshape did not return a part list.")
        return result

    def translate(self, sources, target):
        first = sources[0]
        path = f"/api/v16/partstudios/d/{first.document_id}/m/{target}/e/{first.element_id}/idtranslations"
        ids = list(dict.fromkeys(source.part_id for source in sources))
        result = self.request(
            path,
            {
                "sourceDocumentMicroversion": first.microversion,
                "sourceConfiguration": first.configuration,
                "targetConfiguration": first.configuration,
                "ids": ids,
            },
        )
        require(
            result.get("documentId") == first.document_id
            and result.get("elementId") == first.element_id
            and result.get("sourceDocumentMicroversion") == first.microversion
            and result.get("targetDocumentMicroversion") == target,
            "Onshape translated a different source snapshot.",
        )
        resolved = {}
        for entry in result.get("ids", []):
            old = entry.get("source")
            targets = entry.get("target")
            require(
                old in ids
                and old not in resolved
                and entry.get("status") == "OK"
                and isinstance(targets, list)
                and len(targets) == 1
                and isinstance(targets[0], str)
                and targets[0],
                "A linked part is missing, split, or ambiguous. Relink it explicitly.",
            )
            resolved[old] = targets[0]
        require(set(resolved) == set(ids), "Onshape did not resolve every linked part.")
        return resolved

    def export(self, source):
        path = (
            f"/api/v16/parts/d/{source.document_id}/m/{source.microversion}/e/{source.element_id}"
            f"/partid/{quote(source.part_id, safe='')}"
        )
        config = {"configuration": source.configuration}
        bounds = self.request(path + "/boundingboxes?" + urlencode(config))
        expected = {
            "documentId": source.document_id,
            "elementId": source.element_id,
            "microversion": source.microversion,
            "partIds": source.part_id,
        }
        if source.configuration:
            expected["configuration"] = source.configuration
        data = self.request(
            path
            + "/stl?"
            + urlencode({**config, "mode": "binary", "grouping": "false", "scale": 1, "units": "millimeter"}),
            binary=True,
            expected=expected,
        )
        metrics = validate_stl(data)
        expected_bounds = [[bounds[end + axis] * 1000 for axis in "XYZ"] for end in ("low", "high")]
        error = max(
            abs(expected_bounds[j][i] - metrics["bounds_mm"][j][i]) for i in range(3) for j in range(2)
        )
        require(math.isfinite(error) and error <= 0.1, "Exported model dimensions differ from Onshape.")
        return data, metrics


class Exporter:
    def __init__(self, store):
        self.store = store
        # One exporter per service process. Serializing exports also coalesces
        # simultaneous Orca/Bambu requests through the persistent revision cache.
        self.lock = threading.RLock()
        self.meshes = store.root / "meshes"

    def refresh(self, owner, client, links):
        with self.lock:
            revisions, translated, groups = {}, {}, defaultdict(list)
            sources = {link["id"]: Source(**link["source"]) for link in links}
            for source in sources.values():
                workspace = source.document_id, source.workspace_id
                if workspace not in revisions:
                    revisions[workspace] = client.microversion(*workspace)
                target = revisions[workspace]
                cache_key = digest((owner + source.key + target).encode())
                if not self.store.get("export", cache_key) and source.microversion != target:
                    groups[
                        source.document_id,
                        source.element_id,
                        source.configuration,
                        source.microversion,
                        target,
                    ].append(source)
            for group, batch in groups.items():
                result = client.translate(batch, group[-1])
                for source in batch:
                    translated[source.key] = result[source.part_id]
            prepared = []
            for link in links:
                source = sources[link["id"]]
                target = revisions[source.document_id, source.workspace_id]
                cache_key = digest((owner + source.key + target).encode())
                cached = self.store.get("export", cache_key)
                if cached and not (self.meshes / (cached["sha256"] + ".stl")).is_file():
                    cached = None
                if not cached:
                    part_id = source.part_id if source.microversion == target else translated.get(source.key)
                    if not part_id:
                        part_id = client.translate([source], target)[source.part_id]
                    resolved = replace(source, microversion=target, part_id=part_id)
                    data, metrics = client.export(resolved)
                    sha = metrics["sha256"]
                    atomic_write(self.meshes / (sha + ".stl"), data)
                    cached = {"sha256": sha, "revision": target, "part_id": part_id, **metrics}
                    self.store.put("export", cache_key, owner, cached)
                prepared.append(
                    {
                        **link,
                        "sha256": cached["sha256"],
                        "revision": target,
                        "resolved_part_id": cached["part_id"],
                        "bounds_mm": cached["bounds_mm"],
                    }
                )
            return prepared
