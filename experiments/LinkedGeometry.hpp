// SPDX-License-Identifier: AGPL-3.0-only
// Local experiment, shared by the two pinned slicer builds. No network access.
#pragma once
#include "libslic3r/Model.hpp"
#include <nlohmann/json.hpp>
#include <fstream>
#include <filesystem>
#include <map>
#include <stdexcept>

namespace Slic3r::LinkedGeometry {
using Json = nlohmann::json;
inline constexpr const char* key = "onshape_slicer_link";

inline void require(bool condition, const char* message)
{
    if (!condition) throw std::runtime_error(message);
}

inline bool linked(const ModelObject& object) { return object.config.has(key); }
inline bool any_linked(const Model& model)
{
    for (const auto* object : model.objects) if (linked(*object)) return true;
    return false;
}

// Hex keeps the experimental payload safe in both upstream 3MF XML writers.
// The production format should move meshes into dedicated archive members.
inline std::string encode(const Json& data)
{
    constexpr char digits[] = "0123456789abcdef";
    std::string result;
    for (unsigned char c : data.dump()) {
        result += digits[c >> 4]; result += digits[c & 15];
    }
    return result;
}

inline Json state(const ModelObject& object)
{
    const auto* option = dynamic_cast<const ConfigOptionString*>(object.config.option(key));
    require(option != nullptr, "Object has no source link.");
    const auto& encoded = option->value;
    require(encoded.size() <= 32 * 1024 * 1024 && encoded.size() % 2 == 0, "Invalid link metadata size.");
    auto nibble = [](char c) {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'a' && c <= 'f') return c - 'a' + 10;
        throw std::runtime_error("Invalid link metadata encoding.");
    };
    std::string decoded;
    for (size_t i = 0; i < encoded.size(); i += 2)
        decoded += char((nibble(encoded[i]) << 4) | nibble(encoded[i+1]));
    Json result = Json::parse(decoded);
    require(result.at("schema") == 1, "Unsupported link metadata version.");
    return result;
}

inline Json read_snapshot(const std::string& path)
{
    std::ifstream file(std::filesystem::u8path(path), std::ios::binary | std::ios::ate);
    require(bool(file), "Cannot open source snapshot. Existing geometry retained.");
    require(file.tellg() > 0 && file.tellg() <= 8 * 1024 * 1024, "Snapshot exceeds experiment size limit.");
    file.seekg(0);
    Json result = Json::parse(file);
    require(result.at("schema") == 1, "Unsupported snapshot version.");
    require(!result.at("source_id").get<std::string>().empty(), "Missing source identity.");
    require(!result.at("revision").get<std::string>().empty(), "Missing source revision.");
    return result;
}

inline TriangleMesh mesh_from(const Json& snapshot, const Vec3d& frame = Vec3d::Zero())
{
    require(frame.allFinite() && frame.cwiseAbs().maxCoeff() <= 10000, "Invalid stored source frame.");
    const auto& vertices = snapshot.at("vertices");
    const auto& triangles = snapshot.at("triangles");
    require(vertices.is_array() && triangles.is_array() && vertices.size() >= 4 &&
            vertices.size() <= 100000 && triangles.size() >= 4 && triangles.size() <= 200000,
            "Invalid mesh size.");
    indexed_triangle_set its;
    for (const auto& v : vertices) {
        require(v.is_array() && v.size() == 3, "Invalid vertex.");
        Vec3d point(v[0].get<double>(), v[1].get<double>(), v[2].get<double>());
        require(point.allFinite() && point.cwiseAbs().maxCoeff() <= 10000, "Invalid vertex coordinate.");
        its.vertices.push_back((point - frame).cast<float>());
    }
    std::map<std::pair<int, int>, int> edges;
    double volume6 = 0;
    for (const auto& t : triangles) {
        require(t.is_array() && t.size() == 3, "Invalid triangle.");
        for (const auto& index : t)
            require(index.is_number_integer() && index >= 0 && index < vertices.size(),
                    "Triangle index out of bounds or noninteger.");
        decltype(its.indices)::value_type face(t[0].get<int>(), t[1].get<int>(), t[2].get<int>());
        require(face.minCoeff() >= 0 && face.maxCoeff() < int(its.vertices.size()), "Triangle index out of bounds.");
        const Vec3d a = its.vertices[face[0]].cast<double>();
        const Vec3d b = its.vertices[face[1]].cast<double>();
        const Vec3d c = its.vertices[face[2]].cast<double>();
        require((b-a).cross(c-a).squaredNorm() > 1e-12, "Degenerate triangle.");
        volume6 += a.dot(b.cross(c));
        for (int i=0; i<3; ++i) ++edges[{face[i], face[(i+1)%3]}];
        its.indices.push_back(face);
    }
    for (const auto& edge : edges) {
        auto opposite = edges.find({edge.first.second, edge.first.first});
        require(edge.second == 1 && opposite != edges.end() && opposite->second == 1,
                "Mesh is not closed and consistently oriented.");
    }
    require(std::isfinite(volume6) && volume6 > 1e-6, "Mesh has no positive volume.");
    // This bounded experiment does not yet check arbitrary self-intersections.
    return TriangleMesh(std::move(its));
}

inline Json mesh_json(const TriangleMesh& mesh)
{
    Json result = {{"vertices", Json::array()}, {"triangles", Json::array()}};
    for (const auto& v : mesh.its.vertices) result["vertices"].push_back({v.x(), v.y(), v.z()});
    for (const auto& t : mesh.its.indices) result["triangles"].push_back({t.x(), t.y(), t.z()});
    return result;
}

inline void supported(const ModelObject& object)
{
    require(!object.is_cut() && object.volumes.size() == 1 && object.volumes[0]->is_model_part(),
            "The experiment supports one uncut solid volume per object.");
    const auto& v = *object.volumes[0];
    require(v.supported_facets.empty() && v.seam_facets.empty() &&
            v.mmu_segmentation_facets.empty() && v.fuzzy_skin_facets.empty(),
            "Painted objects are not supported. Existing geometry retained.");
    require(object.layer_config_ranges.empty() && object.layer_height_profile.empty(),
            "Variable layer settings are not supported by this experiment.");
}

inline void attach(ModelObject& object, const Json& snapshot, const std::string& path)
{
    supported(object);
    mesh_from(snapshot);
    require(!linked(object), "Object is already linked.");
    auto offset = object.volumes[0]->source.mesh_offset;
    Json data = {{"schema", 1}, {"source_id", snapshot.at("source_id")},
                 {"revision", snapshot.at("revision")}, {"path", path},
                 {"frame", {offset.x(), offset.y(), offset.z()}},
                 {"automatic_updates_paused", false}, {"previous", nullptr}};
    object.config.set_key_value(key, new ConfigOptionString(encode(data)));
}

// Every allocation, parse, mesh check and convex-hull calculation precedes commit.
// The staged Model owns the replacement volume and takes ownership of the old one.
struct Prepared {
    Model staged;
    ModelObject* target = nullptr;
    bool changed = false;

    void commit()
    {
        if (!changed) return;
        auto* replacement = staged.objects.front();
        target->config.assign_config(std::move(replacement->config));
        target->volumes[0]->swap_prepared_geometry(*replacement->volumes[0]);
        changed = false;
    }
};

inline std::unique_ptr<Prepared> prepare(ModelObject& object, const Json* snapshot, bool revert)
{
    supported(object);
    Json data = state(object);
    auto result = std::make_unique<Prepared>();
    result->target = &object;
    TriangleMesh mesh;
    if (revert) {
        require(!data.at("previous").is_null(), "No geometry update to revert.");
        mesh = mesh_from(data.at("previous"));
        data["revision"] = data["previous"].at("revision");
        data["previous"] = nullptr;
        data["automatic_updates_paused"] = true;
    } else {
        require(snapshot != nullptr && snapshot->at("source_id") == data.at("source_id"),
                "Source identity changed. Existing geometry retained.");
        const auto& f = data.at("frame");
        mesh = mesh_from(*snapshot, Vec3d(f.at(0), f.at(1), f.at(2)));
        if (snapshot->at("revision") == data.at("revision")) {
            require(mesh_json(mesh) == mesh_json(object.volumes[0]->mesh()),
                    "Source revision was reused with different geometry.");
            return result;
        }
        data["previous"] = mesh_json(object.volumes[0]->mesh());
        data["previous"]["revision"] = data.at("revision");
        data["revision"] = snapshot->at("revision");
    }
    auto* replacement = result->staged.add_object(object);
    replacement->volumes[0]->set_mesh(std::move(mesh));
    replacement->volumes[0]->calculate_convex_hull();
    replacement->volumes[0]->set_new_unique_id();
    replacement->config.set_key_value(key, new ConfigOptionString(encode(data)));
    result->changed = true;
    return result;
}
} // namespace Slic3r::LinkedGeometry
