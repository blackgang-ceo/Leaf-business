# LeafBlitz — business site

Single-file brutalist marketing site for **LeafBlitz**, the leaf-removal business of
Corinthian Brown (Montgomery, AL area). One page: instant price estimator ("Price
Puncher"), before/after slider, ZIP service-area checker, booking request flow and
contact details.

**Live site:** <https://blackgang-ceo.github.io/Leaf-business/> (GitHub Pages)

## Contact on the site (single source of truth)

| Channel | Value |
| --- | --- |
| Call / text | 334-777-3031 (`tel:+13347773031`) |
| Second line | 334-578-2252 (`tel:+13345782252`) |
| Email | Corinthianbrown@checkchasinempire.onmicrosoft.com |

The JS `CONTACT` object at the top of the main `<script>` in `index.html` drives every
dynamically built call/text/email link. Static links (`tel:`/`mailto:` hrefs, the JSON-LD
block and `tools/check_site.py`'s `REQUIRED_CONTACTS`) carry the same values — update all
of them together (run the checker afterwards; it fails if a contact detail goes missing).

## Repo layout

```
index.html              the whole site: markup, styles, estimator + booking JS
404.html                branded not-found page served by GitHub Pages
favicon.svg             icon (regenerate with tools/make_icons.py)
apple-touch-icon.png    iOS home-screen icon (regenerate with tools/make_icons.py)
robots.txt, sitemap.xml crawl hints for the published site
tools/check_site.py     static QA: tag balance, dead links, ids referenced by JS,
                        placeholder phone numbers, alt text, JSON-LD validity
tools/smoke_test.js     jsdom end-to-end run (estimator, booking, ZIP, FAQ, coupon)
                        with every CDN blocked -- also proves the no-CDN fallbacks
tools/make_icons.py     regenerates favicon.svg + apple-touch-icon.png (no deps)
tools/package.json      pins jsdom for the smoke test (node_modules/ is ignored)
.github/workflows/publish.yml   validate → deploy pipeline
```

## How publishing works

1. Push to `main` (or merge a PR into `main`).
2. `Publish LeafBlitz site` runs **validate** (`tools/check_site.py` on both pages,
   `node --check` on the inline JavaScript, JSON-LD parse) — it fails the build if a
   placeholder phone number or dead link ever lands on `main`.
3. **deploy** stages exactly `index.html 404.html favicon.svg apple-touch-icon.png
   robots.txt sitemap.xml` into `_site/` and publishes it with
   `actions/deploy-pages`. Nothing else (no `.git`, no `tools/`, no workflow files)
   is ever uploaded.

The workflow can also be triggered manually from the repo's **Actions** tab
(`workflow_dispatch`), and the validate job runs on every pull request without
deploying.

## Run it locally

Any static server works, e.g.:

```bash
python3 -m http.server 8080
# then open http://localhost:8080/
```

Run the QA checks locally before pushing:

```bash
python3 tools/check_site.py index.html
python3 tools/check_site.py 404.html

# optional end-to-end runtime test (needs node + one npm install)
cd tools && npm install && node smoke_test.js ../index.html
```

CI runs both static checks as *blocking* gates and the jsdom smoke test as an
advisory step (a flaky npm registry should never block a deploy, but a failing
smoke test is still shown in the run summary).

## What to edit for common changes

| Change | Where |
| --- | --- |
| Phone / email | `CONTACT` block in `index.html` + static `tel:`/`mailto:` hrefs + JSON-LD + `REQUIRED_CONTACTS` in `tools/check_site.py` |
| Service area | `SERVICE_AREA` (ZIP prefixes) and `SERVICE_TOWNS` (map grid) in `index.html` |
| Prices & multipliers | `CFG`, `DENS`, `FREQ`, `URG` objects + the `hasOfferCatalog` prices in the JSON-LD block |
| Reviews | `testis` array (add a real photo URL as `img` and it replaces the initials badge) |
| Hours | `openingHoursSpecification` in the JSON-LD block (currently Mon–Sat, matching the site's "Sundays we rest" copy) |
| Booking copy / guarantees | the `#bSuccess` panel and the FAQ array |

The site has **no backend**: a completed booking request is packaged into pre-addressed
`mailto:` / `sms:` / `tel:` links plus a copy-to-clipboard button, so the lead lands in
dispatch's inbox or phone instead of vanishing. The ZIP checker and slot picker are
estimators, not live inventory.

## Open items to confirm before treating the site as final

These shipped as sensible, clearly-marked defaults — confirm or correct them:

1. **Service area.** `SERVICE_AREA` defaults to central/east Alabama ZIP prefixes
   (matching the 334 phone numbers) and `SERVICE_TOWNS` lists central-AL towns. Adjust
   to the territory actually served.
2. **Reviews.** The five reviews in `testis` are samples with initials badges (the old
   version used random stock faces from i.pravatar.cc). Replace them with real,
   permissioned customer quotes; "★★★★★ BLITZ REVIEW" is deliberately not a "verified"
   claim until they are.
3. **Marketing numbers.** Counters and copy (yards blitzed, compost tonnage, crew and
   truck counts, response times) came from the original template. Verify or adjust
   them; they are business claims.
4. **Hours.** JSON-LD says Mon–Sat 08:00–18:00 from the "Sundays we rest" copy.
5. **Tailwind CDN.** The page uses `cdn.tailwindcss.com` (the JIT build that prints a
   console warning). Swapping to a compiled CSS file was deliberately *not* done yet:
   it changes the rendering engine and there is no browser in this repo's CI to verify
   it visually.
