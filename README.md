# Auto oglasi → Telegram

GitHub Actions bot koji svaka **2 sata** provjeri tvoje pretrage na Avto.net, Index Oglasima, willhaben.at i Njuškalu, pa pošalje Telegram poruku **samo ako se pojavi novi oglas**.

Repo: [kerper10-dotcom/toyota-auto-bot](https://github.com/kerper10-dotcom/toyota-auto-bot)  
Telegram: [@toyota_auto_bot](https://t.me/toyota_auto_bot)

Sve radi **samo na GitHubu**. Avto.net Cloudflare se rješava FlareSolverrom u Actions jobu.

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

Secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Schedule: `17 */2 * * *` (svaka 2 sata). Ručno: Actions → **Auto oglasi monitor** → Run workflow.
