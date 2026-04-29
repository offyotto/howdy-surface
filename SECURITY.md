# Security Model

`howdy-surface` separates convenience from trust.

## Surface IR / Howdy

Howdy is local PAM face authentication. It is useful for fast unlock, but it is
not equivalent to hardware-backed biometric authentication such as Windows Hello
or Face ID. The face match happens in software.

Use Howdy as a local unlock factor, not as the only protection for high-value
data.

## FIDO2 / Passkey-Style PAM

For stronger local authentication, use the `strong-passkey` PAM profile:

```bash
sudo howdy-surface passkey-enroll --user "$USER" --require-pin
sudo howdy-surface pam --services hyprlock --profile strong-passkey
```

This profile requires a registered FIDO2 authenticator before Howdy or password
authentication can satisfy the rest of the stack.

## Browser Passkeys

Browser passkeys are WebAuthn credentials. They are scoped to websites and are
created by a browser through an authenticator. This package cannot make the
Surface IR camera a WebAuthn platform authenticator.

Use a hardware FIDO2 security key, a phone, or a password manager with browser
passkey support for websites.

## PAM Safety

Changing PAM can lock you out. Before applying strong mode:

- keep a root shell open;
- verify `/etc/howdy-surface/u2f_mappings` contains your user;
- test on `hyprlock` before applying to `sudo`;
- keep password fallback available until you have tested reboot and unlock.

Every PAM edit made by this tool creates a timestamped backup next to the
original file.
