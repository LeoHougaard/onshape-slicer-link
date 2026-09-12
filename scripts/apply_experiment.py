"""Apply the bounded native experiment to the pinned checkouts. Idempotent.

SPDX-License-Identifier: AGPL-3.0-only
"""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def copy_if_changed(source, destination, prefix=b''):
    content = prefix + source.read_bytes()
    if not destination.exists() or destination.read_bytes() != content:
        destination.write_bytes(content)


def replace(path, old, new):
    text = path.read_text(encoding='utf-8')
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'Expected exactly one anchor in {path}: {old[:70]}')
    path.write_text(text.replace(old, new), encoding='utf-8', newline='\n')


def apply(target, wx33=False):
    root = ROOT / 'external' / target
    expected = json.loads((ROOT / 'sources.lock.json').read_text())[target]['commit']
    actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != expected:
        raise RuntimeError(f'{target}: expected pinned commit {expected}, found {actual}')
    copy_if_changed(ROOT / 'experiments/LinkedGeometry.hpp', root / 'src/libslic3r/LinkedGeometry.hpp')
    copy_if_changed(ROOT / 'experiments/LinkedGeometryGui.inc', root / 'src/slic3r/GUI/LinkedGeometryGui.inc')
    copy_if_changed(ROOT / 'experiments/LinkedGeometryCompanion.hpp', root / 'src/slic3r/GUI/LinkedGeometryCompanion.hpp')
    copy_if_changed(ROOT / 'experiments/LinkedGeometryButton.inc', root / 'src/slic3r/GUI/LinkedGeometryButton.inc')
    background = root / 'src/slic3r/GUI/BackgroundSlicingProcess.cpp'
    text = background.read_text(encoding='utf-8')
    if 'onshape_slicer_link_slice_start_count' not in text:
        text = '''#include <atomic>
namespace Slic3r::GUI {
static std::atomic<unsigned> osl_slice_starts{0};
unsigned onshape_slicer_link_slice_start_count() { return osl_slice_starts.load(); }
}
''' + text
        anchor = 'bool BackgroundSlicingProcess::start()\n{'
        if text.count(anchor) != 1:
            raise RuntimeError(f'Could not locate slicing start in {target}')
        text = text.replace(anchor, anchor + '\n    ++osl_slice_starts; // OSL experiment instrumentation')
        background.write_text(text, encoding='utf-8', newline='\n')
    plater = root / 'src/slic3r/GUI/Plater.cpp'
    text = plater.read_text(encoding='utf-8')
    if '#include "libslic3r/LinkedGeometry.hpp"' not in text:
        text = '#include "libslic3r/LinkedGeometry.hpp"\n' + text
        text += '\n#include "LinkedGeometryGui.inc"\n'
        plater.write_text(text, encoding='utf-8', newline='\n')
    replace(plater, '    bool background_processing_enabled() const {',
            '''    bool background_processing_enabled() const {
        // Linked projects require explicit slicing, including after later plate edits.
        if (LinkedGeometry::any_linked(model)) return false;''')
    if target == 'orca':
        for method in ('schedule_auto_reslice_if_needed', 'trigger_auto_reslice_now'):
            replace(plater, f'void Plater::priv::{method}()\n{{',
                    f'''void Plater::priv::{method}()
{{
    if (LinkedGeometry::any_linked(model)) {{
        auto_reslice_timer.Stop();
        auto_reslice_pending = false;
        auto_reslice_after_cancel = false;
        return;
    }}''')
    declaration = root / 'src/slic3r/GUI/Plater.hpp'
    text = declaration.read_text(encoding='utf-8')
    if 'void onshape_slicer_link(int action);' not in text:
        import re
        text, count = re.subn(r'(\s+void\s+reload_from_disk\(\);)',
                             r'\n    void onshape_slicer_link(int action); // Local experiment\1', text)
        if count != 1:
            raise RuntimeError(f'Could not locate Plater declaration in {target}')
        declaration.write_text(text, encoding='utf-8', newline='\n')
    frame = root / 'src/slic3r/GUI/MainFrame.cpp'
    # Migrate the prototype button out of the crowded Slice/Print row.
    text = frame.read_text(encoding='utf-8')
    if '#include "LinkedGeometryButton.inc"\n' in text:
        frame.write_text(text.replace('#include "LinkedGeometryButton.inc"\n', ''), encoding='utf-8', newline='\n')
    replace(root / 'src/slic3r/GUI/BBLTopbar.cpp',
            '    m_redo_item->SetDisabledBitmap(redo_inactive_bitmap);',
            '    m_redo_item->SetDisabledBitmap(redo_inactive_bitmap);\n#include "LinkedGeometryButton.inc"')
    text = frame.read_text(encoding='utf-8')
    if '// OSL native menu' not in text:
        anchor = '    wxMenu* fileMenu = new wxMenu;'
        menu = '''
    // OSL native menu. Fixed IDs also allow the isolated GUI test to invoke these commands.
    if (m_plater != nullptr) {
        auto* link_menu = new wxMenu;
        append_menu_item(link_menu, wxID_HIGHEST + 871, "Add local linked part...", "", [this](wxCommandEvent&) { m_plater->onshape_slicer_link(0); });
        append_menu_item(link_menu, wxID_HIGHEST + 872, "Update linked parts", "", [this](wxCommandEvent&) { m_plater->onshape_slicer_link(1); });
        append_menu_item(link_menu, wxID_HIGHEST + 873, "Revert linked geometry", "", [this](wxCommandEvent&) { m_plater->onshape_slicer_link(2); });
        append_menu_item(link_menu, wxID_HIGHEST + 874, "Run local experiment", "", [this](wxCommandEvent&) { m_plater->onshape_slicer_link(3); });
        fileMenu->AppendSubMenu(link_menu, "Onshape Slicer Link");
        fileMenu->AppendSeparator();
    }
'''
        text = text.replace(anchor, anchor + menu, 1)
        frame.write_text(text, encoding='utf-8', newline='\n')
    if 'wxID_HIGHEST + 875' not in frame.read_text(encoding='utf-8'):
        replace(frame,
                '        fileMenu->AppendSubMenu(link_menu, "Onshape Slicer Link");',
                '        append_menu_item(link_menu, wxID_HIGHEST + 875, "Check reopened experiment", "", [this](wxCommandEvent&) { m_plater->onshape_slicer_link(4); });\n        fileMenu->AppendSubMenu(link_menu, "Onshape Slicer Link");')
    content = frame.read_text(encoding='utf-8')
    updated = content
    for action in range(5):
        updated = updated.replace(f'm_plater->onshape_slicer_link({action}); }});',
                                  f'm_plater->onshape_slicer_link({action}); }}, "", this);')
    if updated != content:
        frame.write_text(updated, encoding='utf-8', newline='\n')
    replace(root / 'src/libslic3r/Model.hpp',
            '    void                calculate_convex_hull();',
            '''    // OSL experiment: commit a fully validated mesh without changing its frame or settings.
    void swap_prepared_geometry(ModelVolume& prepared) {
        m_mesh.swap(prepared.m_mesh);
        m_convex_hull.swap(prepared.m_convex_hull);
        m_convex_hull_2d.clear();
        m_cached_2d_polygon.clear();
        set_new_unique_id();
        object->invalidate_bounding_box();
    }
    void                calculate_convex_hull();''')
    replace(root / 'src/libslic3r/PrintConfig.cpp',
            '    def = this->add("print_settings_id", coString);',
            '''    // OSL experiment: project-persisted object metadata, not a print setting.
    def = this->add("onshape_slicer_link", coString);
    def->set_default_value(new ConfigOptionString(""));
    def->cli = ConfigOptionDef::nocli;

    def = this->add("print_settings_id", coString);''')
    archive = root / 'src/libslic3r/Format/bbs_3mf.cpp'
    replace(archive, '            if (o->volumes.size() == 1) {',
            '            if (o->volumes.size() == 1 && !o->config.has("onshape_slicer_link")) {')
    if target == 'orca':
        content = archive.read_text(encoding='utf-8')
        old = 'object.add_volume(std::move(triangle_mesh));'
        if old in content:
            archive.write_text(content.replace(old,
                'object.add_volume(std::move(triangle_mesh), ModelVolumeType::MODEL_PART, !object.config.has("onshape_slicer_link"));'), encoding='utf-8', newline='\n')
    else:
        replace(archive,
                '                bool modify_to_center_geometry = is_text ? false : true;//text do not modify_to_center_geometry',
                '                bool modify_to_center_geometry = !is_text && !object.config.has("onshape_slicer_link");')
    # The native test uses the exact same libslic3r implementation as the GUI.
    copy_if_changed(ROOT / 'experiments/native_test.cpp', root / 'src/osl_native_test.cpp',
                    b'#define OSL_ORCA 1\n' if target == 'orca' else b'')
    copy_if_changed(ROOT / 'experiments/native_crash.cpp', root / 'src/osl_native_crash.cpp')
    cmake = root / 'src/CMakeLists.txt'
    if target == 'bambu':
        replace(root / 'src/slic3r/CMakeLists.txt',
                'target_include_directories(libslic3r_gui PRIVATE Utils)',
                '''target_include_directories(libslic3r_gui PRIVATE Utils)
if(OSL_EXTRA_INCLUDE_DIR)
    target_include_directories(libslic3r_gui PRIVATE "${OSL_EXTRA_INCLUDE_DIR}")
endif()''')
    if target == 'bambu' and wx33:
        replace(root / 'src/BambuStudio.cpp',
                '    #include <wchar.h>',
                '    #include <wchar.h>\n    #include <commctrl.h>')
        for filename, timer in (
            ('CalibrationPanel.cpp', 'm_refresh_timer'),
            ('MultiMachinePage.cpp', 'm_refresh_timer'),
            ('MultiMachineManagerPage.cpp', 'm_flipping_timer'),
            ('MultiTaskManagerPage.cpp', 'm_flipping_timer'),
            ('SendMultiMachinePage.cpp', 'm_refresh_timer'),
        ):
            path = root / 'src/slic3r/GUI' / filename
            content = path.read_text(encoding='utf-8')
            updated = content.replace('wxTimerEvent()', f'wxTimerEvent(*{timer})')
            updated = updated.replace('AmsRadioSelectorList::Node*', 'AmsRadioSelectorList::compatibility_iterator')
            if updated != content:
                path.write_text(updated, encoding='utf-8', newline='\n')
        replace(root / 'src/slic3r/GUI/Search.cpp',
                'return marker_by_type(opt.type, printer_technology) + opt.category_local',
                'return std::wstring(1, marker_by_type(opt.type, printer_technology)) + opt.category_local')
        for filename in ('Preferences.cpp', 'Plater.cpp'):
            path = root / 'src/slic3r/GUI' / filename
            content = path.read_text(encoding='utf-8')
            if 'RadioSelectorList::Node *' in content:
                path.write_text(content.replace('RadioSelectorList::Node *', 'RadioSelectorList::compatibility_iterator '), encoding='utf-8', newline='\n')
        gui = root / 'src/slic3r/GUI/GUI.cpp'
        content = gui.read_text(encoding='utf-8')
        old_cast = 'wxDynamicCast(comboCtrl->GetPopupControl(), wxCheckListBoxComboPopup)'
        if old_cast in content:
            gui.write_text(content.replace(old_cast, 'dynamic_cast<wxCheckListBoxComboPopup*>(comboCtrl->GetPopupControl())'), encoding='utf-8', newline='\n')
        replace(root / 'src/slic3r/GUI/GUI_App.cpp',
                '    if (WXHWND wxHWND = wxToolTip::GetToolTipCtrl())\n        NppDarkMode::SetDarkExplorerTheme((HWND)wxHWND);',
                '#if !wxCHECK_VERSION(3, 3, 0)\n    if (WXHWND wxHWND = wxToolTip::GetToolTipCtrl())\n        NppDarkMode::SetDarkExplorerTheme((HWND)wxHWND);\n#endif')
        grid = root / 'src/slic3r/GUI/ImageGrid.cpp'
        replace(grid,
                '            renderButtons(dc, {_L("Delete"), (wxChar const *) secondAction, thirdAction.IsEmpty() ? nullptr : (wxChar const *) thirdAction, nullptr}, rect,',
                '            wxStringList buttons;\n            buttons.Add(_L("Delete").wc_str());\n            buttons.Add(secondAction.wc_str());\n            if (!thirdAction.IsEmpty()) buttons.Add(thirdAction.wc_str());\n            renderButtons(dc, buttons, rect,')
        replace(grid,
                '            renderButtons(dc, {(wxChar const *) nonHoverText, nullptr}, rect, -1, states);',
                '            wxStringList buttons;\n            buttons.Add(nonHoverText.wc_str());\n            renderButtons(dc, buttons, rect, -1, states);')
        replace(root / 'src/slic3r/GUI/AboutDialog.cpp',
                '                    find_txt += std::string("\\n") + text_list[i][o];',
                '                    find_txt += "\\n";\n                    find_txt += text_list[i][o];')
        replace(root / 'src/slic3r/GUI/Widgets/Button.cpp',
                '    state_handler.attach({&text_color});',
                '    state_handler.attach(text_color);')
        webview = root / 'src/slic3r/GUI/Widgets/WebView.cpp'
        replace(webview, 'class WebViewEdge : public wxWebViewEdge\n{\npublic:',
                'class WebViewEdge : public wxWebViewEdge\n{\npublic:\n    using wxWebViewEdge::wxWebViewEdge;')
        replace(webview,
                '    wxWebView* webView = new WebViewEdge;\n    webView->SetUserDataPathOption(BuildEdgeUserDataPath());',
                '    auto web_config = wxWebView::NewConfiguration(wxWebViewBackendEdge);\n    web_config.SetDataPath(BuildEdgeUserDataPath());\n    wxWebView* webView = new WebViewEdge(web_config);')
        replace(cmake,
                '        find_package(wxWidgets 3.1 REQUIRED COMPONENTS html adv gl core base webview aui net media richtext xml)',
                '        find_package(wxWidgets 3.3 CONFIG REQUIRED COMPONENTS html adv gl core base webview aui net media richtext xml)')
        replace(cmake, '    include(${wxWidgets_USE_FILE})',
                '    if(wxWidgets_USE_FILE)\n        include(${wxWidgets_USE_FILE})\n    endif()')
    text = cmake.read_text(encoding='utf-8')
    updated = text.split('# OSL experiment tests')[0].rstrip() + '''

# OSL experiment tests
add_executable(osl_native_test osl_native_test.cpp osl_native_crash.cpp)
target_sources(osl_native_test PRIVATE slic3r/Utils/Http.cpp)
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/slic3r/Utils/BBLUtil.cpp")
    target_sources(osl_native_test PRIVATE slic3r/Utils/BBLUtil.cpp)
endif()
target_link_libraries(osl_native_test PRIVATE libslic3r libcurl OpenSSL::SSL OpenSSL::Crypto)
if(WIN32)
    target_link_libraries(osl_native_test PRIVATE bcrypt)
    target_compile_options(osl_native_test PRIVATE /Zi)
    target_link_options(osl_native_test PRIVATE /DEBUG)
endif()
target_include_directories(osl_native_test PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
'''
    if updated != text:
        cmake.write_text(updated, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wx33', action='store_true', help='Use the existing wxWidgets 3.3 dependency prefix for Bambu too')
    args = parser.parse_args()
    for target in ('orca', 'bambu'):
        apply(target, args.wx33)
