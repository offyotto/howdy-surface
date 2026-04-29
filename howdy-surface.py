#!/usr/bin/env python3
"""Surface IR camera helper for Howdy on Arch Linux."""

from __future__ import annotations

import argparse
import glob
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


APP = "howdy-surface"
CONFIG = Path("/etc/howdy/config.ini")
FFMPEG_READER = Path("/usr/lib/howdy/recorders/ffmpeg_reader.py")
PAM_DIR = Path("/etc/pam.d")
STATE_DIR = Path("/etc/howdy-surface")
U2F_MAPPING = STATE_DIR / "u2f_mappings"
DEFAULT_ORIGIN = "pam://howdy-surface"
GUIDE = r"""
howdy-surface

Purpose
  Configure Microsoft Surface IR cameras for Howdy on Arch Linux, then
  optionally add FIDO2/U2F passkey-style PAM authentication with pam-u2f.

Quick start
  1. Inspect the system:
       howdy-surface doctor

  2. Detect the Surface IR camera:
       howdy-surface detect

  3. Configure Howdy for the Surface IR camera and Hyprlock:
       sudo howdy-surface setup --user "$USER" --services hyprlock

  4. Enroll your face after setup:
       sudo howdy-surface enroll --user "$USER"

  5. Benchmark direct Howdy matching:
       sudo howdy-surface benchmark --user "$USER"

Passkey-style PAM support
  Browser passkeys are WebAuthn/FIDO2 credentials. Howdy cannot become a
  browser platform authenticator. This tool supports FIDO2 security keys for
  PAM via pam-u2f, using a root-owned central mapping file so encrypted home
  setups do not break login.

  Install optional dependency:
       sudo pacman -S pam-u2f

  Register a FIDO2 authenticator for PAM:
       sudo howdy-surface passkey-enroll --user "$USER" --require-pin

  Convenience profile, face OR FIDO2 OR password fallback:
       sudo howdy-surface pam --services hyprlock --profile face-or-passkey

  Strong profile, FIDO2 required, then face OR password:
       sudo howdy-surface pam --services hyprlock --profile strong-passkey

Browser passkey guide
       howdy-surface browser-passkeys

Safety model
  - All /etc edits are backed up with a timestamp.
  - PAM changes are explicit commands, not package install hooks.
  - strong-passkey refuses to install unless the user has a central FIDO2
    mapping in /etc/howdy-surface/u2f_mappings.
  - Keep a root shell open when changing PAM.
"""


def run(cmd: list[str], check: bool = False, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def require_root() -> None:
    if os.geteuid() != 0:
        raise SystemExit("This command needs root. Re-run it with sudo.")


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def timestamp() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def backup(path: Path) -> Path:
    if not path.exists():
        raise SystemExit(f"Cannot back up missing file: {path}")
    dst = path.with_name(f"{path.name}.bak.{APP}.{timestamp()}")
    shutil.copy2(path, dst)
    return dst


def user_exists(user: str) -> None:
    try:
        pwd.getpwnam(user)
    except KeyError as exc:
        raise SystemExit(f"User does not exist: {user}") from exc


def print_command_result(label: str, ok: bool, detail: str = "") -> None:
    state = "ok" if ok else "missing"
    suffix = f" - {detail}" if detail else ""
    print(f"{label:24} {state}{suffix}")


def detect_ir_camera() -> dict[str, str] | None:
    best: tuple[int, dict[str, str]] | None = None

    for dev in sorted(glob.glob("/dev/video*")):
        all_info = run(["v4l2-ctl", "--device", dev, "--all"])
        fmt_info = run(["v4l2-ctl", "--device", dev, "--list-formats-ext"])
        text = f"{all_info.stdout}\n{all_info.stderr}\n{fmt_info.stdout}\n{fmt_info.stderr}"

        if all_info.returncode != 0 and fmt_info.returncode != 0:
            continue

        card = ""
        m = re.search(r"Card type\s*:\s*(.+)", text)
        if m:
            card = m.group(1).strip()

        width = height = fps = ""
        size = re.search(r"(\d{3,4})x(\d{3,4})", text)
        if size:
            width, height = size.group(1), size.group(2)
        rate = re.search(r"(\d+(?:\.\d+)?)\s*fps|Frames per second:\s*(\d+(?:\.\d+)?)", text)
        if rate:
            fps = next(x for x in rate.groups() if x)

        upper = text.upper()
        score = 0
        if "SURFACE" in upper:
            score += 30
        if "SURFACE I" in upper or "IR" in upper:
            score += 30
        if "GREY" in upper or "GRAY" in upper:
            score += 25
        if "480X480" in upper:
            score += 20
        if "60.000" in upper or "60 FPS" in upper:
            score += 10

        candidate = {
            "device": dev,
            "card": card or "unknown",
            "width": width or "480",
            "height": height or "480",
            "fps": fps or "60",
            "score": str(score),
        }
        if best is None or score > best[0]:
            best = (score, candidate)

    if best and best[0] >= 45:
        return best[1]
    return None


def cmd_detect(_: argparse.Namespace) -> None:
    camera = detect_ir_camera()
    if not camera:
        raise SystemExit("No likely Surface IR camera found.")
    for key in ("device", "card", "width", "height", "fps", "score"):
        print(f"{key}={camera[key]}")


def edit_key_values(path: Path, values: dict[str, str]) -> Path:
    before = path.read_text()
    changed: set[str] = set()
    out: list[str] = []

    for line in before.splitlines(True):
        stripped = line.strip()
        replaced = False
        for key, value in values.items():
            if stripped.startswith(f"{key} =") or stripped.startswith(f"{key}="):
                newline = "\n" if line.endswith("\n") else ""
                out.append(f"{key} = {value}{newline}")
                changed.add(key)
                replaced = True
                break
        if not replaced:
            out.append(line)

    missing = sorted(set(values) - changed)
    if missing:
        raise SystemExit(f"Could not find config keys in {path}: {', '.join(missing)}")

    saved = backup(path)
    path.write_text("".join(out))
    return saved


def patch_ffmpeg_reader() -> Path | None:
    if not FFMPEG_READER.exists():
        raise SystemExit(f"Howdy ffmpeg recorder not found: {FFMPEG_READER}")

    text = FFMPEG_READER.read_text()
    original = text

    text = text.replace(
        "def __init__(self, device_path, device_format, numframes=10):",
        "def __init__(self, device_path, device_format, numframes=30):",
    )
    text = text.replace(
        "if self.video == ():",
        "if isinstance(self.video, tuple) and self.video == ():",
    )
    text = text.replace("return 0, self.video\n", "return True, self.video[self.num_frames_read]\n")
    text = text.replace(
        "return 0, self.video[self.num_frames_read]\n",
        "return True, self.video[self.num_frames_read]\n",
    )

    marker = "self.num_frames_read = min(14, len(self.video) - 1)"
    if marker not in text:
        pattern = (
            r"(\n[ \t]*self\.video = \(\n"
            r"[ \t]*numpy\n"
            r"[ \t]*\.frombuffer\(stream, numpy\.uint8\)\n"
            r"[ \t]*\.reshape\(\[-1, self\.width, self\.height, 3\]\)\n"
            r"[ \t]*\)\n)"
        )

        def add_skip(match: re.Match[str]) -> str:
            block = match.group(1)
            indent = re.search(r"\n([ \t]*)self\.video", block).group(1)  # type: ignore[union-attr]
            return f"{block}{indent}{marker}\n"

        text, count = re.subn(pattern, add_skip, text, count=1)
        if count != 1:
            raise SystemExit("Could not locate ffmpeg_reader video buffer assignment to patch.")

    if text == original:
        return None

    saved = backup(FFMPEG_READER)
    FFMPEG_READER.write_text(text)
    compile_check = run([sys.executable, "-m", "py_compile", str(FFMPEG_READER)])
    if compile_check.returncode != 0:
        FFMPEG_READER.write_text(original)
        raise SystemExit(
            "Patched ffmpeg_reader.py did not compile; restored original.\n"
            + compile_check.stderr
        )
    return saved


def has_u2f_mapping(user: str) -> bool:
    if not U2F_MAPPING.exists():
        return False
    for line in U2F_MAPPING.read_text().splitlines():
        if line.startswith(f"{user}:") and len(line.split(":", 1)[1]) > 10:
            return True
    return False


def pam_block(profile: str, user: str, origin: str) -> list[str]:
    u2f = (
        "auth sufficient pam_u2f.so "
        f"authfile={U2F_MAPPING} cue origin={origin} appid={origin} "
        "pinverification=1 userverification=0"
    )
    if profile == "face-only":
        lines = [
            "# howdy-surface begin",
            "auth sufficient pam_howdy.so",
            "# howdy-surface end",
        ]
    elif profile == "face-or-passkey":
        lines = [
            "# howdy-surface begin",
            "auth sufficient pam_howdy.so",
            u2f,
            "# howdy-surface end",
        ]
    elif profile == "strong-passkey":
        if not has_u2f_mapping(user):
            raise SystemExit(
                f"No FIDO2 mapping for {user}. Run: sudo howdy-surface passkey-enroll --user {user} --require-pin"
            )
        lines = [
            "# howdy-surface begin",
            "# FIDO2 is required; then Surface IR face auth or password may satisfy the remaining PAM stack.",
            u2f.replace("auth sufficient", "auth required", 1),
            "auth sufficient pam_howdy.so",
            "# howdy-surface end",
        ]
    else:
        raise SystemExit(f"Unknown profile: {profile}")
    return [f"{line}\n" for line in lines]


def configure_pam_service(service: str, profile: str, user: str, origin: str) -> Path:
    pam_file = PAM_DIR / service
    if not pam_file.exists():
        raise SystemExit(f"PAM service does not exist: {pam_file}")

    lines = pam_file.read_text().splitlines(True)
    new_lines: list[str] = []
    in_block = False
    for line in lines:
        if line.strip() == "# howdy-surface begin":
            in_block = True
            continue
        if line.strip() == "# howdy-surface end":
            in_block = False
            continue
        if in_block:
            continue
        if "pam_howdy.so" in line or "pam_u2f.so" in line:
            continue
        new_lines.append(line)

    saved = backup(pam_file)
    pam_file.write_text("".join(pam_block(profile, user, origin) + new_lines))
    return saved


def parse_services(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def cmd_pam(args: argparse.Namespace) -> None:
    require_root()
    user_exists(args.user)
    if args.profile != "face-only" and not Path("/usr/lib/security/pam_u2f.so").exists():
        raise SystemExit("pam-u2f is not installed. Install it with: sudo pacman -S pam-u2f")
    for service in parse_services(args.services):
        saved = configure_pam_service(service, args.profile, args.user, args.origin)
        print(f"configured {PAM_DIR / service} (backup: {saved})")


def configure_howdy(camera: dict[str, str]) -> None:
    values = {
        "timeout_notice": "false",
        "certainty": "3.5",
        "timeout": "2",
        "device_path": camera["device"],
        "max_height": "240",
        "frame_width": camera["width"],
        "frame_height": camera["height"],
        "dark_threshold": "95",
        "recording_plugin": "ffmpeg",
        "device_format": "v4l2",
    }
    saved = edit_key_values(CONFIG, values)
    print(f"configured {CONFIG} (backup: {saved})")


def cmd_setup(args: argparse.Namespace) -> None:
    require_root()
    user_exists(args.user)
    if not CONFIG.exists():
        raise SystemExit("Howdy config not found. Install and configure howdy-git first.")
    if not command_exists("ffmpeg"):
        raise SystemExit("ffmpeg is required.")
    if not command_exists("v4l2-ctl"):
        raise SystemExit("v4l-utils is required.")

    camera = detect_ir_camera()
    if not camera:
        raise SystemExit("No likely Surface IR camera found.")
    print(f"Surface IR camera: {camera['device']} ({camera['card']})")

    configure_howdy(camera)
    saved = patch_ffmpeg_reader()
    if saved:
        print(f"patched {FFMPEG_READER} (backup: {saved})")
    else:
        print(f"{FFMPEG_READER} already has the howdy-surface patch")

    if args.services:
        for service in parse_services(args.services):
            saved = configure_pam_service(service, args.profile, args.user, args.origin)
            print(f"configured {PAM_DIR / service} (backup: {saved})")

    print("Next: sudo howdy-surface enroll --user " + args.user)


def cmd_enroll(args: argparse.Namespace) -> None:
    require_root()
    user_exists(args.user)
    label = args.label or "Surface IR"
    print("Look directly at the Surface IR camera.")
    os.execvp("howdy", ["howdy", "-U", args.user, "add", label])


def cmd_benchmark(args: argparse.Namespace) -> None:
    require_root()
    user_exists(args.user)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, "/usr/lib/howdy/compare.py", args.user], text=True)
    elapsed = time.monotonic() - start
    print(f"elapsed={elapsed:.3f}s")
    raise SystemExit(proc.returncode)


def cmd_passkey_enroll(args: argparse.Namespace) -> None:
    require_root()
    user_exists(args.user)
    if not command_exists("pamu2fcfg"):
        raise SystemExit("pamu2fcfg is missing. Install it with: sudo pacman -S pam-u2f")

    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    cmd = ["pamu2fcfg", "-u", args.user, "-o", args.origin, "-i", args.origin]
    if args.require_pin:
        cmd.append("-N")
    if args.require_uv:
        cmd.append("-V")

    print("Touch your FIDO2/U2F authenticator when it blinks.")
    proc = run(cmd)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr or proc.stdout or "pamu2fcfg failed")

    mapping = ""
    for line in proc.stdout.splitlines():
        if line.startswith(f"{args.user}:"):
            mapping = line.strip()
    if not mapping:
        raise SystemExit("pamu2fcfg did not return a mapping line.")

    user_part, credential = mapping.split(":", 1)
    lines = U2F_MAPPING.read_text().splitlines() if U2F_MAPPING.exists() else []
    out: list[str] = []
    found = False
    for line in lines:
        if line.startswith(f"{user_part}:"):
            found = True
            if credential not in line:
                line = line.rstrip() + ":" + credential
        out.append(line)
    if not found:
        out.append(mapping)

    U2F_MAPPING.write_text("\n".join(out) + "\n")
    os.chmod(U2F_MAPPING, 0o600)
    shutil.chown(U2F_MAPPING, user="root", group="root")
    print(f"registered FIDO2 mapping for {args.user} in {U2F_MAPPING}")


def cmd_doctor(_: argparse.Namespace) -> None:
    print_command_result("howdy", command_exists("howdy"), shutil.which("howdy") or "")
    print_command_result("ffmpeg", command_exists("ffmpeg"), shutil.which("ffmpeg") or "")
    print_command_result("v4l2-ctl", command_exists("v4l2-ctl"), shutil.which("v4l2-ctl") or "")
    print_command_result("pam_howdy", Path("/usr/lib/security/pam_howdy.so").exists())
    print_command_result("pam-u2f", Path("/usr/lib/security/pam_u2f.so").exists(), "optional FIDO2")
    print_command_result("pamu2fcfg", command_exists("pamu2fcfg"), "optional FIDO2 registration")
    print_command_result("howdy config", CONFIG.exists(), str(CONFIG))
    print_command_result("ffmpeg reader", FFMPEG_READER.exists(), str(FFMPEG_READER))
    camera = detect_ir_camera()
    if camera:
        print(f"surface_ir_camera        ok - {camera['device']} {camera['card']} {camera['width']}x{camera['height']}")
    else:
        print("surface_ir_camera        missing")


def cmd_browser_passkeys(_: argparse.Namespace) -> None:
    print(
        """
Browser passkeys on Linux

Passkeys for websites are WebAuthn/FIDO2 credentials created by the browser
with an authenticator. This package cannot turn Howdy or the Surface IR camera
into a browser platform authenticator.

Use one of these instead:
  - a hardware FIDO2 key such as a YubiKey, SoloKey, Nitrokey, or OnlyKey;
  - a phone as a cross-device passkey authenticator when the browser offers it;
  - a password manager that implements passkey storage and browser integration.

For hardware keys:
  1. Install libfido2 and a browser with WebAuthn support.
  2. Plug in the key and set a FIDO2 PIN with fido2-token or the vendor tool.
  3. Open a website's security settings and choose Add passkey/security key.
  4. Touch the key and enter its PIN when the browser prompts.

The howdy-surface passkey commands are PAM-only. They protect local unlock,
sudo, and similar PAM services through pam-u2f.
"""
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP,
        description="Configure Surface IR cameras for Howdy and optional FIDO2 PAM auth.",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("guide", help="print the full setup guide").set_defaults(func=lambda _: print(GUIDE))
    sub.add_parser("detect", help="detect the Surface IR camera").set_defaults(func=cmd_detect)
    sub.add_parser("doctor", help="check dependencies and camera state").set_defaults(func=cmd_doctor)
    sub.add_parser("browser-passkeys", help="explain browser passkey setup boundaries").set_defaults(func=cmd_browser_passkeys)

    setup = sub.add_parser("setup", help="configure Howdy and optional PAM services")
    setup.add_argument("--user", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "root")
    setup.add_argument("--services", default="hyprlock", help="comma-separated PAM services, e.g. hyprlock,sudo")
    setup.add_argument("--profile", choices=["face-only", "face-or-passkey", "strong-passkey"], default="face-only")
    setup.add_argument("--origin", default=DEFAULT_ORIGIN)
    setup.set_defaults(func=cmd_setup)

    pam = sub.add_parser("pam", help="configure PAM services only")
    pam.add_argument("--user", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "root")
    pam.add_argument("--services", default="hyprlock")
    pam.add_argument("--profile", choices=["face-only", "face-or-passkey", "strong-passkey"], default="face-only")
    pam.add_argument("--origin", default=DEFAULT_ORIGIN)
    pam.set_defaults(func=cmd_pam)

    enroll = sub.add_parser("enroll", help="enroll a Howdy face model")
    enroll.add_argument("--user", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "root")
    enroll.add_argument("--label", default="Surface IR")
    enroll.set_defaults(func=cmd_enroll)

    bench = sub.add_parser("benchmark", help="time a direct Howdy compare")
    bench.add_argument("--user", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "root")
    bench.set_defaults(func=cmd_benchmark)

    pk = sub.add_parser("passkey-enroll", help="register a FIDO2/U2F authenticator for PAM")
    pk.add_argument("--user", default=os.environ.get("SUDO_USER") or os.environ.get("USER") or "root")
    pk.add_argument("--origin", default=DEFAULT_ORIGIN)
    pk.add_argument("--require-pin", action="store_true", help="require FIDO2 PIN verification")
    pk.add_argument("--require-uv", action="store_true", help="require authenticator user verification, if supported")
    pk.set_defaults(func=cmd_passkey_enroll)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        print(GUIDE)
        return
    args.func(args)


if __name__ == "__main__":
    main()
