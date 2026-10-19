# Security and Data Safety Specification

## 1. Principles of Nintendo Switch Homebrew Safety

Operating in a custom firmware environment requires uncompromising respect for user data, storage integrity, and operating system boundaries.

H3H Backgrounds enforces the following hard invariants across all modules:

### 1.1 Zero Modification to System and Game Files
- **NO SAVE DATA ACCESS:** The app never touches or queries `save:/` or `sdmc:/Nintendo/save/`.
- **NO FIRMWARE/NAND MODIFICATIONS:** The app never opens `bis:/` or any NAND storage partitions.
- **NO ATMOSPHERE/4IFIR CORE MODIFICATIONS:** The app does not modify `.ini` configuration files, `bootloader`, `exosphere.ini`, or payload files.
- **NO GAME APPLICATION FILE ACCESS:** The app does not modify `.nsp`, `.xci`, RomFS, or ExeFS files of any installed game.

---

## 2. Path Traversal & Destination Lockdown

### 2.1 Threat Model
An attacker might tamper with a compromised remote catalog or a man-in-the-middle proxy, injecting malicious paths into URL filenames or game entries (e.g., `../../../../atmosphere/kips/evil.kip`).

### 2.2 Boundary Defense
1. **Title ID Strict Validation:**
   Every Title ID must match the regular expression:
   ```
   ^0100[0-9A-Fa-f]{12}$
   ```
   Any entry with characters outside `[0-9A-Fa-f]` or a length other than 16 is immediately rejected with a schema validation error.

2. **Deterministic Local Path Calculation:**
   The destination path is NEVER constructed using remote strings. It is strictly:
   ```
   target_path = covers_directory + "/" + uppercase_hex(title_id) + ".mp4"
   ```
   Because `title_id` is strictly 16 hexadecimal characters, it cannot contain `/`, `\`, `..`, `:`, or null bytes.

3. **Restricted Storage Root:**
   All cover write operations must be canonicalized and checked to start with the resolved path of `sdmc:/recordings/covers/`.

---

## 3. Atomic Installation and Rollback Engine

Corrupted downloads, battery exhaustion, or premature console sleep must never result in corrupted files or destroyed user data.

```
                    +------------------------+
                    | Start Download Request |
                    +------------------------+
                                |
                                v
               [1. Check Free Storage: Size + 20MB buffer]
                                | (sufficient)
                                v
             [2. Stream download -> <TITLEID>.tmp]
                                |
                                v
               [3. Validate File Size == expected]
                                | (pass)
                                v
              [4. Calculate SHA-256 == expected]
                                | (pass)
                                v
        +-----------------------------------------------+
        | 5. If <TITLEID>.mp4 exists:                   |
        |    Rename <TITLEID>.mp4 -> <TITLEID>.bak      |
        +-----------------------------------------------+
                                |
                                v
        +-----------------------------------------------+
        | 6. Rename <TITLEID>.tmp -> <TITLEID>.mp4      |
        |    (Atomic Commit Point)                      |
        +-----------------------------------------------+
                                |
                                v
        +-----------------------------------------------+
        | 7. Installation Complete                      |
        |    (User can trigger "Restore Backup" anytime)|
        +-----------------------------------------------+
```

### 3.1 Failure Handling & Automatic Cleanup
- If network drops during step 2: `<TITLEID>.tmp` is closed and deleted. Existing `<TITLEID>.mp4` remains untouched.
- If checksum fails in step 4: `<TITLEID>.tmp` is deleted immediately. User is informed of integrity error.
- If step 6 fails: If `<TITLEID>.bak` was created, it is restored back to `<TITLEID>.mp4`.

### 3.2 User Preserved Assets Protection
- The installer NEVER deletes unknown `.mp4` files in `sdmc:/recordings/covers/`.
- If an existing file was placed manually by the user, installing a new catalog variant safely moves it to `.bak`.
- The user interface provides a dedicated **"Restore Backup"** option on any title that has an existing `.bak` file.

---

## 4. Memory Budget & Applet Mode Constraints

Nintendo Switch Homebrew can run in two distinct environments:

| Mode | Launch Method | Available Heap | H3H Downloader Policy |
| :--- | :--- | :--- | :--- |
| **Applet Mode** | Launched from Album | ~32 MB to ~400 MB depending on CFW config | Conservative mode: Minimal image cache (only 1-2 thumbnail icons in RAM), stream chunks of 64 KB, prompt user to launch via Title Override for optimal experience. |
| **Title Override** | Hold [R] while launching any installed game | ~3.5 GB | Full mode: Fast icon caching, silky smooth 60fps scrolling, multi-item download queuing. |

The application calls `appletGetAppletType()` at startup:
- If `AppletType_LibraryApplet` is detected, the UI displays a non-intrusive badge: `"Applet Mode (Limited RAM) — Hold [R] on any game for high memory"`.
- Memory allocations are strictly capped with guard limits to prevent crashes.

---

## 5. Network & TLS Verification

- TLS/SSL verification is mandatory.
- Self-signed or mismatched domain certificates are rejected.
- Embedded or Switch OS CA certificate stores are used.
- HTTP redirects are bounded (max 5 hops) and restricted to `https://` protocols only.
