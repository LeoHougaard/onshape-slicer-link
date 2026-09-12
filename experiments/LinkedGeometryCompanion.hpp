// SPDX-License-Identifier: AGPL-3.0-only
// Desktop-only transport. OAuth credentials never enter the slicer or project.
#pragma once
#include <curl/curl.h>
#include <future>
#include <chrono>
#include <atomic>
#include <wx/progdlg.h>

namespace Slic3r::LinkedGeometry {
inline Json fetch_companion(const Json& sources, wxWindow* parent)
{
    wxString setting;
    require(wxGetEnv("OSL_COMPANION_FILE", &setting),
            "Start the Onshape Slicer Link companion and launch the linked slicer shortcut first.");
    std::ifstream file(std::filesystem::u8path(std::string(setting.utf8_string())), std::ios::binary | std::ios::ate);
    require(bool(file) && file.tellg() > 0 && file.tellg() <= 4096,
            "Companion connection file is missing or invalid. Start the companion first.");
    file.seekg(0);
    const Json connection = Json::parse(file);
    const std::string key = connection.at("key");
    require(connection.at("schema") == 1 && key.size() == 64 &&
            key.find_first_not_of("0123456789abcdef") == std::string::npos, "Invalid companion connection file.");
    require(sources.size() <= 16, "This experiment supports up to 16 distinct Onshape sources per update.");
    const std::string payload = Json({{"schema", 1}, {"sources", sources}}).dump();
    std::atomic<bool> cancel{false};
    wxProgressDialog progress("Update linked parts", "Downloading and validating Onshape geometry...", 100,
                              parent, wxPD_APP_MODAL | wxPD_CAN_ABORT | wxPD_AUTO_HIDE);
    auto work = std::async(std::launch::async, [payload, key, &cancel]() {
        std::unique_ptr<CURL, decltype(&curl_easy_cleanup)> curl(curl_easy_init(), curl_easy_cleanup);
        require(bool(curl), "Cannot initialize the companion connection.");
        curl_slist* list = nullptr;
        list = curl_slist_append(list, "Content-Type: application/json");
        list = curl_slist_append(list, "Host: localhost:8766");
        list = curl_slist_append(list, ("Authorization: Bearer " + key).c_str());
        std::unique_ptr<curl_slist, decltype(&curl_slist_free_all)> headers(list, curl_slist_free_all);
        std::string body;
        auto* handle = curl.get();
        curl_easy_setopt(handle, CURLOPT_URL, "http://127.0.0.1:8766/v1/update");
        curl_easy_setopt(handle, CURLOPT_PROXY, "");
        curl_easy_setopt(handle, CURLOPT_NOPROXY, "*");
        curl_easy_setopt(handle, CURLOPT_FOLLOWLOCATION, 0L);
        curl_easy_setopt(handle, CURLOPT_CONNECTTIMEOUT, 3L);
        curl_easy_setopt(handle, CURLOPT_TIMEOUT, 120L);
        curl_easy_setopt(handle, CURLOPT_NOSIGNAL, 1L);
        curl_easy_setopt(handle, CURLOPT_HTTPHEADER, list);
        curl_easy_setopt(handle, CURLOPT_POSTFIELDS, payload.c_str());
        curl_easy_setopt(handle, CURLOPT_POSTFIELDSIZE, long(payload.size()));
        curl_easy_setopt(handle, CURLOPT_WRITEFUNCTION, +[](char* data, size_t size, size_t count, void* output) -> size_t {
            auto& text = *static_cast<std::string*>(output);
            if (count > (32 * 1024 * 1024 - text.size()) / (size ? size : 1)) return 0;
            try { text.append(data, size * count); } catch (...) { return 0; }
            return size * count;
        });
        curl_easy_setopt(handle, CURLOPT_WRITEDATA, &body);
        curl_easy_setopt(handle, CURLOPT_NOPROGRESS, 0L);
        curl_easy_setopt(handle, CURLOPT_XFERINFOFUNCTION,
            +[](void* flag, curl_off_t, curl_off_t, curl_off_t, curl_off_t) -> int {
                return static_cast<std::atomic<bool>*>(flag)->load() ? 1 : 0;
            });
        curl_easy_setopt(handle, CURLOPT_XFERINFODATA, &cancel);
        const auto result = curl_easy_perform(handle);
        require(!cancel, "Update cancelled. Existing geometry retained.");
        require(result == CURLE_OK, "Cannot reach the companion or the request timed out. Existing geometry retained.");
        long status = 0;
        curl_easy_getinfo(handle, CURLINFO_RESPONSE_CODE, &status);
        const Json response = Json::parse(body);
        if (status != 200) {
            const std::string error = response.value("error", "Companion rejected the update. Existing geometry retained.");
            throw std::runtime_error(error.substr(0, 512));
        }
        return response;
    });
    while (work.wait_for(std::chrono::milliseconds(40)) != std::future_status::ready)
        if (!progress.Pulse()) cancel = true;
    const Json response = work.get();
    require(!cancel, "Update cancelled. Existing geometry retained.");
    require(response.at("schema") == 1 && response.at("snapshots").is_array() &&
            response.at("snapshots").size() == sources.size(), "Incomplete companion response. Existing geometry retained.");
    Json snapshots = Json::object();
    for (size_t i = 0; i < sources.size(); ++i) {
        const Json& snapshot = response.at("snapshots").at(i);
        require(snapshot.at("schema") == 1 && snapshot.at("source_id") == sources.at(i),
                "Companion source mismatch. Existing geometry retained.");
        const std::string revision = snapshot.at("revision");
        require(snapshot.at("units") == "millimeter" && revision.size() == 24 &&
                revision.find_first_not_of("0123456789abcdef") == std::string::npos &&
                snapshot.dump().size() <= 8 * 1024 * 1024,
                "Invalid companion snapshot. Existing geometry retained.");
        snapshots[sources.at(i).get<std::string>()] = snapshot;
    }
    return snapshots;
}
}
