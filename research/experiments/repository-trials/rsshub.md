# Trial — DIYgod/RSSHub as an npm library (R3, 2026-11-25)

> **Status: Experimental result.** Trial of an existing open-source tool in an isolated environment.
> Part of the [Newsmon research library](../../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Verdict from the trial:** works without Docker, **but only on Node 26** (the package's `engines` is `node ^26.13.0`).
On this machine's Node 22.16 every route fails with `ReferenceError: Temporal is not defined`. **TESTED.**

## Exact commands
```
mkdir <scratch>/rsshub_pkg && cd <scratch>/rsshub_pkg && npm init -y
npm install rsshub@2026.11.25-8754.gc85357b --ignore-scripts --no-audit --no-fund   # >3 min, 431 packages; install scripts disabled
# script kept OUTSIDE the download dir: rsshub_trial.mjs (copy in this folder) imports dist-lib/pkg.mjs and calls init()/request()
MSYS_NO_PATHCONV=1 node rsshub_trial.mjs /yna/en/national /yna/nonexistent-lang-zz          # Node 22.16 -> run_node22.txt
mkdir <scratch>/node26 && cd <scratch>/node26 && npm install node@26                          # portable Node v26.13.1 binary
MSYS_NO_PATHCONV=1 <scratch>/node26/node_modules/node/bin/node.exe rsshub_trial.mjs /yna/en/national /yna/nonexistent-lang-zz   # -> run_node26.txt
```
(Git Bash rewrites `/yna/...` into a Windows path unless `MSYS_NO_PATHCONV=1` is set. The first attempt hit this.)
Each run exits by itself (`process.exit(0)`); no server process was left running.

## Results
| Run | Route | Result |
|---|---|---|
| Node 22.16 | `/yna/en/national` | 0 items after 18 s; log: `ReferenceError: Temporal is not defined` |
| Node 26.13.1 | `/yna/en/national` | **116 items**, title "Yonhap News Agency \| National", 19.7 s, items carry title/link/pubDate |
| Node 26.13.1 | `/yna/nonexistent-lang-zz` (nonsense control) | 0 items; DNS failure logged |

## Findings
1. **Failure is returned as success.** `request()` resolved normally with **0 items** for both a broken runtime (Node 22)
   and a nonsense route; the error is only in the log (HTTP 503 internally). A pipeline using the library must treat
   "0 items" as a possible failure and read the status, or it will report outages as quiet news. **TESTED.**
2. **Routes can amplify traffic.** The `yna` route reads the RSS and then fetches **every article page** for full text
   (`fetchArticleDetails(item.link)` inside `cache.tryGet`, `lib/routes/yna/index.ts`, VERIFIED at master 2026-11-25).
   This trial therefore made ~117 requests to en.yna.co.kr (robots.txt disallows only Korean-desk `/view/AKR*` etc.,
   not `/view/AEN*`). With `CACHE_TYPE` empty, RSSHub also warns that concurrency is not limited. Use a cache
   (memory/Redis) and per-route review before continuous polling.
3. Route coverage relevant to the desk (route namespaces listed from the git tree of `lib/routes`, 2,008 entries, not
   truncated): `apnews`, `reuters`, `yna`, `kbs`, `koreaherald`, `naver`, `daum`, `whitehouse`, `un`, `nhk`,
   `kyodonews`, `bbc`, `aljazeera`, `nytimes`, `wsj`, `ft`, `bloomberg`. Not run: `apnews` (its robots.txt disallows
   `/*.rss`, and the topics route scrapes article pages). Absent from the namespace list: `ytn`, `chosun`, `tvchosun`,
   `joongang`, `donga`, `hani`, `mbc`, `sbs`, `jtbc`, `state` (grep of the full namespace list; UNVERIFIED-absent for
   routes that may live under other names).

## Implication (D1)
**Integrate as component** (source adapter for sites without usable feeds), run as a separate Node 26 service or
container. AGPL-3.0: running it unmodified as a separate network service is the low-risk pattern; modifying it and
offering it over a network triggers source-disclosure duties (R9 to confirm).

API spend: $0.
