import tkinter as tk

import pytest

from slicer_link.model import LinkError
from slicer_link.setup import REDIRECT, SetupWizard


@pytest.fixture(scope="module")
def tk_application():
    window = tk.Tk()
    window.withdraw()
    yield window
    window.destroy()


@pytest.fixture
def root(tk_application):
    window = tk.Toplevel(tk_application)
    window.withdraw()
    yield window
    try:
        window.destroy()
    except tk.TclError:
        pass


def test_wizard_back_copy_and_cancel_do_not_save_credentials(root):
    writes = []
    wizard = SetupWizard(root, writes.append)
    wizard.advance()
    identifier = wizard.identifier
    wizard.previous()
    wizard.advance()
    assert wizard.identifier == identifier
    wizard.advance()
    # Exercise the real Copy button in the redirect row.
    row = next(child for child in wizard.content.winfo_children() if child.winfo_class() == "TFrame")
    button = next(child for child in row.winfo_children() if child.winfo_class() == "TButton")
    button.invoke()
    assert root.clipboard_get() == REDIRECT
    wizard.advance()
    wizard.client_secret.set("test-secret-not-a-credential")
    wizard.advance()
    wizard.previous()
    assert wizard.client_secret.get() == "test-secret-not-a-credential"
    root.destroy()
    assert writes == [] and wizard.result is None


def test_wizard_validates_then_retries_locked_store_without_losing_existing_key(root):
    writes = []
    locked = True

    def save(value):
        if locked:
            raise LinkError("Unlock your desktop password store and retry.")
        writes.append(value)

    old = {"key": "existing-encryption-key", "control": "existing-control-token", "owner": "old-owner"}
    wizard = SetupWizard(root, save, existing=old)
    wizard.use_existing()
    wizard.advance()
    assert wizard.step == 3 and not writes
    wizard.client_secret.set("incomplete key")
    wizard.advance()
    assert wizard.step == 3
    assert "spaces or line breaks" in wizard.message.get()
    wizard.client_secret.set("test-secret-not-a-credential")
    wizard.advance()
    wizard.advance()
    assert wizard.step == 4 and not writes
    wizard.client_id.set("test-client-id")
    wizard.advance()
    assert "Unlock" in wizard.message.get() and not writes
    assert root.winfo_exists()
    locked = False
    wizard.advance()
    assert len(writes) == 1 and wizard.result == writes[0]
    assert writes[0]["key"] == old["key"] and writes[0]["control"] == old["control"]
    assert writes[0]["owner"] == ""  # A changed client must authorize a fresh grant.
    assert old["owner"] == "old-owner"


def test_paste_replaces_saved_secret_and_next_button_advances(root):
    writes = []
    wizard = SetupWizard(root, writes.append, existing={"client_id": "old-id", "client_secret": "old-secret"})
    assert wizard.step == 0
    wizard.use_existing()
    root.clipboard_clear()
    root.clipboard_append(" \r\ntest-new-secret\r\n ")
    row = next(child for child in wizard.content.winfo_children() if child.winfo_class() == "TFrame")
    next(child for child in row.winfo_children() if child.winfo_class() == "TButton").invoke()
    assert wizard.client_secret.get() == "test-new-secret"
    wizard.next.invoke()
    assert wizard.step == 4 and not writes
    wizard.previous()
    assert wizard.client_secret.get() == "test-new-secret"


def test_saved_details_never_skip_the_start_and_new_registration_clears_them(root):
    old = {"client_id": "old-id", "client_secret": "old-secret", "key": "keep-encryption"}
    wizard = SetupWizard(root, lambda _: None, existing=old)
    assert wizard.step == 0
    wizard.use_existing()
    assert wizard.step == 3 and "Step 2 of 3" in wizard.progress.cget("text")
    wizard.previous()
    assert wizard.step == 0
    wizard.next.invoke()
    assert wizard.step == 1
    assert not wizard.client_id.get() and not wizard.client_secret.get()
    assert wizard.existing == old


@pytest.mark.parametrize(
    "value, message",
    [
        ("", "empty"),
        ("OAuth secret key: example", "spaces or line breaks"),
        ("wrapped\r\nsecret", "spaces or line breaks"),
        ("hidden\u00a0space", "spaces or line breaks"),
        ("********", "hidden key"),
        ("https://cad.onshape.com", "address"),
        ('"quoted-secret"', "quoted text"),
    ],
)
def test_invalid_paste_explains_correction_without_revealing_value(root, value, message):
    wizard = SetupWizard(root, lambda _: pytest.fail("Invalid input saved"))
    wizard.use_existing()
    wizard.client_secret.set(value)
    wizard.next.invoke()
    assert wizard.step == 3 and message in wizard.message.get()
    assert not value or value not in wizard.message.get()


def test_same_key_in_both_fields_is_rejected(root):
    wizard = SetupWizard(root, lambda _: pytest.fail("Same key saved twice"))
    wizard.use_existing()
    wizard.client_secret.set("example-test-key")
    wizard.next.invoke()
    wizard.client_id.set("example-test-key")
    wizard.next.invoke()
    assert wizard.step == 4 and "same value" in wizard.message.get()


@pytest.mark.parametrize("scaling", [96 / 72, 144 / 72])
def test_navigation_and_error_stay_visible_at_desktop_scaling(root, scaling):
    original = root.tk.call("tk", "scaling")
    try:
        root.tk.call("tk", "scaling", scaling)
        wizard = SetupWizard(root, lambda _: None)
        root.deiconify()
        for step in range(5):
            wizard.step = step
            wizard.render()
            if step >= 3:
                wizard.next.invoke()
            root.update()
            assert wizard.next.winfo_ismapped()
            assert wizard.back.winfo_ismapped()
            assert (
                wizard.next.winfo_rooty() + wizard.next.winfo_height()
                <= root.winfo_rooty() + root.winfo_height()
            )
            for child in wizard.content.winfo_children():
                assert child.winfo_ismapped()
                assert child.winfo_y() + child.winfo_height() <= wizard.content.winfo_height()
    finally:
        root.tk.call("tk", "scaling", original)
