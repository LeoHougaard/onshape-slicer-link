// SPDX-License-Identifier: AGPL-3.0-only
#ifndef NOMINMAX
#define NOMINMAX
#endif
#define NANOSVG_IMPLEMENTATION
#include "nanosvg/nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "nanosvg/nanosvgrast.h"
#include "libslic3r/LinkedGeometry.hpp"
#include "libslic3r/Format/bbs_3mf.hpp"
#include <filesystem>
#include <iostream>

using namespace Slic3r;
using namespace Slic3r::LinkedGeometry;

int main(int argc, char** argv)
{
    try {
        require(argc == 3, "Usage: osl_native_test FIXTURES OUTPUT_DIRECTORY");
        auto fixtures = std::filesystem::u8path(argv[1]);
        auto output = std::filesystem::u8path(argv[2]);
        std::filesystem::create_directories(output);
        Json first = read_snapshot((fixtures / "r1.json").u8string());
        Json second = read_snapshot((fixtures / "r2.json").u8string());
        Model model;
        auto* object = model.add_object();
        object->name = "Identical display name";
        object->add_volume(mesh_from(first));
        object->add_instance();
        object->instances[0]->set_rotation(Vec3d(0.2, -0.3, 0.71));
        object->instances[0]->set_offset(Vec3d(91, 117, 22));
        object->config.set_key_value("wall_loops", new ConfigOptionInt(4));
        object->config.set_key_value("layer_height", new ConfigOptionFloat(0.16));
        object->config.set_key_value("sparse_infill_density", new ConfigOptionPercent(27));
        object->config.set_key_value("extruder", new ConfigOptionInt(2));
        object->volumes[0]->config.set_key_value("extruder", new ConfigOptionInt(2));
        attach(*object, first, (fixtures / "current.json").u8string());
        const auto original_id = object->id();
        const auto transform = object->instances[0]->get_matrix();
        const auto local_transform = object->volumes[0]->get_matrix();
        const auto original_mesh = mesh_json(object->volumes[0]->mesh());
        auto world_reference = [&]() -> Vec3d {
            return object->instances[0]->get_matrix() * object->volumes[0]->get_matrix() *
                   object->volumes[0]->mesh().its.vertices[0].cast<double>();
        };
        const Vec3d reference = world_reference();
        auto* copy = model.add_object(*object);
        copy->instances[0]->set_offset(Vec3d(421, 73, 24));
        auto* unrelated = model.add_object(*object);
        unrelated->config.erase(key);
        const auto unrelated_mesh = mesh_json(unrelated->volumes[0]->mesh());

        auto update = prepare(*object, &second, false);
        require(mesh_json(object->volumes[0]->mesh()) == original_mesh, "Preparation mutated the live mesh.");
        update->commit();
        require(object->id() == original_id, "Object identity changed.");
        require(object->instances[0]->get_matrix().isApprox(transform), "Instance transform changed.");
        require(object->volumes[0]->get_matrix().isApprox(local_transform), "Volume transform changed.");
        const double reference_drift = (world_reference() - reference).norm();
        require(reference_drift < 1e-5, "Rotated reference vertex moved.");
        require(std::abs(TriangleMesh(object->volumes[0]->mesh()).volume() - 3360) < 0.01, "Wrong updated mesh volume.");
        require(object->config.opt_int("wall_loops") == 4 && object->config.opt_int("extruder") == 2,
                "Object settings changed.");
        require(object->config.opt_float("layer_height") == 0.16 &&
                object->config.opt_float("sparse_infill_density") == 27, "Process settings changed.");
        require(object->volumes[0]->config.opt_int("extruder") == 2, "Volume material selection changed.");
        prepare(*copy, &second, false)->commit();
        require(copy->instances[0]->get_offset().isApprox(Vec3d(421, 73, 24)), "Copy placement changed.");
        require(mesh_json(unrelated->volumes[0]->mesh()) == unrelated_mesh, "Unrelated object changed.");

        const auto updated_mesh = mesh_json(object->volumes[0]->mesh());
        const auto updated_state = state(*object);
        Json invalid = second;
        invalid["source_id"] = "local:another-part-with-the-same-name";
        bool failed = false;
        try { prepare(*object, &invalid, false); } catch (...) { failed = true; }
        require(failed && state(*object) == updated_state && mesh_json(object->volumes[0]->mesh()) == updated_mesh,
                "Identity failure mutated object.");
        invalid = second;
        invalid["triangles"][0][0] = 99999;
        failed = false;
        try { prepare(*object, &invalid, false); } catch (...) { failed = true; }
        require(failed && mesh_json(object->volumes[0]->mesh()) == updated_mesh, "Invalid mesh mutated object.");
        require(!prepare(*object, &second, false)->changed, "Same revision should be a no-op.");

        // Later placement edits must survive a dedicated geometry Revert.
        object->instances[0]->set_offset(Vec3d(399, 87, 26));
        object->instances[0]->set_rotation(Vec3d(0.4, 0.1, -0.6));
        object->config.set_key_value("wall_loops", new ConfigOptionInt(6));
        const auto later_transform = object->instances[0]->get_matrix();

        // Use each target's real project writer and reader, including plate records.
        // This model test saves explicit object overrides. The GUI test supplies
        // a real printer profile; synthetic FullPrintConfig defaults in Bambu
        // contain enum vectors without a serialization key map.
        DynamicPrintConfig config;
        config.set_key_value("layer_height", new ConfigOptionFloat(0.20));
        std::cout << "PASS: replacement, source anchor, copies, settings and rejected inputs\n" << std::flush;
        std::set<std::pair<int, int>> plate0_objects = {{1, 0}, {2, 0}};
        std::set<std::pair<int, int>> plate1_objects = {{0, 0}};
        PlateData plate0(0, plate0_objects, false), plate1(1, plate1_objects, false);
        const std::string project = (output / "linked-updated.3mf").u8string();
        StoreParams params;
        params.path = project.c_str(); params.model = &model; params.config = &config;
        params.plate_data_list = {&plate0, &plate1};
        require(store_bbs_3mf(params), "3MF save failed.");
        Model reopened;
        DynamicPrintConfig reopened_config;
        ConfigSubstitutionContext substitutions(ForwardCompatibilitySubstitutionRule::Enable);
        PlateDataPtrs plates;
        std::vector<Preset*> presets;
        bool is_bbl = false;
        Semver version;
#ifdef OSL_ORCA
        bool is_orca = false;
        require(load_bbs_3mf(project.c_str(), &reopened_config, &substitutions, &reopened, &plates,
                            &presets, &is_bbl, &is_orca, &version, nullptr,
                            LoadStrategy::LoadModel | LoadStrategy::LoadConfig), "3MF reopen failed.");
#else
        require(load_bbs_3mf(project.c_str(), &reopened_config, &substitutions, &reopened, &plates,
                            &presets, &is_bbl, &version, nullptr,
                            LoadStrategy::LoadModel | LoadStrategy::LoadConfig), "3MF reopen failed.");
#endif
        require(reopened.objects.size() == 3, "Objects lost on reopen.");
        auto* restored = reopened.objects[0];
        require(state(*restored) == state(*object), "Link or preceding geometry lost on reopen.");
        require(restored->instances[0]->get_matrix().isApprox(later_transform, 1e-5), "Saved placement changed.");
        require(restored->volumes[0]->get_matrix().isApprox(local_transform, 1e-5),
                "3MF reload changed the volume frame; persistent Revert needs frame compensation.");
        require(plates.size() == 2, "Plate records lost.");
        prepare(*restored, nullptr, true)->commit();
        require(mesh_json(restored->volumes[0]->mesh()) == original_mesh, "Revert restored the wrong mesh.");
        require(restored->instances[0]->get_matrix().isApprox(later_transform, 1e-5), "Revert undid later placement.");
        const Vec3d reverted_reference = restored->instances[0]->get_matrix() * restored->volumes[0]->get_matrix() *
                                         restored->volumes[0]->mesh().its.vertices[0].cast<double>();
        const Vec3d expected_reference = later_transform * local_transform *
                                         Vec3d(original_mesh["vertices"][0][0], original_mesh["vertices"][0][1], original_mesh["vertices"][0][2]);
        require((reverted_reference - expected_reference).norm() < 1e-4, "Revert after reopen shifted the source anchor.");
        require(state(*restored).at("automatic_updates_paused") == true, "Revert did not pause automatic updates.");
        require(restored->config.opt_int("wall_loops") == 6, "Revert undid the later wall-count edit.");
        release_PlateData_list(plates);
        Json report = {{"status", "passed"}, {"scope", "native model and 3MF I/O; GUI acceptance still required"},
                       {"reference_vertex_drift_mm", reference_drift},
                       {"checks", {"validated replacement", "rotated source anchor", "independent copy", "object settings",
                                   "wrong identity rejected", "invalid geometry rejected", "3MF round trip",
                                   "revert after later transforms and reopen", "automatic updates paused"}}};
        std::ofstream(output / "native-results.json") << report.dump(2) << '\n';
        std::cout << report.dump(2) << '\n';
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
