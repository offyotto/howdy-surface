# Passkeys Guide

## Local PAM Authentication

`howdy-surface` supports FIDO2/U2F keys through `pam-u2f`.

Install:

```bash
sudo pacman -S pam-u2f
```

Register:

```bash
sudo howdy-surface passkey-enroll --user "$USER" --require-pin
```

Configure Hyprlock:

```bash
sudo howdy-surface pam --services hyprlock --profile strong-passkey
```

The strong profile means:

- your FIDO2 key is required;
- after the key succeeds, Surface IR face auth may unlock immediately;
- if face auth fails, password fallback remains in the PAM stack.

## Browser Passkeys

Use browser passkeys with a hardware security key, phone, or credential manager.

General steps:

1. Install `libfido2`.
2. Plug in your FIDO2 key.
3. Set a FIDO2 PIN with `fido2-token` or the vendor tool.
4. Open a website's account security settings.
5. Choose add passkey or security key.
6. Follow the browser prompt.

The local PAM credential created by `howdy-surface passkey-enroll` is not a
website passkey and is not synced to any browser.
