import os
import re
import sys
import shutil
import logging
import subprocess

logger = logging.getLogger("adb_utils")

# Ensure writable adb config dir if /root is read-only
if not os.environ.get("ANDROID_USER_HOME"):
    try:
        home_dir = os.path.expanduser("~")
        if not os.access(home_dir, os.W_OK):
            os.environ["ANDROID_USER_HOME"] = "/tmp/.android"
    except Exception:
        os.environ["ANDROID_USER_HOME"] = "/tmp/.android"


def run_adb_cmd(args: list, timeout: int = 8) -> tuple[int, str, str]:
    """Execute an ADB command safely and return (returncode, stdout, stderr)."""
    adb_bin = shutil.which("adb") or "adb"
    cmd = [adb_bin] + args
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        logger.warning("ADB command timed out after %ds: %s", timeout, cmd)
        return -1, "", "Command timed out"
    except Exception as e:
        logger.error("Failed to execute ADB command %s: %s", cmd, e)
        return -1, "", str(e)


def get_adb_devices() -> list[dict]:
    """
    Query attached ADB devices and return structured list:
    [
        {
            "serial": "172.17.131.136:37913",
            "state": "device",  # device, offline, unauthorized
            "model": "Realme_GT",
            "product": "...",
            "transport_id": "1",
            "is_network": True
        },
        ...
    ]
    """
    code, out, err = run_adb_cmd(["devices", "-l"])
    if code != 0 and not out:
        logger.warning("adb devices failed: %s", err)
        return []

    devices = []
    lines = out.splitlines()
    for line in lines[1:]:  # skip 'List of devices attached'
        line = line.strip()
        if not line:
            continue

        parts = re.split(r'\s+', line)
        if len(parts) < 2:
            continue

        serial = parts[0]
        state = parts[1]

        info = {
            "serial": serial,
            "state": state,
            "model": "Unknown",
            "product": "Unknown",
            "device": "Unknown",
            "transport_id": "",
            "is_network": ":" in serial
        }

        for item in parts[2:]:
            if ":" in item:
                k, v = item.split(":", 1)
                info[k] = v

        devices.append(info)

    return devices


def connect_adb(target: str) -> tuple[bool, str]:
    """
    Connect to a network ADB target (e.g. '172.17.131.136:37913').
    Returns (success, message).
    """
    target = target.strip()
    if not target:
        return False, "Target address is empty"

    # Default port 5555 if only IP provided
    if ":" not in target and re.match(r'^\d{1,3}(\.\d{1,3}){3}$', target):
        target = f"{target}:5555"

    code, out, err = run_adb_cmd(["connect", target], timeout=10)
    full_msg = (out or err).strip()

    if "connected to" in full_msg.lower() or "already connected" in full_msg.lower():
        logger.info("Successfully connected to ADB target: %s (%s)", target, full_msg)
        return True, full_msg
    else:
        logger.warning("Failed to connect to %s: %s", target, full_msg)
        return False, full_msg or "Failed to connect"


def disconnect_adb(target: str = None) -> tuple[bool, str]:
    """Disconnect an ADB device or all devices."""
    args = ["disconnect"]
    if target:
        args.append(target)
    code, out, err = run_adb_cmd(args, timeout=5)
    return (code == 0), (out or err).strip()


def interactive_device_prompt(devices: list[dict]) -> str | None:
    """
    Display a numbered interactive menu on terminal for the user to select or enter a device.
    """
    print("\n" + "=" * 55)
    print(" ADB Target Device Selection")
    print("=" * 55)

    valid_devices = [d for d in devices if d.get("state") == "device"]
    other_devices = [d for d in devices if d.get("state") != "device"]

    all_opts = []
    idx = 1
    for d in valid_devices:
        desc = f"{d['serial']} [{d.get('model', 'Phone')}] (online)"
        print(f" [{idx}] {desc}")
        all_opts.append(d['serial'])
        idx += 1

    for d in other_devices:
        desc = f"{d['serial']} [{d.get('state')}]"
        print(f" [{idx}] {desc}")
        all_opts.append(d['serial'])
        idx += 1

    print(f" [m] Enter custom IP:Port manually")
    print(f" [s] Standby / Wait for Web UI connection")
    print("=" * 55)

    default_choice = "1" if valid_devices else "m"
    prompt_str = f"Select target [Default {default_choice}]: "

    try:
        choice = input(prompt_str).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nSelection aborted.")
        return None

    if not choice:
        choice = default_choice

    if choice.lower() == 'm':
        try:
            custom = input("Enter device IP:Port (e.g. 172.17.131.136:37913): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if custom:
            if ":" in custom:
                connect_adb(custom)
            return custom
        return None
    elif choice.lower() == 's':
        return None
    elif choice.isdigit():
        choice_idx = int(choice) - 1
        if 0 <= choice_idx < len(all_opts):
            return all_opts[choice_idx]

    print("Invalid option selected.")
    return None


def resolve_serial(
    cli_serial: str = None,
    env_serial: str = None,
    interactive: bool = True
) -> str | None:
    """
    Resolve ADB serial following priority:
    1. CLI argument (--serial)
    2. Environment variable (ADB_SERIAL)
    3. Interactive TTY selection menu (if available)
    4. Auto-detect from `adb devices`
    5. None (Standby mode)
    """
    # 1. CLI serial
    if cli_serial and cli_serial.strip():
        serial = cli_serial.strip()
        if ":" in serial:
            connect_adb(serial)
        return serial

    # 2. Environment variable
    env_val = env_serial or os.environ.get("ADB_SERIAL", "").strip()
    if env_val:
        if ":" in env_val:
            connect_adb(env_val)
        return env_val

    # Query currently attached devices
    devices = get_adb_devices()
    active_devices = [d for d in devices if d.get("state") == "device"]

    # 3. Interactive prompt if terminal is attached
    is_interactive = interactive and sys.stdin.isatty() and not os.environ.get("NON_INTERACTIVE")
    if is_interactive:
        selected = interactive_device_prompt(devices)
        if selected:
            return selected

    # 4. Auto-detection for non-interactive / headless
    if len(active_devices) == 1:
        chosen = active_devices[0]["serial"]
        logger.info("Auto-detected single active ADB device: %s (%s)", chosen, active_devices[0].get("model"))
        return chosen
    elif len(active_devices) > 1:
        chosen = active_devices[0]["serial"]
        logger.info("Multiple active devices found (%d). Selecting first: %s", len(active_devices), chosen)
        return chosen

    logger.warning("No active ADB devices found. Starting in standby mode.")
    return None
