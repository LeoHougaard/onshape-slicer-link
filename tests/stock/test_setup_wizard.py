import tkinter as tk

import pytest

from slicer_link.model import LinkError
from slicer_link.setup import REDIRECT, SetupWizard


@pytest.fixture
def root():
    window = tk.Tk()
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
