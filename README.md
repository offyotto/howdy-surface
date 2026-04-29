# howdy-surface

`howdy-surface` is an Arch Linux helper package for Microsoft Surface laptops
that use the 480x480 greyscale Surface IR camera with Howdy.

It provides one command:

```bash
howdy-surface
```

Running it without arguments prints the full setup guide.

## What It Does

- Detects the Surface IR camera with `v4l2-ctl`.
- Configures Howdy to use `/dev/video*` IR capture through ffmpeg.
- Applies the minimal Howdy ffmpeg recorder fixes needed for Surface IR warm-up.
- Configures PAM services such as `hyprlock` with backed-up edits.
- Optionally registers a FIDO2/U2F authenticator through `pam-u2f`.
- Offers a strong PAM profile: FIDO2 required, then Surface IR face auth or password.

## What It Does Not Do

Howdy is not a WebAuthn authenticator, and the Surface IR camera cannot be
turned into a browser passkey provider by this package. Browser passkeys are
created by browsers with a WebAuthn/FIDO2 authenticator, such as a hardware
security key, phone, or credential manager.

For browser passkeys, use a hardware FIDO2 key or another browser-supported
authenticator. The passkey support in this package is PAM-local authentication
via `pam-u2f`.

## Install From This Repo

```bash
git clone https://github.com/offyotto/howdy-surface.git
cd howdy-surface
makepkg -si
```

## Quick Start

```bash
howdy-surface doctor
howdy-surface detect
sudo howdy-surface setup --user "$USER" --services hyprlock
sudo howdy-surface enroll --user "$USER"
sudo howdy-surface benchmark --user "$USER"
```

## FIDO2 / Passkey-Style PAM Setup

Install the optional dependency:

```bash
sudo pacman -S pam-u2f
```

Register a FIDO2 authenticator:

```bash
sudo howdy-surface passkey-enroll --user "$USER" --require-pin
```

Convenience profile, where either Surface IR, FIDO2, or password can unlock:

```bash
sudo howdy-surface pam --services hyprlock --profile face-or-passkey
```

Strong profile, where FIDO2 is required before Surface IR or password:

```bash
sudo howdy-surface pam --services hyprlock --profile strong-passkey
```

Keep a root shell open while changing PAM so you can revert a bad config.

## Security Notes

The strong profile is the recommended high-security local unlock mode:

```pam
auth required pam_u2f.so ...
auth sufficient pam_howdy.so
auth include login
```

That means the FIDO2 authenticator must succeed first. After that, a successful
Surface IR face match can unlock quickly; if face auth fails, the normal
password stack remains available.

The FIDO2 mapping is stored centrally at:

```text
/etc/howdy-surface/u2f_mappings
```

This avoids the encrypted-home deadlock where PAM needs a key mapping inside a
home directory that has not been unlocked yet.

## References

- Yubico `pam-u2f`: https://developers.yubico.com/pam-u2f/
- `pam_u2f` manual: https://developers.yubico.com/pam-u2f/Manuals/pam_u2f.8.html
- MDN passkeys overview: https://developer.mozilla.org/en-US/docs/Web/Security/Authentication/Passkeys

