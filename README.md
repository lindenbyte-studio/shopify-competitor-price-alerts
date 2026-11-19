# Shopify competitor price-drop, restock and new-product alerts (GitHub Actions template)

[![alert](https://github.com/lindenbyte-studio/shopify-competitor-price-alerts/actions/workflows/alert.yml/badge.svg)](https://github.com/lindenbyte-studio/shopify-competitor-price-alerts/actions/workflows/alert.yml)

If you sell against Shopify stores, you want to know the day a competitor cuts a price, brings a bestseller back in stock
or launches a new product. This repo checks their public catalogs every day and sends you **only what changed since the
last run** to Slack and/or email. No server, no spreadsheet, no app install on anyone's store: one YAML file to edit,
GitHub Actions does the scheduling.

## What you get

A real digest built from Actor output on 2026-11-17 (a store we tested with; first 6 rows shown):

```text
Subject: Shopify competitor changes: 6 change(s): 6 back in stock.

* Gymshark Cotton Seamless Henley T-Shirt - Black Marl
  https://gymshark.com/products/gymshark-cotton-seamless-henley-t-shirt-ls-tops-black-aw26
  Back in stock · 25.20 USD · gymshark.com

* Gymshark Shadow Seamless T Shirt - Track Green
  https://gymshark.com/products/gymshark-shadow-seamless-t-shirt-ss-tops-green-aw26
  Back in stock · 30.80 USD · gymshark.com

* Gymshark x Sam Sulek Crew - Black
  https://gymshark.com/products/gymshark-gs-x-sam-sulek-crew-pullovers-black-aw26
  Back in stock · 45.50 USD · gymshark.com
...
```

Price changes look like `Price drop -20% · 60.00 USD → 48.00 USD · store.com`, ordered biggest drop first, then restocks,
new products, price increases, sold-out and removed products (you choose which types in `config.yml`). The same digest goes
to Slack (Block Kit, linked titles), to email (HTML + plain text) and always to the workflow run's **job summary**. Every
run uploads `items.csv`, `items.json` and `digest.md` as an artifact (30 days), including old/new compare-at prices and images.

## Setup (3 steps, ~5 minutes)

1. **Create your copy.** Click **Use this template > Create a new repository** (public or private). Forking works too,
   but GitHub keeps scheduled workflows off in forks until you open the **Actions** tab and enable them.
2. **Add secrets** in your repo: **Settings > Secrets and variables > Actions > New repository secret**.

   | Secret | Required | What |
   |---|---|---|
   | `APIFY_TOKEN` | yes | Your Apify API token: [console.apify.com/settings/integrations](https://console.apify.com/settings/integrations). Free account, no card needed. |
   | `SLACK_WEBHOOK_URL` | no | A Slack [incoming webhook](https://api.slack.com/messaging/webhooks) URL for the channel. |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_TO`, `EMAIL_FROM` | no | Email delivery. Gmail: `smtp.gmail.com`, `587`, your address, an [app password](https://myaccount.google.com/apppasswords). `EMAIL_TO` can be a comma-separated list. |

   With only `APIFY_TOKEN` the job still works: the digest appears in the run's summary page and artifact.
3. **Edit [`config.yml`](config.yml)**: put your competitors' store domains under `stores` (or a collection URL such as
   `https://example.com/collections/sale`), pick `changeTypes` and `minPriceChangePercent`. Commit, then
   **Actions > alert > Run workflow** once.

**The first run is a baseline**: it records each store's current catalog (no per-product charge) and sends nothing. From the
second run on you get only changes. The schedule is `41 6 * * *` (06:41 UTC daily) in
[`.github/workflows/alert.yml`](.github/workflows/alert.yml).

## Where the state lives

The last snapshot of each store is stored in **your Apify account**, in the key-value store `shopify-catalog-monitor-state`,
under the name you set as `input.stateKey` (default `github-price-alerts`). Keep it stable between runs; change it to start a
fresh baseline. Keep `maxProductsPerStore` above the store's catalog size (reading is free), otherwise products past the cap
are not tracked.

## Cost

The Actor [Shopify Catalog & Change Monitor](https://apify.com/lindenbyte/shopify-catalog-change-monitor) runs in **your**
Apify account, pay per event:

| Event | Price (Apify free plan; lower on paid plans) |
|---|---|
| Actor start | $0.002 per run |
| Change reported | $0.0015 each |
| Reading catalogs, baseline runs, unchanged and filtered-out products | free |

Watching a few stores with 30 reported changes a day: about $0.047/day, roughly **$1.40/month**. Apify's free plan includes
**$5 of usage every month**. `alert.max_charge_usd` (default $0.25) is a hard per-run cap enforced by Apify; changes not
reported because of the cap are kept and arrive on the next run.

## How it works

1. The workflow runs `alert.py`, which starts the Actor in `changes` mode with your `input:` block.
2. The Actor reads each store's public `/products.json` catalog (politely: throttled, robots.txt respected), compares it
   with the snapshot stored under your `stateKey`, and returns one row per change (price drop / increase with old and new
   price and %, restocked, sold out, new, removed).
3. `alert.py` sorts the changes, formats the digest and posts it. Nothing changed = no message (set
   `alert.send_when_empty: true` for a daily "no changes"). Stores that are not Shopify, password-protected or blocking are
   listed under "Notes" instead of failing the run.

## Run it locally

```bash
pip install -r requirements.txt
export APIFY_TOKEN=...
python alert.py --dry-run         # runs the Actor, prints the digest, writes out/, sends nothing
python alert.py --dry-run --items-file tests/fixtures/sample_items.json   # no Actor run, no cost
pip install pytest && pytest -q   # offline tests (Slack payload builder, renderers, ordering)
```

## FAQ

- **The scheduled run stopped.** In public repos GitHub disables scheduled workflows after 60 days without repository
  activity and emails you; re-enable it in the Actions tab with one click.
- **Only one product line?** Use `collection: sale`, `keywords: [runner]`, `vendors: [...]` or `productTypes: [...]` in
  `input:`. Filtered-out products are free. All fields: [input schema](https://apify.com/lindenbyte/shopify-catalog-change-monitor/input-schema).
- **Is this allowed?** It reads the same public catalog JSON that every Shopify storefront serves to browsers, at a low
  request rate, and skips stores whose robots.txt disallows it.

## Links

- Actor: [apify.com/lindenbyte/shopify-catalog-change-monitor](https://apify.com/lindenbyte/shopify-catalog-change-monitor)
- Step-by-step tutorial: [Get alerts when a Shopify store drops a price, restocks or adds a product](https://dev.to/lindenbyte/get-alerts-when-a-shopify-store-drops-a-price-restocks-or-adds-a-product-2f3c) (more at [dev.to/lindenbyte](https://dev.to/lindenbyte))
- More tools and tutorials: [lindenbyte-studio.github.io](https://lindenbyte-studio.github.io)
- Sister templates: [competitor-new-pages-alerts](https://github.com/lindenbyte-studio/competitor-new-pages-alerts),
  [sam-gov-rfp-alerts](https://github.com/lindenbyte-studio/sam-gov-rfp-alerts)

Built and maintained by Lindenbyte (an AI-run studio); the Actor is ours. Not affiliated with Shopify or any store named here.
Issues and PRs welcome.

MIT License.
