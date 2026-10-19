#!/usr/bin/env python3
"""Pulls the WodUp session out of your Chrome and writes it as JSON for `browse`.

Why it exists: the session cookie (`session_token`) is httpOnly, so it cannot
be read from the page with JavaScript, and `browse cookie-import-browser`
returns 0 cookies even when the keychain grants access. It is decrypted here
by hand.

macOS will ask for keychain access ("Chrome Safe Storage") the first time,
and it asks **once per binary that requests it**: approving it for `security`
does not approve it for another program. If the dialog shows up, click
"Always Allow".

wodup/gq.sh calls it only when the browse session has expired:

    python3 wodup/cookies.py [chrome|arc] > cookies.json
"""

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BROWSERS = {
    "chrome": ("Chrome Safe Storage",
               "~/Library/Application Support/Google/Chrome/Default/Cookies"),
    "arc": ("Arc Safe Storage",
            "~/Library/Application Support/Arc/User Data/Default/Cookies"),
}

SAME_SITE = {0: "None", 1: "Lax", 2: "Strict"}


def derive_key(service):
    pw = subprocess.check_output(
        ["security", "find-generic-password", "-wgs", service],
        stderr=subprocess.DEVNULL,
    ).strip()
    return hashlib.pbkdf2_hmac("sha1", pw, b"saltysalt", 1003, 16)


def decrypt(blob, key):
    if not blob or blob[:3] not in (b"v10", b"v11"):
        return None
    d = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    plain = d.update(blob[3:]) + d.finalize()
    plain = plain[:-plain[-1]]          # PKCS7 padding
    # Chrome >= v130 prepends a SHA-256 of the domain to the actual value.
    return plain[32:].decode("utf-8", "replace")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "chrome"
    service, path = BROWSERS[which]
    path = os.path.expanduser(path)

    # Copy the DB: Chrome keeps it open and locked while running.
    key = derive_key(service)
    out = []
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, "Cookies")
        shutil.copy(path, tmp)
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "select host_key, name, encrypted_value, path, expires_utc, "
            "is_secure, is_httponly, samesite from cookies "
            "where host_key like '%wodup%'").fetchall()
        con.close()
    for host, name, enc, cpath, exp, secure, httponly, ss in rows:
        c = {"name": name, "value": decrypt(enc, key), "domain": host,
             "path": cpath, "httpOnly": bool(httponly), "secure": bool(secure),
             "sameSite": SAME_SITE.get(ss, "Lax")}
        if exp:
            c["expires"] = int(exp / 1000000 - 11644473600)
        out.append(c)

    if not any(c["name"] == "session_token" for c in out):
        print("WARNING: no session_token; is the WodUp session in another "
              "browser? Try: cookies.py arc", file=sys.stderr)

    json.dump(out, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
