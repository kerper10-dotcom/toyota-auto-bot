# Auto oglasi → Telegram

GitHub Actions bot koji svaka **2 sata** provjeri tvoje pretrage na Avto.net, Index Oglasima, willhaben.at i Njuškalu, pa pošalje Telegram poruku **samo ako se pojavi novi oglas**.

Prvi uspješan run samo zapamti postojeće oglase (`seen.json`) i **ne šalje** stotine starih oglasa.

Repo: [kerper10-dotcom/toyota-auto-bot](https://github.com/kerper10-dotcom/toyota-auto-bot)  
Telegram: [@toyota_auto_bot](https://t.me/toyota_auto_bot)

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

URL-ovi su u [`searches.json`](searches.json).

## Telegram

Secrets u GitHubu (Settings → Secrets and variables → Actions):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID` (`199701564`)

Schedule: `17 */2 * * *` (svaka 2 sata). Ručno: Actions → **Auto oglasi monitor** → Run workflow.

GitHub **ne može** čitati Avto.net (Cloudflare na datacenter IP). Te 4 pretrage idu s ovog Maca preko `launchd` svaka 2 sata, isti Telegram bot.

```bash
./scripts/install_avto_mac.sh
```

Mac mora biti upaljen (sleep = preskočena Avto.net provjera). Index / willhaben / Njuškalo i dalje idu preko GitHuba.

## Lokalni test

```bash
pip install -r requirements.txt
python -m playwright install chromium
python monitor.py --dry-run
```
