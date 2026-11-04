## Summary

Describe the behavior change and which install profiles/components it affects.

## Validation

- [ ] Added or updated an offline regression test for behavior changes.
- [ ] `python3 -m unittest discover -s tests -v` passes.
- [ ] Python entry points compile and shell scripts pass `bash -n`.
- [ ] Installer smoke tests pass for affected profiles.
- [ ] User systemd units verify when service definitions change.
- [ ] Documentation and support boundaries are updated.
- [ ] No user configuration, credentials, machine-specific paths, or generated caches are committed.
- [ ] Optional features remain optional; no implicit root or sandbox-permission changes were introduced.

## Manual testing (if applicable)

List the distribution, desktop/session, client packaging, optical drive, and tests performed. Clearly mark anything not tested on real hardware.
