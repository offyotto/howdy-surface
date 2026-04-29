# AUR Packaging Notes

This repository is structured like an AUR package source tree.

Build locally:

```bash
makepkg -si
```

Regenerate `.SRCINFO` after changing `PKGBUILD`:

```bash
makepkg --printsrcinfo > .SRCINFO
```

Update checksums after changing packaged source files:

```bash
updpkgsums
```

The package intentionally does not run `howdy-surface setup` in `post_install`.
PAM and Howdy configuration edits must be explicit user actions.
