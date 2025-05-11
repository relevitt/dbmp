#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import sqlite3
from pathlib import Path
import socket

# === Paths ===
# Source files
REPO_ROOT = Path(__file__).resolve().parent
SCHEMA_FILE = REPO_ROOT / "setup" / "schema.sql"
USER_CONFIG_PY = REPO_ROOT / "setup" / "config.py"
MPD_CONFIG_TEMPLATE = REPO_ROOT / "setup" / "mpd.conf"

# .dbmp
USER_HOME = Path.home()
INSTALL_ROOT = USER_HOME / ".dbmp"
CONFIG_DST = INSTALL_ROOT / "config.py" 
CERTS_DST = INSTALL_ROOT / "certs"
DB_FILE = INSTALL_ROOT / "dbmp.sqlite"

# .mpd
MPD_DIR = USER_HOME / ".mpd"
MPD_CONFIG_TARGET = MPD_DIR / "mpd.conf"

# === Utility Functions ===

def emit(tag, text):
    colors = {
        "INFO": "\x1b[92m",
        "WARNING": "\x1b[93m",
        "ERROR": "\x1b[91m"
    }
    reset = "\x1b[0m"
    label = f"{colors.get(tag)}[{tag}]{reset}"
    print(label, text)

    
def info(text):
    emit("INFO", text)

def warn(text):
    emit("WARNING", text)

def exit():
    print("Exiting installation.")
    print("Please run install.py again to complete the installation after the problem is resolved.")
    sys.exit(1)

def error(text):
    emit("ERROR", text)

def check_python_deps():
    pip_path = shutil.which("pip3")
    if not pip_path:
        error("pip3 is not installed. Please install it first (e.g., 'sudo apt install python3-pip').")
        exit()

    info("Installing python3 libraries with pip3 ...")
    pip_cmd = [pip_path, "install", "-r", str(REPO_ROOT / "setup" / "python_requirements.txt")]
    if sys.version_info >= (3, 11):
        pip_cmd.insert(2, "--break-system-packages")
    try:
        subprocess.run(pip_cmd, check=True)
    except subprocess.CalledProcessError as e:
        error(f"Pip install failed with return code {e.returncode}")
        exit()
    except Exception as e:
        error(f"Unexpected error during pip install: {e}")
        exit()

def check_system_programs():
    groups = {
        "coreutils": ["tee", "tail"],
        "procps": ["ps"],
        "catdoc": ["catdoc"],
        "mkcert": ["mkcert"],
        "mpd": ["mpd"],
    }

    missing_by_group = {}
    for group, programs in groups.items():
        for prog in programs:
            if shutil.which(prog) is None:
                missing_by_group.setdefault(group, []).append(prog)

    if missing_by_group:
        error("Missing required system programs:")
        for group, progs in missing_by_group.items():
            print(f"  {', '.join(progs)}  (suggest: sudo apt install {group})")
        exit()
    else:
        info("All required system programs are available.")


def create_directories():
    required_dirs = [
        INSTALL_ROOT,
        CERTS_DST,
        INSTALL_ROOT / "artwork",
        INSTALL_ROOT / "artwork" / "covers",
        INSTALL_ROOT / "artwork" / "artists",
        INSTALL_ROOT / "artwork" / "playlists",
        MPD_DIR,
        MPD_DIR / "playlists",
    ]

    for path in required_dirs:
        path.mkdir(parents=True, exist_ok=True)
        info(f"Ensured directory exists: {path}")

def initialize_database():
    if DB_FILE.exists():
        info("Database already exists, skipping initialization.")
        return
        
    if not SCHEMA_FILE.exists():
        error(f"Schema file not found: {SCHEMA_FILE}")
        exit()

    try:
        with open(SCHEMA_FILE) as f:
            schema = f.read()
        conn = sqlite3.connect(DB_FILE)
        conn.executescript(schema)
        conn.close()
        info(f"Initialized database at {DB_FILE}")
    except Exception as e:
        error(f"Failed to initialize database: {e}")
        exit()

def install_user_config():

    if CONFIG_DST.exists():
        info(f"User config already exists at {CONFIG_DST}")
        return

    try:
        shutil.copy2(USER_CONFIG_PY, CONFIG_DST)
        info(f"Installed default config to {CONFIG_DST}")
        info("You may edit this file to change settings such as ports or paths.")
    except Exception as e:
        error(f"Failed to copy config.py: {e}")
        exit()
        
def patch_and_install_mpd_config():
    if not MPD_CONFIG_TEMPLATE.exists():
        warn(f"mpd.conf template not found: {MPD_CONFIG_TEMPLATE}")
        return

    with open(USER_CONFIG_PY) as f:
        for line in f:
            if line.strip().startswith("MUSICPATH"):
                music_dir = line.split("=", 1)[1].strip().strip("\"'")
                break
        else:
            warn("MUSICPATH not found in config.py")
            return

    with open(MPD_CONFIG_TEMPLATE) as f:
        mpd_conf = f.read()

    mpd_conf = mpd_conf.replace("/mnt/Music", music_dir)
    mpd_conf = mpd_conf.replace("~", str(USER_HOME))

    if MPD_CONFIG_TARGET.exists():
        warn(f"mpd.conf already exists at {MPD_CONFIG_TARGET}")
        choice = input("Do you want to overwrite it with the default template? [y/N]: ").strip().lower()
        if choice != "y":
            info("Skipping mpd.conf update.")
            return

    try:
        with open(MPD_CONFIG_TARGET, "w") as f:
            f.write(mpd_conf)
        info(f"mpd.conf installed to {MPD_CONFIG_TARGET}")
        info("If you later change MUSICPATH in config.py, update mpd.conf too.")
    except Exception as e:
        error(f"Failed to write mpd.conf: {e}")
        exit()


def configure_mpd():
    info("Checking MPD system service...")

    # Step 1: Stop the system MPD service if it's running
    try:
        subprocess.run(["sudo", "systemctl", "stop", "mpd"], check=True)
        info("Stopped system MPD service.")
    except subprocess.CalledProcessError:
        warn("Failed to stop MPD service (maybe it wasn't running).")

    # Step 2: Disable it to prevent automatic startup
    try:
        subprocess.run(["sudo", "systemctl", "disable", "mpd"], check=True)
        info("Disabled system MPD service.")
        print("       MPD will now be launched only by this application.")
    except subprocess.CalledProcessError:
        warn("Failed to disable MPD service.")
        print("       You may need to run: sudo systemctl disable mpd")
        
    # Step 3: Warn about pulse audio
    warn("MPD may not be able to play audio unless PulseAudio's TCP module is loaded.")

    print("To enable PulseAudio access from MPD:")
    print("  1. Edit your ~/.profile file.")
    print("  2. Add the following line (if it's not already present):")
    print("     pacmd load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1")
    print("  3. Log out and log back in (or reboot) to apply the change.\n")

    print("Without this, MPD may fail silently when trying to output sound via PulseAudio.")
        
def get_local_ips():
    ips = set()

    # Try default method
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith("127."):
            ips.add(ip)
    except Exception:
        pass

    # Use UDP socket trick to get outward-facing IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if not ip.startswith("127."):
            ips.add(ip)
        s.close()
    except Exception:
        pass

    return sorted(ips)


def install_mkcert():
    info("Installing and generating SSL certificates...")

    subprocess.run(["mkcert", "-install"], check=True)

    # Step 1: Detect IPs
    ips = get_local_ips()
    print("\nAvailable local IP addresses:")
    for i, ip in enumerate(ips, 1):
        print(f"  {i}: {ip}")

    selected = input("\nSelect one or more IPs (comma-separated numbers, or press Enter to use all): ").strip()
    if selected:
        try:
            chosen_ips = [ips[int(i.strip()) - 1] for i in selected.split(",")]
        except (ValueError, IndexError):
            error("Invalid selection. Exiting.")
            exit()
    else:
        chosen_ips = ips

    # Step 2: Add standard names
    hostname = socket.gethostname()
    all_hosts = sorted(set(chosen_ips + ["localhost", hostname]))

    info(f"Creating certificate for: {', '.join(all_hosts)}")
    subprocess.run(["mkcert"] + all_hosts, check=True)

    # Step 3: Move and rename certificates
    cert_files = list(REPO_ROOT.glob("*.pem"))

    # Identify key and cert files from mkcert
    for f in cert_files:
        if "-key.pem" in f.name:
            target_name = "server-key.pem"
        else:
            target_name = "server.pem"
        shutil.move(str(f), str(CERTS_DST / target_name))

    ca_root = subprocess.check_output(["mkcert", "-CAROOT"]).decode().strip()
    info(f"SSL certificates renamed and moved to {CERTS_DST}")
    warn("If your hostname or IP address change, you will need to generate new certificates.")
    warn("Your web browser may display a warning about untrusted certificates.")

    print("You can either:")
    print(" - Proceed through the warning (usually by clicking 'Advanced' > 'Proceed'), or")
    print(" - Install the local root certificate to eliminate the warning on trusted devices.\n")

    print("To install the local root certificate on an Android device:")
    print(f"  1. Find the file named 'rootCA.pem'. This is usually located at: {ca_root}/rootCA.pem")
    print("  2. Upload 'rootCA.pem' to your device (e.g., via Google Drive, email, or USB).")
    print("  3. On your device, go to:")
    print("     Settings > Security > Encryption & credentials > Install a certificate > CA certificate")
    print("  4. Select and install 'rootCA.pem'.\n")

    print("Note: Device settings vary depending on manufacturer and Android version.\n")


        
def main():
    print("=== Starting DBMP installation ===")

    check_python_deps()
    check_system_programs()
    create_directories()
    initialize_database()
    install_user_config()
    patch_and_install_mpd_config()
    configure_mpd()
    install_mkcert()

    print("=== Installation complete ===")

if __name__ == "__main__":
    main()

