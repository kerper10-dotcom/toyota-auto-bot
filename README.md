# Auto oglasi → Telegram

GitHub Actions bot koji svaka **2 sata** provjeri tvoje pretrage na Avto.net, Index Oglasima, willhaben.at i Njuškalu, pa pošalje Telegram poruku **samo ako se pojavi novi oglas**.

Prvi uspješan run samo zapamti postojeće oglase (`seen.json`) i **ne šalje** stotine starih oglasa. U repo je već upisan trenutni snapshot oglasa, pa kad dodaš Telegram secrete dobivaš samo oglase koji se pojave **nakon toga**.

## Pretrage

| Izvor | Filter |
| --- | --- |
| Avto.net | Toyota Yaris, 2020+, do 19.000 €, automatik |
| Avto.net | Toyota Yaris Cross, do 19.000 €, automatik |
| Avto.net | Toyota Corolla, 2019+, do 19.000 €, automatik |
| Avto.net | Mazda2, 2020+, do 17.000 €, automatik |
| Index Oglasi | Toyota Yaris + Yaris Cross, od 2020. |
| willhaben | Mazda2, 2020+, automatik, do 17.500 € |
| willhaben | Toyota Yaris, 2020+, automatik, do 17.500 € |
| Njuškalo | Toyota Yaris, od 2020. |
| Njuškalo | Mazda 2, automatik / sekvencijski |

URL-ovi su u [`searches.json`](searches.json). Za novu pretragu dodaj objekt tamo (`site` mora biti `avto`, `index`, `willhaben` ili `njuskalo`).

## Zašto 2 sata

Avto.net i Njuškalo imaju Cloudflare / bot zaštitu. 2 sata je dovoljno često za rabljene auta, a dovoljno rijetko da GitHub IP-ovi obično prođu bez captche. Ako neka stranica padne na jednom runu, bot **ne briše** već viđene ID-ove te pretrage, pa sljedeći run neće spamati.

## Telegram bot

1. U Telegramu otvori [@BotFather](https://t.me/BotFather) → `/newbot` → kopiraj token.
2. Pošalji svom botu bilo koju poruku (npr. `/start`).
3. Otvori u browseru (zamijeni token):

   `https://api.telegram.org/botTOKEN/getUpdates`

4. U JSON-u nađi `"chat":{"id": 123456789}` — to je `TELEGRAM_CHAT_ID`.
5. U GitHub repou: **Settings → Secrets and variables → Actions → New repository secret**:

   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID` (može i više ID-ova odvojeno zarezom)

Dok secreti nisu postavljeni, bot i dalje radi i puni `seen.json`, samo ne šalje poruke.

## GitHub (public repo)

Repo: [kerper10-dotcom/toyota-auto-bot](https://github.com/kerper10-dotcom/toyota-auto-bot)

Telegram bot: [@toyota_auto_bot](https://t.me/toyota_auto_bot)

Zatim:

1. Dodaj dva secreta gore.
2. **Actions** tab → **Auto oglasi monitor** → **Run workflow** (prvi run samo seeda `seen.json`).
3. Schedule ide sam: `17 */2 * * *` (svaka 2 sata).

Actions treba imati pravo pisanja u repo (default `GITHUB_TOKEN` + `contents: write` u workflowu) da može commitati `seen.json`.

## Lokalni test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
# na ovom Macu, ako bundled Chromium nije instaliran, bot koristi Google Chrome

python monitor.py --dry-run
```

`--dry-run` ne šalje Telegram. `--send-existing` šalje i trenutno aktivne oglase (samo za test).

Sa stvarnim Telegramom:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
python monitor.py
```

## Poruka

Svaki novi oglas je jedna poruka:

```
🆕 Novi oglas
Avto.net · Toyota Yaris

Toyota Yaris Hybrid 115 ...
14.990 €
2022 · 45.100 km
https://www.avto.net/Ads/details.asp?id=...
```

## Ako nešto prestane raditi

Stranice mijenjaju HTML. U Actions logu vidiš `scrape failed` ili `0 listings parsed` za taj izvor. Ostali izvori i dalje rade. Ako Avto.net pokaže Cloudflare challenge, sljedeći run obično prođe — zato je interval 2h, ne 10 minuta.
