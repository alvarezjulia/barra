# Security

Barra handles two sessions that belong to you: your Garmin Connect login (kept
in a local browser profile at `~/.garmin-browser-profile`) and your WodUp
session cookie (read from your local Chrome by `wodup/cookies.py`, used inside
a local headless browser and deleted right after). Neither is sent anywhere
except to Garmin and WodUp themselves.

If you find a way this leaks a session or personal data, please report it
privately through GitHub: **Security → Report a vulnerability** on this
repository, rather than opening a public issue.
