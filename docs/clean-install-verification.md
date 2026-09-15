# Clean Windows installation test

September 14, 2026. Version 0.3.2 was tested in a newly installed Windows 11
Enterprise Evaluation VM with no Python, source checkout, Slicer Link data, or
copied Onshape credentials. A new OAuth application was created through Onshape's
account settings using the authorized test account.

The release packages came from commit `675ce7bab07950d6cee5632da8477c0b30ce71e0`,
[build 34932056463](https://github.com/LeoHougaard/onshape-slicer-link/actions/runs/34932056463).
The Windows installer SHA-256 is
`718547ec2181da6a654cd13f63104c5edd5a081c3990fc986a069ab2506c4b06`.

Verified in the VM:

- Installed 0.3.0 through its GUI, then upgraded while its wizard was open.
  The installer closed the old wizard and opened the new version.
- Followed Onshape's registration screens, pasted the actual secret and client
  identifier, authorized access, and reached the slicer selection screen.
- Regenerated the VM connection's secret, copied the whole secret sentence, and
  used Paste and Next successfully in the final release package.
- Reopened connection setup with saved credentials. It started at step 1.
  Reusing the saved connection required an explicit choice.
- Installed official OrcaSlicer 2.4.2. Slicer Link detected it, connected an
  Onshape document, listed its Part Studios and solid parts, and exported a real
  part to OrcaSlicer. Its object list showed the linked part on Plate 1.
- Reloaded unfinished browser setup. It started at step 1 and retained the saved
  slicer, document, and part link.

The VM exposed two failures absent from the development environment. Python's
default certificate lookup could not verify Onshape on fresh Windows, reporting
`unable to get local issuer certificate`. The app now uses native certificate
verification through [truststore](https://truststore.readthedocs.io/en/stable/).
The packaged server also tried to load an unused WebSocket implementation. The
local HTTP server now disables that optional protocol.

The Windows automated suite passed 71 tests, including browser interaction,
secret replacement, failure recovery, and retained setup choices. Both release
archives were inspected for their runtime dependencies, including native TLS
verification and Linux password-store support.

This is evidence for the tested Windows installation, not every possible
computer. Linux and Arch execution remain untested, as requested. The VM used
QEMU with an emulated display. OrcaSlicer's 3D viewport stayed blank, and the
slicer exited during the attempted Save, so this VM does not verify rendering
or saved-project behavior. Earlier stock-slicer checks on the host are recorded
separately in [stock verification](stock-verification.md).

The VM used guest-only Windows setup accommodations for
its missing virtual TPM. No host BIOS or Windows feature changes were needed.
