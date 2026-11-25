Build sources for the coaches' page.

index.html at the repo root is a single encrypted file: a password gate plus
the whole page as AES-GCM ciphertext. PBKDF2-SHA256, 600,000 iterations. The
plaintext never appears in the repo.

To rebuild:

    python3 -I make_data.py raw_players.json raw_games.json data.json
    python3 -I build.py "<passphrase>" ../index.html

raw_players.json and raw_games.json are dumps of the recruiting dashboard's
database. make_data.py works by whitelist: a field reaches the coaches' page
only if it is named in that script. Emails, phone numbers, parent names and
the outreach log are not, and both scripts abort rather than publish a page
that contains a phone number or an email address.

data.json, the raw dumps and any preview are gitignored. Do not commit them.
