// SPDX-License-Identifier: AGPL-3.0-only
// Included at the end of Plater.cpp, where Plater::priv is complete.
#include "LinkedGeometryCompanion.hpp"
namespace Slic3r::GUI {
unsigned onshape_slicer_link_slice_start_count();
void Plater::onshape_slicer_link(int action)
{
    // Progress/error dialogs run a nested event loop. Ignore queued duplicate commands.
    static bool active = false;
    if (active) return;
    active = true;
    struct ResetActive { bool& value; ~ResetActive() { value = false; } } reset_active{active};
    using namespace LinkedGeometry;
    try {
        const unsigned slicing_starts_before = onshape_slicer_link_slice_start_count();
        require(!p->background_process.running() && p->m_worker.is_idle(),
                "Wait for the current slicer operation to finish before updating geometry.");

        auto refresh = [&]() {
            p->update();
            // Apply invalidation and validation without calling restart_background_process.
            p->update_background_process(true);
            p->background_process_timer.Stop();
            require(!p->background_process.running(), "Unexpected background processing after geometry change.");
            require(onshape_slicer_link_slice_start_count() == slicing_starts_before,
                    "Geometry command attempted to start slicing.");
        };

        auto add = [&](const std::string& path) -> size_t {
            Json snapshot = read_snapshot(path);
            Model imported;
            auto* object = imported.add_object();
            object->name = "Linked asymmetric part";
            object->add_volume(mesh_from(snapshot));
            attach(*object, snapshot, path);
            take_snapshot("Add linked part");
            auto indexes = p->load_model_objects(imported.objects);
            require(indexes.size() == 1, "The linked object could not be added.");
            wxGetApp().mainframe->select_tab(this);
            refresh();
            return indexes.front();
        };

        auto update = [&](bool revert) {
            std::vector<std::unique_ptr<Prepared>> changes;
            std::map<std::string, std::pair<std::string, Json>> snapshots;
            Json sources = Json::array();
            for (const auto* object : p->model.objects) {
                if (!linked(*object)) continue;
                supported(*object);
                const std::string source = state(*object).at("source_id");
                if (!revert && source.rfind("onshape-v1:", 0) == 0 &&
                    std::find(sources.begin(), sources.end(), source) == sources.end()) sources.push_back(source);
            }
            // Modal progress keeps plate edits out of the download/validation transaction.
            const Json remote = sources.empty() ? Json::object() : fetch_companion(sources, this);
            // Validate every replacement before touching any linked object.
            for (auto* object : p->model.objects) {
                if (!linked(*object)) continue;
                if (revert) {
                    if (!state(*object).at("previous").is_null())
                        changes.push_back(prepare(*object, nullptr, true));
                } else {
                    const Json link = state(*object);
                    const auto source = link.at("source_id").get<std::string>();
                    const auto path = link.at("path").get<std::string>();
                    auto found = snapshots.find(source);
                    if (found == snapshots.end())
                        found = snapshots.emplace(source, std::make_pair(path,
                            remote.contains(source) ? remote.at(source) : read_snapshot(path))).first;
                    require(remote.contains(source) || found->second.first == path, "One source has conflicting snapshot locations.");
                    auto change = prepare(*object, &found->second.second, false);
                    if (change->changed) changes.push_back(std::move(change));
                }
            }
            if (changes.empty()) return;
            take_snapshot(revert ? "Revert linked geometry" : "Update linked parts");
            for (auto& change : changes) {
                // Retain plate membership, and invalidate every plate containing this object.
                auto it = std::find(p->model.objects.begin(), p->model.objects.end(), change->target);
                int index = int(it - p->model.objects.begin());
                for (int plate = 0; plate < p->partplate_list.get_plate_count(); ++plate)
                    for (int instance = 0; instance < int(change->target->instances.size()); ++instance)
                        if (p->partplate_list.get_plate(plate)->contain_instance(index, instance))
                            p->partplate_list.get_plate(plate)->update_slice_result_valid_state(false);
                change->commit();
            }
            refresh();
        };

        if (action == 0) {
            wxFileDialog dialog(this, "Add local linked part", "", "", "Snapshot JSON (*.json)|*.json", wxFD_OPEN | wxFD_FILE_MUST_EXIST);
            if (dialog.ShowModal() == wxID_OK) add(into_u8(dialog.GetPath()));
        } else if (action == 1 || action == 2) {
            require(any_linked(p->model), "This project has no linked parts.");
            update(action == 2);
        } else if (action == 4) {
            wxString root_value;
            require(wxGetEnv("OSL_EXPERIMENT_DIR", &root_value), "Missing experiment directory.");
            auto root = std::filesystem::u8path(into_u8(root_value));
            require(p->model.objects.size() == 1 && linked(*p->model.objects[0]), "Expected the reopened experiment project.");
            auto* object = p->model.objects[0];
            require(state(*object).at("source_id") == "local:asymmetric-part:configuration-default" &&
                    state(*object).at("revision") == "r1", "Expected the saved reverted local fixture.");
            const auto placement = object->instances[0]->get_matrix();
            const auto volume_frame = object->volumes[0]->get_matrix();
            const auto before_mesh = mesh_json(object->volumes[0]->mesh());
            const int plate = p->partplate_list.find_instance(0, 0);
            require(plate >= 0 && p->partplate_list.get_plate(plate)->is_slice_result_valid(),
                    "Manually slice the reopened test object's plate before checking invalidation.");
            update(false);
            require(state(*object).at("revision") == "r2", "Reopened link did not update.");
            require(object->instances[0]->get_matrix().isApprox(placement) &&
                    object->volumes[0]->get_matrix().isApprox(volume_frame), "Update after reopen changed a transform.");
            require(p->partplate_list.find_instance(0, 0) == plate && plate >= 0, "Reopened plate assignment changed.");
            require(object->config.opt_int("wall_loops") == 7, "Saved settings were lost.");
            require(object->config.opt_float("layer_height") == 0.16 &&
                    object->config.opt_float("sparse_infill_density") == 27 &&
                    object->config.opt_int("extruder") == 1, "Saved process or material settings were lost.");
            require(!p->partplate_list.get_plate(plate)->is_slice_result_valid(), "Previously sliced toolpaths were not invalidated.");
            update(true);
            require(mesh_json(object->volumes[0]->mesh()) == before_mesh, "Revert after GUI reopen failed.");
            Json report = {{"status", "passed"}, {"fresh_process_update_and_revert", true},
                           {"plate", plate}, {"wall_loops", 7},
                           {"previously_sliced_toolpaths_invalidated", true},
                           {"slice_start_attempts", onshape_slicer_link_slice_start_count() - slicing_starts_before}};
            std::ofstream(root / "results" / "gui-reopened-results.json") << report.dump(2) << '\n';
        } else if (action == 3) {
            // Test-only entry point. The finished integration uses the native menu commands above.
            require(p->model.objects.empty(), "Run the experiment in an empty isolated project.");
            wxString root_value;
            require(wxGetEnv("OSL_EXPERIMENT_DIR", &root_value), "Set OSL_EXPERIMENT_DIR to the experiment directory.");
            auto root = std::filesystem::u8path(into_u8(root_value));
            auto fixtures = root / "fixtures";
            auto output = root / "results";
            std::filesystem::create_directories(output);
            std::filesystem::copy_file(fixtures / "r1.json", fixtures / "current.json", std::filesystem::copy_options::overwrite_existing);
            size_t index = add((fixtures / "current.json").u8string());
            auto* object = p->model.objects[index];
            auto original_mesh = mesh_json(object->volumes[0]->mesh());
            const int first_plate = p->partplate_list.get_curr_plate_index();
            require(p->partplate_list.get_plate(first_plate)->contain_instance(int(index), 0), "Add missed the active plate.");
            object->instances[0]->set_rotation(Vec3d(0, 0, 0.645771823));
            object->config.set_key_value("wall_loops", new ConfigOptionInt(4));
            object->config.set_key_value("layer_height", new ConfigOptionFloat(0.16));
            object->config.set_key_value("sparse_infill_density", new ConfigOptionPercent(27));
            object->config.set_key_value("extruder", new ConfigOptionInt(1));
            int second_plate = p->partplate_list.create_plate();
            p->partplate_list.add_to_plate(int(index), 0, second_plate);
            p->partplate_list.select_plate(second_plate);
            const auto before = object->instances[0]->get_matrix();
            auto world_reference = [&]() -> Vec3d {
                return object->instances[0]->get_matrix() * object->volumes[0]->get_matrix() *
                       object->volumes[0]->mesh().its.vertices[0].cast<double>();
            };
            const Vec3d reference = world_reference();
            std::filesystem::copy_file(fixtures / "r2.json", fixtures / "current.json", std::filesystem::copy_options::overwrite_existing);
            update(false);
            const double drift = (world_reference() - reference).norm();
            require(drift < 1e-5 && object->instances[0]->get_matrix().isApprox(before), "Update shifted the rotated part.");
            require(p->partplate_list.get_plate(second_plate)->contain_instance(int(index), 0), "Update changed plate membership.");
            require(!p->partplate_list.get_plate(second_plate)->is_slice_result_valid(), "Toolpaths remain marked valid.");
            require(object->config.opt_int("wall_loops") == 4, "Object override lost.");
            const std::string project = (output / "gui-updated.3mf").u8string();
            export_3mf(boost::filesystem::path(project));
            require(std::filesystem::is_regular_file(std::filesystem::u8path(project)), "GUI project save failed.");
            object->instances[0]->set_offset(object->instances[0]->get_offset() + Vec3d(7, -3, 0));
            object->config.set_key_value("wall_loops", new ConfigOptionInt(7));
            const auto later = object->instances[0]->get_matrix();
            update(true);
            require(mesh_json(object->volumes[0]->mesh()) == original_mesh, "GUI Revert failed.");
            require(object->instances[0]->get_matrix().isApprox(later), "Revert undid later placement.");
            require(object->config.opt_int("wall_loops") == 7, "Revert undid later settings.");
            const auto before_failure = state(*object);
            std::filesystem::copy_file(fixtures / "invalid.json", fixtures / "current.json", std::filesystem::copy_options::overwrite_existing);
            bool rejected = false;
            try { update(false); } catch (...) { rejected = true; }
            require(rejected && state(*object) == before_failure && mesh_json(object->volumes[0]->mesh()) == original_mesh,
                    "Failed update changed the project.");
            std::filesystem::copy_file(fixtures / "r2.json", fixtures / "current.json", std::filesystem::copy_options::overwrite_existing);
            export_3mf(boost::filesystem::path((output / "gui-reverted.3mf").u8string()));
            Json report = {{"status", "passed"}, {"reference_vertex_drift_mm", drift},
                           {"active_plate_add", true}, {"plate_move", true}, {"update", true},
                           {"revert_after_move", true}, {"failure_preserves_project", true},
                           {"slicing_running", p->background_process.running()},
                           {"slice_start_attempts", onshape_slicer_link_slice_start_count() - slicing_starts_before},
                           {"reopen_in_new_process", "pending"}};
            std::ofstream(output / "gui-results.json") << report.dump(2) << '\n';
        }
    } catch (const std::exception& error) {
        if (action == 3 || action == 4) {
            wxString root;
            if (wxGetEnv("OSL_EXPERIMENT_DIR", &root)) {
                auto output = std::filesystem::u8path(into_u8(root)) / "results";
                std::filesystem::create_directories(output);
                std::ofstream(output / (action == 3 ? "gui-results.json" : "gui-reopened-results.json")) << LinkedGeometry::Json({{"status", "failed"}, {"error", error.what()}}).dump(2);
            }
        }
        MessageDialog(this, from_u8(error.what()), "Onshape Slicer Link", wxOK | wxICON_ERROR).ShowModal();
    }
}
} // namespace Slic3r::GUI
