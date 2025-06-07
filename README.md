# dbmp – database music player

dbmp is a local music server and controller. It uses sqlite3 to store metadata about audio files, mpd to play them locally, and also acts as a Sonos controller. You interact with dbmp through a browser interface. As a Sonos controller, dbmp can either serve local audio files to Sonos speakers or search for and queue Spotify content using Spotify’s Web API. To enable Spotify features, you must first authorize dbmp to access your Spotify account.

dbmp is designed to run on Linux. It has currently been tested only on Ubuntu, but will likely run on other Linux distributions as well.

---

## Screenshots

### Main Interface
![Sonos Queue](/assets/01%20Main%20Page%20Sonos%20Queue.png)

### Search Spotify
![Search Spotify](/assets/02%20Search%20Spotify.png)

### Spotify Artist Result
![Spotify Artist Result](/assets/03%20Search%20Spotify%20Result%20Artist.png)

### Spotify Album Result
![Spotify Album Result](/assets/04%20Search%20Spotify%20Result%20Album.png)

---

## 🔧 Installation

To set up dbmp:

1. **Make the installer script executable (if needed):**

    ```bash
    chmod +x install.py
    ```

2. **Run the installer:**

    ```bash
    ./install.py
    ```

    This will:
    - Create all necessary directories under `~/.dbmp` and `~/.mpd`
    - Install required Python libraries and check for required system packages (must be pre-installed)
    - Generate a default SQLite database and configuration file
    - Set up `mpd` for user-level audio playback
    - Create SSL certificates for secure access
    - Disable the system-wide mpd service (mpd will be launched by this app instead)

---

## 🎧 Running the App

Once installed:

1. **Make the main script executable (if needed):**

    ```bash
    chmod +x run_dbmp
    ```

2. **Start dbmp:**

    ```bash
    ./run_dbmp
    ```

    dbmp will start and can be accessed from your browser, typically at:

    ```
    https://localhost:8005
    ```

    (Port can be changed in `~/.dbmp/config.py`.)

---

## 🔐 SSL Certificates

- If your browser shows a security warning, you can either proceed through it or install the generated root certificate.
- To install the root certificate on an Android phone or other device, follow these instructions (which are also displayed at the end of `install.py`):

1. Run: `mkcert -CAROOT` to locate the root certificate directory.
2. Copy the `rootCA.pem` file to your phone (e.g., via Google Drive, email or USB).
3. On your phone, go to Settings > Security > Encryption & credentials > Install a certificate > CA certificate.
4. Select `rootCA.pem` to trust it for local HTTPS.

---

## 🔊 PulseAudio Configuration

If you're using PulseAudio and experience audio issues:

1. Edit your `~/.profile` and add this line:

    ```bash
    pacmd load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1
    ```

2. Reboot or log out/in for the change to take effect.

This allows mpd (running under your user) to connect to PulseAudio.

---

## 🛠 Customisation

- All user-editable settings are in:

    ```bash
    ~/.dbmp/config.py
    ```

- If you change `MUSICPATH`, you may also need to update:

    ```bash
    ~/.mpd/mpd.conf
    ```

---

## 📂 App Directory Structure

```plaintext
dbmp/
├── install.py                      ← Installer script
├── run_dbmp                        ← Main launch script
├── dbmp/                           ← Python source files
├── dbmp/soco/                      ← Bundled Python library
├── html/                           ← Frontend files (HTML, JS, etc.)
├── scripts/                        ← Bash scripts
├── setup/                          ← Installation files
├── setup/config.py                 ← Default user config template
├── setup/mpd.conf                  ← MPD configuration template
├── setup/python_requirements.txt   ← List of Python dependencies
└── setup/schema.sql                ← SQLite schema file
```
---

## 💬 Troubleshooting & Contributions

This is an early-stage installer. If you encounter any errors during setup:

- Rerun `./install.py` to retry installation steps.
- Check the terminal output for warnings and detailed instructions.
- Review `~/.dbmp/config.py` and `~/.mpd/mpd.conf` for configuration issues.

Feedback and contributions are welcome — feel free to open issues or pull requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

> This software is provided "as is", without warranty of any kind. Use at your own risk.

