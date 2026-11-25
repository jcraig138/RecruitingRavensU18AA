#!/usr/bin/env python3
"""Build an encrypted, read-only recruiting board page.

Mirrors the scheme already used on the U18AA-Coaches staff page:
PBKDF2-SHA256 (600,000 iterations) -> 256-bit key -> AES-GCM.
The plaintext page never appears in the output file.

Usage: python3 -I build.py <passphrase> [outfile]
"""
import base64, datetime, json, os, sys, hashlib, pathlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = pathlib.Path(__file__).resolve().parent
ITER = 600_000
KEY_NAME = "rv-recruit-key"
TITLE = "Ravens U18AA recruiting"

GATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>__TITLE__</title>
<style>
:root { --gold: #FFCC00; --bg: #f7f6f3; --panel: #ffffff; --fg: #1a1a1a; --muted: #5f5e5a; --line: #e3e1dc; --bad: #c62828; }
@media (prefers-color-scheme: dark) { :root { --bg: #1c1c1b; --panel: #262624; --fg: #f0efea; --muted: #a8a69f; --line: #3a3936; --bad: #ef6b6b; } }
html, body { margin: 0; background: var(--bg); color: var(--fg); font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 16px; box-sizing: border-box; }
form { background: var(--panel); border: 1px solid var(--line); border-top: 4px solid var(--gold); border-radius: 10px; padding: 24px; width: 100%; max-width: 360px; box-sizing: border-box; display: flex; flex-direction: column; gap: 12px; }
h1 { font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1.5rem; margin: 0; }
p { margin: 0; color: var(--muted); font-size: .9rem; line-height: 1.4; }
input[type=password] { font: inherit; font-size: 1rem; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--fg); }
label { display: flex; gap: 8px; align-items: center; font-size: .9rem; color: var(--muted); }
button { font: inherit; font-weight: 600; padding: 10px 12px; border: 0; border-radius: 8px; background: var(--gold); color: #1a1a1a; cursor: pointer; }
button:disabled { opacity: .6; cursor: default; }
#msg { color: var(--bad); min-height: 1.2em; }
</style>
</head>
<body>
<div class="wrap">
<form id="f" autocomplete="on">
  <h1>__TITLE__</h1>
  <p>Enter the password to open this page.</p>
  <input type="password" id="pw" name="password" autocomplete="current-password" aria-label="Password" required autofocus>
  <label><input type="checkbox" id="keep"> Remember on this device</label>
  <button type="submit" id="go">Open</button>
  <p id="msg" role="alert"></p>
</form>
</div>
<script>
const LOCK = __LOCK__;
const KEY_NAME = '__KEY_NAME__';
const u8 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
async function derive(pw) {
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw), 'PBKDF2', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt: u8(LOCK.salt), iterations: LOCK.iter }, base, 256));
}
async function open(raw) {
  const key = await crypto.subtle.importKey('raw', raw, 'AES-GCM', false, ['decrypt']);
  const html = new TextDecoder().decode(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: u8(LOCK.iv) }, key, u8(LOCK.ct)));
  document.open(); document.write(html); document.close();
}
const toB64 = a => btoa(String.fromCharCode(...a));
(async () => {
  let saved = null; try { saved = localStorage.getItem(KEY_NAME); } catch (e) {}
  if (saved) { try { await open(u8(saved)); return; } catch (e) { try { localStorage.removeItem(KEY_NAME); } catch (e2) {} } }
})();
document.getElementById('f').addEventListener('submit', async ev => {
  ev.preventDefault();
  const go = document.getElementById('go'), msg = document.getElementById('msg');
  go.disabled = true; msg.textContent = ''; go.textContent = 'Opening...';
  try {
    const raw = await derive(document.getElementById('pw').value);
    const keep = document.getElementById('keep').checked;
    await open(raw);
    if (keep) { try { localStorage.setItem(KEY_NAME, toB64(raw)); } catch (e) {} }
  } catch (e) {
    go.disabled = false; go.textContent = 'Open'; msg.textContent = 'That password did not work. Try again.';
  }
});
</script>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: build.py <passphrase> [outfile]")
    passphrase = sys.argv[1]
    out = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "index.html"

    data = json.loads((HERE / "data.json").read_text(encoding="utf-8"))
    page = (HERE / "page.html").read_text(encoding="utf-8")

    logo_b64 = base64.b64encode((HERE / "ravens-logo.png").read_bytes()).decode()
    page = page.replace("__LOGO__", "data:image/png;base64," + logo_b64)
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("America/Toronto"))
    except Exception:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5)))
    stamp = now.strftime("%b %-d, %Y at %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    page = page.replace("__BUILT__", stamp)
    page = page.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    # Safety net: the plaintext must not carry contact details.
    import re
    leaks = []
    if re.search(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b", page):
        leaks.append("phone number")
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", page):
        leaks.append("email address")
    if leaks:
        sys.exit("ABORT: plaintext still contains " + ", ".join(leaks))

    salt = os.urandom(16)
    iv = os.urandom(12)
    key = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, ITER, dklen=32)
    ct = AESGCM(key).encrypt(iv, page.encode("utf-8"), None)

    lock = {
        "salt": base64.b64encode(salt).decode(),
        "iv": base64.b64encode(iv).decode(),
        "iter": ITER,
        "ct": base64.b64encode(ct).decode(),
    }

    html = (GATE.replace("__TITLE__", TITLE)
                .replace("__KEY_NAME__", KEY_NAME)
                .replace("__LOCK__", json.dumps(lock)))
    out.write_text(html, encoding="utf-8")

    print(f"players   : {len(data['players'])}")
    print(f"games     : {len(data['games'])}")
    print(f"plaintext : {len(page):,} chars")
    print(f"output    : {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
