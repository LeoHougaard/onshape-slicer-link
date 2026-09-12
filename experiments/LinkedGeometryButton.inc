// SPDX-License-Identifier: AGPL-3.0-only
// Included in BBLTopbar::Init. Keep updates accessible in narrow windows.
const int linked_update_id = wxWindow::NewControlId();
this->AddSpacer(FromDIP(10));
this->AddTool(linked_update_id, "Update linked parts", wxNullBitmap,
              "Update linked objects on all plates. Does not slice or print.");
this->Bind(wxEVT_AUITOOLBAR_TOOL_DROPDOWN, [](wxAuiToolBarEvent&) {
    if (auto* plater = wxGetApp().plater()) plater->onshape_slicer_link(1);
}, linked_update_id);
this->Bind(wxEVT_UPDATE_UI, [](wxUpdateUIEvent& event) {
    bool linked = false;
    if (auto* plater = wxGetApp().plater())
        for (const auto* object : plater->model().objects)
            if (object->config.has("onshape_slicer_link")) { linked = true; break; }
    event.Enable(linked);
}, linked_update_id);
