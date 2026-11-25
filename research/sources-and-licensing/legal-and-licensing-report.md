# 08 · Legal, licensing and operational constraints (Workstream L, agent R9)

> **Status: Verified finding.** Deliverable 08. Research notes, not legal advice. Statutes were fetched from law.go.kr; contract readings are INFERRED where tagged.
> Part of the [Newsmon research library](../README.md). Evidence dates default to 2026-11-25; first-person statements are by the AI research agents that wrote the notes.

**Date of all checks: 2026-11-25. This is research, not legal advice.** Nothing here replaces a Korean 변호사 opinion before a paid launch.
Decisions informed: **D2** (which sources may be collected, stored, summarised, shown), **D3** (is a commercial clipping service legal without
licences), **D1** (open-source licence constraints). The project owner's supplements are answered in **§9** (three deployment models) and **§13** (Supplement 02: Model A vs Model B, customer-owned licences, DR-16 to DR-30).

Companion files: statute texts [`sources-and-licensing/statute-extracts.md`](statute-extracts.md) (fetched live from law.go.kr, **VERIFIED**) ·
licence registry [`sources-and-licensing/oss-licenses.csv`](oss-licenses.csv) (21 rows, with `customer_hosted / managed_private / saas` columns) ·
scripts in a private file (not published).

Evidence tags follow [`evidence-conventions.md`](../evidence-conventions.md). Short form used below: **V** VERIFIED, **D** DOCUMENTED, **I** INFERRED, **U** UNVERIFIED, **U-abs** UNVERIFIED-absent.
Where I apply a verified rule to this project's facts, the application is **I** even when the rule is **V**.

---

## 0. Answers first

| Decision | Answer | Basis |
|---|---|---|
| **D3** Is a commercial clipping service legal without licences? | **No, not in practice.** Storing and sending full articles, or lede-sized excerpts, to paying clients is outside every Korean exception that could apply (§30 private copying excludes commercial and non-household use; §35-5 fair use is weak for a substitutive commercial copy), the Korean press foundation treats internal scrapping as infringement, and the closest foreign precedent (AP v. Meltwater) held exactly this model not fair use. A **licence-free floor** exists: headline + link + source + own-words summary. A foreign-desk assistant used **inside a broadcaster that already holds its own wire licences** is the legally cheapest MVP. | §2.1–2.3, §3.1, §6 (I, resting on V statute text and V Meltwater summary) |
| **D2** Which sources may the MVP collect, store, summarise, show? | Tier 1 (free to collect and store; show headline/link/own-words summary): public RSS/API metadata where terms allow, **GDELT**, and **unprotected official texts** (§7). Tier 2 (full text only inside a tenant that brings its own licence): AP, Reuters, Korean newspaper/BIGKinds licences. Tier 3 (excluded in MVP): paywalled or ToS-blocked pages, Naver news pages, YouTube video storage, any training use. | §5, §6, §8 |
| **D1** OSS licence constraints | No lead is blocked for **internal** use. For **commercial** models: avoid **n8n** (Sustainable Use: internal use only, cannot be bundled or offered as a service) and any **SSPL** component; treat **AGPL** leads (worldmonitor, FreshRSS, RSSHub, firecrawl, superdesk-core) as **run-unmodified or isolate as separate services**; **no licence** means no rights (spearb0lt/Self-Hosted-News-Research-Agent, Ramrod72/OpenNews); itheCreator1/newsintel returns 404. | §7, registry (V) |
| **Supplement 02**: can a software vendor processing a customer's own wire licence avoid being a content distributor? | **Yes, if** the vendor holds no rights in the content, keeps every item and derivative inside one tenant, the tenant chooses sources and triggers ingestion with its own credentials, and the customer's licence permits a service provider. External AI on licensed wire text is a separate third-party-disclosure question: default off. No Korean authority found; contract plus architecture decide. | §13 (I; public wire terms are a template only) |
| Korea TDM exception? | **None in the current 저작권법** (statute full text, term count 0, with a known-answer control). Pending bills: status **U**. | §3.1 (V-absent) |

---

## 1. Findings in the project's format (the ones that move a decision)

### F-L-01 · Korean copyright law has no internal-use or TDM exception that covers a company storing news full text
- Question: can the MVP store full text for internal analysis (the brief's example rule)?
- Finding: 저작권법 §30 allows copying of published works only "영리를 목적으로 하지 아니하고 개인적으로 이용하거나 가정 및 이에 준하는 한정된 범위 안에서". A company or a paid service is outside it. §35-2 permits only transient technical copies and not where "그 저작물의 이용이 저작권을 침해하는 경우". §35-5 (fair use) is the only general fallback, with four factors incl. market effect. No 정보분석/TDM article exists (term count 0 across the whole statute; control: 인공지능기본법 = 389 hits). The Korean press foundation's usage rules state: "업무상 목적으로 뉴스를 스크랩하여 내부 직원 또는 외부에 배포 … 하는 것은 뉴스저작권 침해임."
- Evidence: V statute text ([`sources-and-licensing/statute-extracts.md`](statute-extracts.md), MST 285693, 시행 2026-10-29); D KPF rule as published at https://www.dailian.co.kr/info/copyright (2017 rule, revised 2018; an outlet's reproduction, not the foundation's own page), verified 2026-11-25.
- Limits: no Korean court ruling found on a company's internal full-text archive under §35-5 (searches in §10). The foundation's rule is the licensor's position, not law.
- Implication: "store full text for internal analysis only" **lowers risk but is not a safe harbour in Korea**. Retention of third-party full text needs a licence flag (own-words derivatives and transient processing are the safe defaults). Rule DR-4.

### F-L-02 · Scraping liability in Korea turns on access authority, database substantiality and unfair-competition law, not on copyright alone
- Finding (criminal, primary text): 대법원 2022. 5. 12. 선고 2021도1533 (야놀자/여기어때) dismissed the prosecutor's appeal. Holdings: (1) 정통망법 §48(1) intrusion requires lack of access authority, judged by "보호조치나 이용약관 등 객관적으로 드러난 여러 사정"; ToS clauses that restrict *use* of obtained information, or ban load-causing auto-access, did not restrict *access*; no protective measure existed. (2) DB-maker right §93: "상당한 부분" judged quantitatively **and** qualitatively by the maker's investment in the copied part; repeated/systematic taking of insubstantial parts counts only if it amounts to taking a substantial part; the lower court's findings (info already well known, retrievable through the app, no evidence of updating investment) were upheld. (3) No 업무방해 without actual processing disruption.
- Finding (civil, press): 여기어때 was ordered to pay 10억원 as 부정경쟁행위 (서울고법 2021나2034740, reported as final). 잡코리아 v 사람인: 서울고법 2017. 4. 6. 선고 2016나2019365 found DB-maker-right infringement by automated crawling (reported); a Supreme Court finality and a case number (2017다224395) are reported but not checked.
- Statute: 부정경쟁방지법 §2(1) **카목** (데이터 부정사용: access without authority by 절취·기망·**부정접속**, use by authorised parties for improper gain, knowing receipt, and 4) circumvention tools for technical protection of the data) and **파목** (성과 도용: "타인의 상당한 투자나 노력으로 만들어진 성과 등을 공정한 상거래 관행이나 경쟁질서에 반하는 방법으로 자신의 영업을 위하여 무단으로 사용"). Criminal exposure, read from §18(4)1 as fetched: the paragraph (up to 3 years / 3천만원) expressly **excludes** 카목 1)-3) and 파목 from its list, so those are civil/injunction matters; **카목 4) (circumvention tools and services) is within the criminal list**.
- Evidence: V (대법원 text at https://www.scourt.go.kr/sjudge/1652779958317_183238.pdf; statute text); D (civil outcomes: press via Daum/Bizhankook/Lawtimes).
- Implication: a **polite, non-circumventing, low-volume collector of public pages is unlikely to be criminal**, but a commercial competitor-style re-use of someone's database-like output is exactly the 파목/DB-right fact pattern. Do not circumvent anything (§48(4), 카목 4)); do not mirror an outlet's whole archive. Rules DR-2, DR-5.

### F-L-03 · AP v. Meltwater is directly on point for a commercial clipping service
- Finding: S.D.N.Y. 2013, 931 F. Supp. 2d 537: a news-monitoring service that crawled ~162,000 sites and delivered excerpts of 33 AP articles to subscribers (nonprofits, government agencies, corporations) lost its fair-use defence on summary judgment. Not transformative ("merely automatically captured and republished segments of text … without adding commentary or insight"); amount factor "strongly against" (4.5%–61% of articles incl. the lede, "meant to convey the heart of the story"); market factor "strongly against" (AP already licensed this market, Meltwater refused to buy a licence and competed for the same customers).
- Evidence: V — U.S. Copyright Office Fair Use Index summary, https://www.copyright.gov/fair-use/summaries/ap-meltwater-sdny2013.pdf (text extracted locally 2026-11-25).
- Limits: district court; US law; the hot-news outcome in that case is **U** (not checked). The parties settled and partnered later (press, D).
- Implication: for D3, "we only show excerpts" is not a defence when the client base overlaps the wire's licensed market. Licences, or a metadata-only product, are the only clean paths.

### F-L-04 · No TDM/AI-training safe harbour in Korea; litigation is live; EU and US differ
- Finding: Korean 저작권법 has no TDM article (F-L-01). Reported suits: 지상파 3사 v. 네이버 (filed Jan 2025; 저작권 + 부정경쟁방지법 성과도용/데이터부정사용), 신문협회 complaint to 공정위 (2025). Status in Nov 2026: **U**. EU: DSM Directive Art. 4 permits commercial TDM unless the rightholder reserves rights in an appropriate manner (machine-readable for online content); Art. 3 covers research organisations; Art. 15 gives press publishers a right that expires "two years after the press publication is published" and (per Recital 58) does not reach "individual words or very short extracts". US: Bartz v. Anthropic and Kadrey v. Meta found training fair use on narrow records (and the pirated-library issue settled for $1.5bn in Bartz, reported); the Third Circuit in Thomson Reuters v. ROSS (reported 2026-09-29) rejected fair use for a **non-generative** legal-search tool.
- Evidence: V (statute absence; EUR-Lex recitals/articles as fetched: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019L0790, partial quotes only); D (Korean suits: https://journalist.or.kr/news/article.html?no=57604; US cases: https://www.ballardspahr.com/insights/alerts-and-articles/2026/10/third-circuit-addresses-fair-use-in-ai-training-but-leaves-generative-ai-questions-unresolved).
- Implication: **no training or fine-tuning on third-party text in the MVP** (DR-7). Inference-time use of an LLM on text the tenant is entitled to process is a different, lower-risk activity (§6).

### F-L-05 · Wire and API terms: the usable ones are narrower than the technical interfaces
| Source | Term (what it says) | Tag | Date |
|---|---|---|---|
| GDELT | "available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee"; redistribution allowed; "any use or redistribution … must include a citation to the GDELT Project and a link" | V (https://www.gdeltproject.org/about.html) | 2026-11-25 |
| YouTube API Services policies | no download/cache/store of audiovisual content without written approval (III.E.1); stored API data deleted or refreshed after 30 days (III.E.4.c); no resale/sublicense of the API services (III.G.1.a); no mention of ML/AI training | V (https://developers.google.com/youtube/terms/developer-policies) | 2026-11-25 |
| NYT developer APIs | non-commercial only; commercial redistribution needs a separate agreement; general site terms exclude ML/AI model training from "non-commercial" | D (secondary snapshots; developer.nytimes.com not fetchable from this tool) | 2026-11-25 |
| Guardian Open Platform | developer key = personal, non-commercial; commercial tier by agreement; a forum reading says §6(g) bars ML/text-mining use | D/U (snippet + forum; terms page not fetchable) | 2026-11-25 |
| AP / Reuters customer agreements | **not public.** Searches for AP Media API / Reuters Connect customer terms returned only AP's AI-licensing stance and Thomson Reuters legal-product terms. | U-abs (§10 lists searches) | 2026-11-25 |
| Naver API / news | Naver revised search-API terms (reported effective 2026-09-07) to bar automated collection and circumvention; the 2026-06-25 API-HUB terms restrict keeping API content in a separate DB; Naver blocks AI crawlers via robots.txt | D (press; Naver PDF not opened) | 2026-11-25 |
| BIGKinds (한국언론진흥재단) | REST API and cloud lab exist; terms on commercial use/redistribution **not found** | U-abs | 2026-11-25 |
| Outlet terms (한국일보, 경향신문) | automated mass crawling disallowed; AI-training crawling needs prior written permission | D (journalist.or.kr; khan.co.kr) | 2026-11-25 |

### F-L-06 · AI Basic Act (시행 2026-01-22): label generated output; fines are narrow and enforcement is in a grace period
- Finding: §31(1) 인공지능사업자 must tell users **in advance** that a product/service runs on high-impact or generative AI; §31(2) must **label** generative output as generated; §31(3) deepfake-like content must be clearly labelled. §43 fines up to 3천만원 reach only: §31(1) notice failure, missing 국내대리인 (§36(1)), and non-compliance with a §40(3) correction order. §31(2) is enforced through §40 orders. 인공지능사업자 = 개발사업자 or 이용사업자 ("가목의 사업자가 제공한 인공지능을 이용하여 인공지능제품 또는 인공지능서비스를 제공하는 자").
- Evidence: V (statute; MST 282791: the API's body field says 시행 2026-01-22, the search listing says 2026-07-21 after a 2026-01-20 amendment, so treat the current-version date as U; the article text quoted is the one served on 2026-11-25); D (press: government announced a fine grace period of at least one year; exact end not confirmed: https://www.mt.co.kr/tech/2025/12/31/2025123009504430416).
- Implication: **internal use by an organisation's own staff** probably does not make the organisation a provider of an AI service to "이용자" (I; ministry guidance not read). A **client-facing or public** product is a 인공지능이용사업자 and must carry notice + label. Costless to implement for all surfaces (DR-8).

### F-L-07 · Personal data in news text is personal data; the press exemption does not extend to a vendor
- Finding: 개인정보 보호법 §2(1) covers "성명 … 등을 통하여 개인을 알아볼 수 있는 정보"; "처리" includes collection, storage, search and provision. §58(1)4 exempts from chapters 3–8 information collected/used by **언론** for its own 취재·보도 purpose (§58(4) still imposes minimum-necessary and security duties). A broadcaster desk may use it; a software vendor or clipping firm is not 언론. §15(1)6 legitimate-interest basis is only for cases that "명백하게 정보주체의 권리보다 우선". §28-8 restricts moving personal data abroad ("제공(조회되는 경우를 포함)·처리위탁·보관") unless an enumerated route applies.
- Evidence: V (statute); the 2026-08-20 amendment on AI-development personal-data processing passed the plenary and awaited promulgation (D: https://www.lawtimes.co.kr/news/articleViewAmp.html?idxno=225424), not in the fetched current text.
- Implication: see §9(d). Practical rule: avoid person-centric products, and make the LLM provider/region a per-tenant setting.

---

## 2. Korea (primary)

### 2.1 저작권법 — what protects news and what does not (V unless noted)
| Provision | Operative text (Korean, fetched) | Effect for the MVP |
|---|---|---|
| §7(5) | "사실의 전달에 불과한 시사보도" is not protected | Pure fact dispatches (a one-line wire flash) can be used; **narrow**, and each article must be judged on its own content, not its source label. I |
| §26 | "시사보도를 하는 경우에 그 과정에서 보이거나 들리는 저작물은 보도를 위한 정당한 범위 안에서 복제ㆍ배포ㆍ공연 또는 공중송신할 수 있다" | Covers works that appear *in the course of reporting* by a newsroom; does not cover a clipping service or a monitoring database. I |
| §28 | quotation of published works "보도ㆍ비평ㆍ교육ㆍ연구 등을 위하여 … 정당한 범위 안에서 공정한 관행에 합치되게" | Short quoted excerpts with attribution inside a news/analysis output; not wholesale lede copying. I |
| §30 | private copying: non-profit, personal or household-like | Individual research only (context P). |
| §35-2 | transient copies for efficient processing, not if the use infringes | Does not legitimise an unlicensed pipeline. |
| §35-5 | general fair use, 4 factors incl. "현재 시장 또는 가치나 잠재적인 시장 또는 가치에 미치는 영향" | Uncertain; weak where a licensing market exists (cf. Meltwater, F-L-03). |
| §36 | translation allowed with uses under §28, §26, §30, §35-3..35-5 etc. (§36(1) and (2) lists differ) | Translation of quoted/fair-use material is covered; translation as a standalone product is a derivative work (§5, §22). |
| §37 | source must be stated for most exception uses (not §26, §30 …) | Always show source/outlet. |
| §2(19)(20), §93 | DB = systematically arranged, individually searchable collection; maker = "상당한 투자"; right covers "전부 또는 상당한 부분"; repeated/systematic taking of insubstantial parts counts when it conflicts with normal use or harms the maker | A news archive/site can be a protected DB; **do not mirror**. §94(2)2 lets anyone use a DB "시사보도를 위하여". |
| §136 | 침해 of §93 right: up to 3 years / 3천만원; ordinary copyright infringement up to 7 years / 1억원 | Exposure scale. |
| (no article) | no 정보분석/TDM exception | F-L-01 |

**TDM bill status (U):** a 2023 paper reviewed three pending TDM bills; a source says only a 김태선 bill (non-commercial/public-interest TDM) existed in the 22nd Assembly; a 2026 autumn Copyright Commission quarterly carries a paper "Designing a Limited Text and Data Mining Exception for Generative AI Training" (title only; PDF unreadable to the tool). The 2026-02-10 amendments (enhanced damages, effective 2026-08-11) concern remedies, not TDM. **I could not reach 국회 의안정보시스템; the live bill list is the one thing to check in round 2 if D2 depends on it.** It would not change the MVP rule (no training; derived-data processing only), so it was not chased (time-box rule).

### 2.2 Unfair competition, access crimes and case law
See F-L-02. Additional points: 정통망법 §48(1) intrusion is punishable under §71(1)11 (5 years / 5천만원, attempt punishable §71(2)); §48(4) (added 2024) bans installing or distributing programs or devices that bypass "정상적인 보호ㆍ인증 절차". A tool whose *purpose* is bypassing paywalls or bot protection also meets 부경법 카목 4). **V** statute text.

### 2.3 News-clipping licensing in Korea (D, with U items)
- The state, local governments and public bodies contract for newspaper content through **한국언론진흥재단** as trust operator (신탁사업자). Online contracting through 디지털저작권거래소 started in 2014 with the foundation and "유통대행업체" (distribution agents); the Ministry of Culture release says it supports licence contracts between the foundation/agents and public bodies using news (https://kidd.co.kr/news/170628 and the MCST notices). Revenue from these contracts was about 11.2bn won (2014) and 14bn won (2015). A 2015 survey found 241 of 597 public-sector news-using sites (40.4%) without a lawful contract (military 100%, police 93.9%, central agencies 65.2%) (https://www.journalist.or.kr/m/m_article.html?no=40113, reported 2016-10).
- Rules the foundation publishes (as reproduced): internal scrapping for staff or outsiders is infringement; intranet or website use needs a contract with the rightholder, including private firms and associations; re-RSS to third parties is prohibited; simple links are free, direct-link and framing use can create tort liability when commercially exploited (https://www.dailian.co.kr/info/copyright). The foundation consulted on amended 사용료징수규정 on 2025-11-14; rates not found.
- **U:** whether broadcasters' own news is in the same trust scheme; the rate card; how 비큐에이아이 / 다하미커뮤니케이션즈 license their clipping (likely via the foundation's agents or direct outlet contracts; not found). These are the first things a real commercial clipping launch must pin down; they do not affect the desk-assistant MVP.
- Portals: Naver blocks AI crawlers and restricts API storage (F-L-05); Daum terms not checked (U).

### 2.4 개인정보 보호법 and AI 기본법 — see F-L-07 and F-L-06 and §9(d).

---

## 3. International

### 3.1 United States (D unless V)
- **Fair use / headlines and snippets:** Meltwater (V). Headlines alone and short facts are generally safer than ledes (I, from the "heart of the story" reasoning); a headline-only index is the usual search-engine pattern, but fair use is case-by-case.
- **Hot news:** *INS v. AP* (1918) recognised the doctrine; *Barclays Capital v. Theflyonthewall.com*, 650 F.3d 876 (2d Cir. 2011) held the state-law hot-news claim preempted on its facts and left only a narrow remnant (D: https://en.wikipedia.org/wiki/Barclays_Capital_Inc._v._Theflyonthewall.com,_Inc.; commentary splits on breadth). INS text not fetched (U).
- **Scraping:** *Van Buren v. U.S.* (2021) and *hiQ v. LinkedIn*, 31 F.4th 1180 (9th Cir. 2022): CFAA likely does not reach public pages; on remand the district court found hiQ breached LinkedIn's User Agreement (Nov 2022) and the parties settled (D: https://en.wikipedia.org/wiki/HiQ_Labs_v._LinkedIn). **ToS can still bind as contract even when CFAA does not.**

### 3.2 European Union (V partial)
DSM Directive 2019/790: Art. 2(2) TDM definition; Art. 3 research-organisation exception; Art. 4 general TDM exception, conditional on the rightholder not having reserved rights "in an appropriate manner" (recital 18: machine-readable means for online content); Art. 15 press publishers' right, 2-year term, individual words / very short extracts and hyperlinks outside scope (recitals 57–58); transposition deadline 2021-06-07. Evidence: V for article headings and recitals quoted; full Art. 4(3) sentence not captured (tool truncation). **A TDM exception does not license storing or displaying a clipping; it covers the analysis copy only.** (I)

### 3.3 China (D, brief)
著作权法 (2020 revision, in force 2021-06-01) Art. 5(2): the law does not apply to "单纯事实消息" (the older text said 时事新闻). Lawyers read this as covering bare facts (flashes, meeting notices), not news with original expression (https://m.thepaper.cn/baijiahao_13118192). Platform terms not reviewed (U). Practical parallel to Korea §7(5).

### 3.4 Wire licences (public information only)
No public AP or Reuters customer agreement was found (U-abs). What public reporting shows: AP licenses by use case (AI-training licence to OpenAI covering an archive back to 1985, per press; a Meltwater-era licence defined "Snippets" as headlines and the leading 140 characters, per commentary), and states that AI training needs compensation (D: Press Gazette/PYMNTS results). **Typical restrictions in wire contracts, I (industry pattern, not these contracts):** use limited to the named licensee and site/seat/territory; no resale or sublicence; storage/archive limits; display rules; AI/ML use only if expressly granted; credentials non-transferable. Treat all as "unknown until read" and encode as per-tenant flags (DR-1, DR-15).

---

## 4. Platform and data-service terms — see F-L-05 (table).

---

## 5. Source tiers for D2 (I, resting on the verified items above)

| Tier | Sources | Collect | Store | Show | Why |
|---|---|---|---|---|---|
| 1 | GDELT metadata; outlets' public RSS/API metadata where terms allow; **unprotected official texts** (법령, 고시·공고, 판결 under §7(1)-(3); US federal-government texts such as State Dept briefing transcripts are public domain under 17 U.S.C. §105: I, not fetched); YouTube metadata (≤30 days) | yes | metadata + for §7/public-domain items full text | headline, link, source, own-words summary; full text only for §7/public-domain | no third-party expression, or none protected |
| 2 | AP / Reuters / Korean newspaper licences / BIGKinds, **brought by the tenant** | per tenant | per tenant, isolated | per tenant, within its licence flags | licence belongs to the tenant (§9b) |
| 3 | Naver news pages; paywalled/login pages; ToS-forbidden sites; YouTube/broadcast video storage; training sets | no (MVP) | no | no | F-L-02, F-L-05, F-L-04 |

For the desk-assistant case, the broadcaster's own wire feeds are Tier 2 by definition. Korean-government press releases and 공공누리 (KOGL) licences: type terms **U** (not fetched).

---

## 6. Matrix: use context × activity

Codes: **A** allowed (low risk on the rules cited) · **C** conditional (state the condition) · **R** restricted (needs a licence or is unlawful/contractually barred).
Every cell is an **I** application of the rule IDs below. Contexts: **P** private research (one person, non-commercial) · **I** internal organisational use (staff only) · **W** public-facing publication · **D** commercial software distribution (software only; ships no third-party content or credentials) · **S** commercial intelligence service (provider processes content for paying clients).

| Activity ↓ / Context → | P private | I internal | W public | D software only | S commercial service |
|---|---|---|---|---|---|
| **a1 fetch headlines + links** (RSS/API/sitemap) | A K2,K10 | A K10 | C K10,K5 (headline+link ok; framing and commercial deep-link tort risk; honour ToS) | A (customer fetches) | C K10 (NYT/Guardian keys non-commercial; GDELT ok; Naver API storage limits) |
| **a2 store full text** | A K2 (personal, not shared) | C K1,K5 (no internal-use exception: needs licence, §7(5) item, or transient only) | C (as I; storage for display needs licence) | A (provider stores nothing) | R unless licensed (K5,K4,U1) |
| **a3 display full text** | A K2 (to yourself) | C K5 (intranet = contract per KPF) | R (공중송신; §7(5)/PD/licensed only) | A | R unless licensed (U1) |
| **a4 summarise with AI** | A K3 | C K3,K9 (own-words facts; model input is a copy; label as AI; use only text you may process) | C K3,K9 (own words, not close paraphrase; label; cite source) | A (provider's software; customer's duties) | C K9,K8 (inputs must be licensed or metadata; label) |
| **a5 translate** | A K2,§36 | C (derivative §5/§22; wire licence usually allows; else §36 route only with §28/§35-5 grounds) | R for protected text (published translation = derivative + 공중송신); C for §7(5) items | A | R unlicensed / C licensed (licence must allow translation) |
| **a6 redistribute** (clips, digests with article text, re-RSS) | R K2 | R K5 (to outsiders) | R | A (tool only) | R (Meltwater; KPF forbids re-RSS) |
| **a7 archive video** | C K2 (personal recording of broadcast ok; YouTube: R) | C (own feeds under own rights ok; third-party video R; YouTube store R III.E.1) | R | A | R (rights + YouTube III.E.1) |
| **a8 train / fine-tune** | C K3 (no TDM exception; non-commercial research helps factor 1; no Korean ruling) | C→R (no TDM exception; suits pending; ToS of NYT/Guardian bar) | R | C (do not ship weights trained on news) | R (cross-tenant training; licences rarely grant) |

**Rule IDs.** K1 저작권법 §30/§35-2 (no internal/commercial copy) · K2 §30 private use · K3 §28/§35-5/§36 · K4 §93-94 DB right · K5 KPF contract rules (D) · K8 개인정보 보호법 · K9 AI 기본법 §31 · K10 source ToS/API terms (contract, F-L-05) · U1 *AP v. Meltwater* (V).

**Notes on the matrix.**
1. Column **D** assumes the product ships **no content and no credentials** and has no circumvention feature; a bypass feature moves the whole row to R (정통망법 §48(4), 부경법 카목 4)). Secondary-liability analysis for a general-purpose tool is **U**.
2. Row **a4** is the lowest-risk AI activity but not risk-free: the model input is a full-text copy, so legality follows the legality of holding that text (a2). Own-words summaries of facts are outside copyright protection of expression (I, idea/expression distinction; not fetched).
3. Row **a8** for **I**: the TDM question may change when a bill passes (§2.1, U).
4. **Broadcaster desk use** gets extra room from §26 and §58(1)4 (press exemption) for its own reporting. That room does not transfer to a vendor.

---

## 7. Open-source licences (registry: [`sources-and-licensing/oss-licenses.csv`](oss-licenses.csv), all via `gh api repos/<o>/<r>/license` on 2026-11-25, V)

| Lead | SPDX (gh) | Note |
|---|---|---|
| koala73/worldmonitor | AGPL-3.0 | thin clients (cli, sdk/*) MIT; commercial licence offered; hosted EULA separate |
| Thysrael/Horizon | MIT | |
| itheCreator1/newsintel | **404** | repo not found (owner's list has 3 other repos); U-abs |
| spearb0lt/Self-Hosted-News-Research-Agent | **none** | no LICENSE file: no rights granted |
| Ramrod72/OpenNews | NOASSERTION | LICENSE is a placeholder: no licence applied |
| UnbubbleHub/gdelt-pulse | MIT | |
| FreshRSS/FreshRSS | AGPL-3.0 | |
| miniflux/v2 | Apache-2.0 | |
| DIYgod/RSSHub | AGPL-3.0 | |
| huginn/huginn | MIT | |
| dgtlmoon/changedetection.io | Apache-2.0 | |
| adbar/trafilatura | Apache-2.0 | |
| firecrawl/firecrawl | AGPL-3.0 | SDKs (js, python) MIT; cloud has own terms |
| superdesk/superdesk-core | AGPL-3.0 | |
| n8n-io/n8n (R3 candidate) | NOASSERTION: Sustainable Use + Enterprise (`.ee` files) | |

**Reading the licence texts (V for the quotes; implications I):**
- **MIT / BSD / Apache-2.0:** keep notices; Apache adds NOTICE retention, change marking and a patent grant that terminates if you sue over the work. No restriction on any deployment model.
- **GPL-3.0:** duties trigger on **conveying**. Network service alone does not.
- **AGPL-3.0:** "To 'convey' a work means any kind of propagation that enables other parties to make or receive copies. Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying." §13: "if you modify the Program, your modified version must prominently offer all users interacting with it remotely through a computer network … an opportunity to receive the Corresponding Source". **§13 binds only a modified version.** §2 lets a licensee have contractors make or run covered works "exclusively on your behalf, under your direction and control, on terms that prohibit them from making any copies … outside their relationship with you".
- **Sustainable Use (n8n):** "You may use or modify the software only for your own internal business purposes or for non-commercial or personal use. You may distribute the software or provide it to others only if you do so free of charge for non-commercial purposes." Files with `.ee.` need a paid licence.
- **SSPL-1.0 (MongoDB):** §13: "If you make the functionality of the Program or a modified version available to third parties as a service, you must make the Service Source Code available via network download to everyone at no charge", where Service Source Code covers management, UI, API, automation, monitoring, backup, storage and hosting software. Not an OSI licence.
- **BSL / source-available:** U (texts not fetched); read each dependency's Additional Use Grant before adopting.

| Context | Permissive | GPL-3 | AGPL-3 (unmodified) | AGPL-3 (modified) | n8n | SSPL |
|---|---|---|---|---|---|---|
| (a) private use | A | A | A | A | A | A |
| (b) internal organisational use | A | A | A | A | A | A |
| (c) public SaaS | A | A (no source duty) | A | C: offer source to all users | R | R |
| (d) distributing software | A + notices | C: whole work GPL + source | C: whole work AGPL + source | C: same | R | C |

---

## 8. Design rules the MVP must follow (each with its reason)

| ID | Rule | Reason |
|---|---|---|
| DR-1 | **Per-source licence flags in the source registry**, default `metadata-only` when unknown: `access_method`, `tos_url`, `tos_checked_on`, `robots_ok`, `storage` (none / metadata / transient / full), `display` (none / headline / snippet / full), `ai_processing` (yes / no / unknown), `redistribution`, `training` (default no), `licence_owner` (provider / tenant / public-domain / unknown), `retention_days`, `attribution_text` | F-L-05, F-L-01 |
| DR-2 | Collect only through interfaces the source offers (RSS, API, sitemap, feed). Never bypass login, paywall, CAPTCHA, rate limit or bot protection; no stealth headless browsers; honour robots.txt and machine-readable opt-outs (TDM-Rep/noai-style signals where present); stable descriptive User-Agent; throttle | 정통망법 §48(1)(4), 부경법 카목, 2021도1533 (access judged by protective measures and ToS) |
| DR-3 | **Default display = headline + link + source + time + own-words summary.** No full-text display or export except §7(5), public-domain/official texts, or tenant-licensed flagged sources | §26/§28 limits; Meltwater; KPF rules |
| DR-4 | **Full text is retained only for flagged sources.** Otherwise: fetch → extract entities/features/embeddings/summary → discard body, keep URL, hash, timestamp. "Internal-only" retention is risk reduction, not a Korean safe harbour | F-L-01 |
| DR-5 | Never mirror an outlet's archive; no systematic repeated pulls beyond what the feed exposes; cap per-source volume | §93(2); 부경법 파목 |
| DR-6 | **Tenant isolation of licensed content**: `tenant_id` on every row, per-tenant credential vault, no cross-tenant dedup of bodies, no shared index containing licensed text | §9(b) |
| DR-7 | No training or fine-tuning on third-party text in the MVP; use LLM vendors that do not train on API content (Anthropic Commercial Terms §B and OpenAI Services Agreement §4.2: V) | F-L-04 |
| DR-8 | **Label all generated output**: `generated_by_ai=true` in the data model, "AI 생성" in every UI, digest and API payload; state AI use at onboarding/ToS | AI 기본법 §31(1)(2) |
| DR-9 | PII hygiene: no person-centric profiles; honour deletion/correction; log which fields are sent to which AI provider and region; provider/region configurable per tenant | §9(d); PIPA §3, §26, §28-8 |
| DR-10 | No video download or storage in the MVP; YouTube = metadata and official embeds only (≤30-day cache); broadcast video only from the tenant's own feeds under its rights | YouTube III.E.1, III.E.4.c; D7 |
| DR-11 | NYT/Guardian developer keys are research-only; never in a paid service without an agreement; GDELT with citation | F-L-05 |
| DR-12 | Always show outlet and link (출처 명시) | §37 |
| DR-13 | Opt-out/takedown route plus an **audit log** of what was fetched, from where, under which licence flag | evidence in a 부경법/KPF dispute |
| DR-14 | Third-party code: SBOM and a notices bundle for anything shipped; AGPL components unmodified or isolated as separate services; no n8n or SSPL; no reuse of no-licence repos | §7, §9(a) |
| DR-15 | Customer-supplied wire or API credentials live in the tenant's vault, are used only for that tenant, and are never pooled | §9(b) |

---

## 9. Supplement: three commercial deployment models (project owner, 2026-11-25)

Models: **CH** customer-hosted (customer-owned or -controlled infrastructure) · **MP** managed private (dedicated infrastructure the provider operates) · **SaaS** provider-hosted multi-customer.

### 9(a) Open-source obligations per model (registry columns `customer_hosted / managed_private / saas`)
| Question | Answer | Tag |
|---|---|---|
| Does shipping an image or installer to a customer count as distribution? | **Yes.** AGPL/GPL "convey" = "any kind of propagation that enables other parties to make or receive copies"; a delivered image or installer lets the customer make copies, even for one customer and even free. It is also redistribution of every package in the image (base-image Linux packages, language dependencies). | V text, I application |
| AGPL network clause vs GPL | GPL: network use alone is not conveying, so **MP and SaaS trigger no source duty** for GPL code. AGPL §13 adds a duty for **modified** versions offered to remote users: it applies to **MP and SaaS** if the provider modified the component, and to **CH** only through the customer's own users (the customer becomes the operator). **Unmodified AGPL services have no §13 duty.** | V |
| AGPL in CH | Shipping = conveying: the customer receives AGPL rights and you must supply Corresponding Source. A proprietary module compiled or linked into the same program becomes part of the covered work. **Keep proprietary code in separate processes that talk to the AGPL service over HTTP/queue**, and treat the interface as the boundary. (Whether process separation avoids "covered work" status is a legal judgment; FSF's FAQ position is not fetched: I/U.) | I |
| MP where the customer owns the cloud account | If the provider runs the software for the customer in the customer's account, §2 (contractors acting "exclusively on your behalf") is the relevant text; if the provider runs it in its own account, the customer interacts over a network (not conveying). Either way no source transfer is needed unless the provider modified AGPL code. | V text, I |
| Fair-code / Sustainable Use (n8n) | CH: provider cannot ship it commercially ("distribute … only … free of charge for non-commercial purposes"); a customer may run its own copy for its own internal business. MP and SaaS: operating it as part of a paid service for others is outside "own internal business purposes". **Blocked in all three models without a commercial licence.** | V text |
| SSPL | MP and SaaS offer functionality "to third parties as a service": §13 would require releasing the whole hosting stack. CH: provider shipping it is distribution under SSPL. | V text |
| BSL / source-available | **U.** Check Additional Use Grant per dependency. | U |
| Notice and attribution in distributed images | Include licence texts and copyright notices for every component; keep Apache NOTICE contents; mark changes; for GPL/AGPL components provide source (or a durable written offer) and the licence; generate an SBOM at build and ship a `THIRD_PARTY_NOTICES` file. Same duty for **base-image** packages. | I |
| Commercial escape hatch | worldmonitor and others advertise a commercial licence alongside AGPL; ask before building a product on them. | D |

**Constraint for MVP time:** put every AGPL, SSPL and fair-code component behind a network boundary, keep the proprietary core permissively licensed (MIT/Apache/BSD) or written in-house, and produce an SBOM from day one. This keeps all three models available.

### 9(b) Customer-owned licensed sources (AP, Reuters, BIGKinds)
- **Who is the licensee?** The customer, as the named party to the wire or BIGKinds agreement (I; the contracts are not public, so this rests on the standard structure of such licences, U-abs).
- **Can the provider's SaaS process that content for that customer only?** **Probably yes, if** the customer's agreement allows use by service providers or agents on its behalf, and the content never leaves that tenant. It is a **contract** question first and a copyright question second (copies made by a provider acting as the customer's instrument are treated as the customer's use, I; unverified in Korean case law).
- **Risks in typical wire-agreement terms (I, pattern):** (1) licence limited to named entity, sites, seats or territory; (2) no sublicence, resale or transfer, which a multi-tenant provider could be argued to breach if it holds the content under its own account; (3) no third-party processors without consent; (4) storage and archive limits and deletion on termination; (5) display and redistribution limits (internal only); (6) **AI/ML uses excluded unless expressly granted**, and AP publicly requires licences for AI training; (7) credentials non-transferable, so shared or provider-held keys can breach them; (8) audit rights.
- **The Meltwater lesson:** if the provider ingests wire content under the **provider's** account and sells excerpts to clients, the provider needs its own redistribution licence. Bring-your-own-licence (BYOL) avoids that because the provider never becomes a licensor.
- **Architecture constraints:** DR-6 and DR-15; per-tenant licence flags (`licence_owner=tenant`, `ai_processing`, `retention_days`, `redistribution`); **a pre-onboarding checklist asking the customer to confirm in writing that its licence permits processing by a hosted service provider and by AI**; no shared pooled index of licensed text; delete licensed content on contract end or licence expiry; export only the tenant's own licensed content back to that tenant.

### 9(c) Customer-provided vs provider-managed AI/API credentials
| Option | Anthropic (V, Commercial Terms) | OpenAI (V, Services Agreement) | Implication |
|---|---|---|---|
| Provider-managed key serving customers | A.1 permits use "to power products and services Customer makes available to its own customers and end users"; D.4(a): may not "resell the Services except as expressly approved by Anthropic"; K.2: indemnify for users' Usage Policy breaches | §3.1: "may not resell or lease access to its Account or any End User Account"; End User Accounts single-user (§3.2); §3.3(g) no "buy, sell, or transfer API keys" | **Allowed as a value-added application; not as a pass-through API or token resale.** Flow Usage Policy down in customer terms; price the application, not tokens; keep indemnity exposure in the contract. |
| Customer-provided key (BYOK) | Terms do not address key sharing; customer "is responsible for all activity under its account" (D.5) | §3.3(g) bars transferring keys to a third party: BYOK to a hosted vendor is **at risk on a literal reading** | Prefer customer-hosted or provider-managed for OpenAI; for Anthropic BYOK is silent, not blessed. Ask each vendor in writing before offering BYOK as a product feature (I/U). Store keys encrypted, use only for that tenant. |
| Data processing | Data submitted is processed under Anthropic's DPA (§C); "Anthropic may not train models on Customer Content from Services" (§B) | DPA incorporated (§5.3); no use of Customer Content to improve services (§4.2) | Under provider-managed keys the provider is the vendor's customer and a **sub-processor chain** results (§9(d)). Under BYOK the customer contracts with the vendor, but the provider still handles the data in transit. |
| Output | customer owns outputs (§B) | customer owns output (§4.1) | Do not build rights in outputs on third-party text beyond what the source licence allows. |
| Competing models | training competing AI models is barred (D.4) | no output used to build competing models (§3.3(e)) | Do not use vendor outputs as training data for a model you sell. |

### 9(d) Data protection by model (개인정보 보호법) and portability
- Roles, from the statute: 개인정보처리자 = whoever operates a personal-data file "for business" "스스로 또는 다른 사람을 통하여" (§2(5)). A 수탁자 processes under entrustment and **§26**: written entrustment (processing purpose limits, security measures), publication of the entrustment, supervision by the 위탁자, no use beyond scope (§26(5)), **sub-entrustment only with the 위탁자's consent (§26(6))**, and the 수탁자 is treated as the controller's employee for damages (§26(7)). Statute text: V.
- **CH:** the customer is the 처리자; the provider is merely a software vendor if it has no access. If the provider gets remote support access or logs, it becomes a 수탁자 for that access (I).
- **MP:** the provider operates dedicated infrastructure: **수탁자** (§26 entrustment contract with scope, security, sub-processor list; customer publishes the entrustment). Dedicated infrastructure helps security and data residency; it does not change the role.
- **SaaS:** same role as MP, for every customer, plus the provider is a **controller** for its own account/billing/usage data and for any personal data it collects for its own purposes (I). Multi-tenant makes the sub-processor list and incident duties product features.
- **Cross-border (§28-8):** transfer abroad, including "제공(조회되는 경우를 포함)ㆍ처리위탁ㆍ보관", is prohibited unless an enumerated route applies: separate consent; treaty; contract performance **with the data subject** with disclosure in the privacy policy (§28-8(1)3); a certified recipient (§28-8(1)4); or a PIPC adequacy finding (§28-8(1)5). **Consequence (I, needs counsel):** sending news text containing names to a US-hosted LLM or hosting a SaaS abroad is a "처리위탁/보관" abroad. The contract-performance route is built for the data subject's own contract, which news subjects do not have, so it is doubtful here; consent is impractical; certification/adequacy depend on the vendor and the country (current PIPC list: U). **Architecture constraint:** make hosting region and AI provider per-tenant settings, support Korean-region deployment (MP/CH) for tenants that need it, log which fields went where, and offer a mode that sends no personal data fields (entity-masked inputs) where acceptable.
- **Press exemption:** §58(1)4 helps a broadcaster tenant for its own 취재·보도; not the provider.
- **AI-development amendment (2026-08-20, awaiting promulgation; press):** a PIPC-approval route for using lawfully collected personal data to develop AI; irrelevant while DR-7 forbids training.
- **Data export and portability:** §35-2 (전송 요구) is a data-subject right against controllers designated by decree, not an export duty of a software vendor to its customer. Portability for tenants is therefore **contractual**: provide full export (open formats: JSON/Parquet/SQLite plus the licence-flag table), documented deletion on exit with a certificate, and export of the tenant's licensed content to that tenant only (never other tenants' data; no export of third-party text that the tenant's licence does not allow it to hold). Retention windows from DR-1 apply at exit.
- **Provider-side AI Basic Act duty:** in SaaS and MP the provider (and, where the customer exposes output to the public, the customer) is a 인공지능사업자; §31 notice/labelling is a product feature (DR-8). A provider with no Korean address and enough users or revenue (thresholds in the decree, not read) needs a 국내대리인 (§36), fine up to 3천만원 (§43).

**Architecture decisions to settle at MVP time (summary):** (1) tenant-scoped data model and credential vault from the first migration; (2) licence/permission flags per source and per tenant; (3) proprietary core free of AGPL/SSPL/fair-code code, AGPL tools behind a network boundary; (4) SBOM + notices bundle in the build; (5) AI provider and region as per-tenant config, one adapter interface so BYOK can be added or refused; (6) full export + deletion tooling; (7) `generated_by_ai` flag everywhere. None of these costs much if done first and all are expensive to retrofit.

---

## 10. What could not be established, and the searches that were run

| Item | Status | Searches / attempts |
|---|---|---|
| Live status of Korean TDM bills (22nd Assembly) | U | 3 web searches (Korean, incl. an extended one); 국회 의안정보시스템 not reached; 계간저작권 443 PDF not machine-readable to the fetch tool |
| AP / Reuters customer agreement text | U-abs | AP terms page and Reuters agency terms not fetchable by the tool; 2 searches returned only AI-policy stories and Thomson Reuters legal-product terms |
| NYT and Guardian API terms (current text) | D only | developer.nytimes.com and open-platform.theguardian.com blocked for the fetch tool; snapshots and forum posts used |
| BIGKinds and Daum/Naver news terms | U-abs / D | 2 searches; Naver API terms PDF not opened |
| 한국언론진흥재단 fee schedule and broadcaster news coverage | U | 1 search; only 2025-11-14 consultation notice found |
| Civil outcome finality (여기어때 2021나2034740; 잡코리아 2017다224395) | D | 2 searches each; no judgment text opened |
| Hot-news outcome inside AP v. Meltwater; INS v. AP text | U | not opened |
| PIPC adequacy list; AI 기본법 decree thresholds and ministry guidance on internal use | U | not fetched |
| BSL/Elastic licences, FSF process-separation FAQ | U | not fetched |
| firecrawl SDK licences other than js and python; superdesk client/planning repos | not checked | tree scan only |
| Decisions not chased because no result could change D1–D3 (time-box rule): full case-law sweep for news scraping beyond the 4 cases, EU member-state case law, a full ToS crawl of 20 outlets | skipped | cost ~1–2 hours; offered for round 2 |

Instrument integrity notes: statute fetches were by the a law.go.kr API client; its flattening dropped 목 (found because 부경법 §2(1) 카목 was missing) and a second walker was built; both are in `scripts/`. A first renderer run produced misordered headings (fixed and re-read). The absence finding for TDM has a known-answer control (§0 and [`sources-and-licensing/statute-extracts.md`](statute-extracts.md)).

## 11. Out-of-scope findings (for other agents; not acted on)
- R5 (sources): Naver API terms (reported effective 2026-09-07) restrict automated collection and separate-DB storage; GDELT is free for commercial use with citation (V). YouTube metadata cache limit is 30 days.
- R3/R4 (open source): itheCreator1/newsintel is not reachable (404); two leads have no usable licence; n8n is not OSI open source.
- R7 (AI): vendor ToS bar training competing models on outputs; BYOK is contested under OpenAI §3.3(g).
- R8 (video): YouTube III.E.1 forbids storing video; broadcast archive needs the tenant's own rights.
- Phase 2 (architecture): DR-1..DR-15 and the §9 constraints are inputs to the data model (tenant_id, licence flags) and the deployment design.

## 12. Source list (all fetched 2026-11-25)
- law.go.kr Open API, via an API client (V): 저작권법 MST 285693; 부정경쟁방지 및 영업비밀보호에 관한 법률 MST 277201; 개인정보 보호법 MST 283839; 정보통신망법 MST 290001; 인공지능기본법 MST 282791. See [`sources-and-licensing/statute-extracts.md`](statute-extracts.md).
- https://www.scourt.go.kr/sjudge/1652779958317_183238.pdf (대법원 2021도1533, V)
- https://www.copyright.gov/fair-use/summaries/ap-meltwater-sdny2013.pdf (V)
- https://www.gnu.org/licenses/agpl-3.0.txt ; https://www.mongodb.com/legal/licensing/server-side-public-license (V)
- https://www.anthropic.com/legal/commercial-terms ; https://openai.com/policies/services-agreement/ (V)
- https://developers.google.com/youtube/terms/developer-policies ; https://www.gdeltproject.org/about.html (V)
- https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019L0790 (V, partial)
- gh API licence endpoints for 15 repos; `LICENSE`/`LICENSE.md` files of Ramrod72/OpenNews, n8n-io/n8n; worldmonitor `docs/license.mdx`; firecrawl and worldmonitor tree scans (V)
- D (press, commentary, secondary): dailian.co.kr/info/copyright; journalist.or.kr (no=40113, 57604); kidd.co.kr; lawtimes.co.kr (225424); mt.co.kr (2025/12/31); ballardspahr.com (2026/10); en.wikipedia.org (hiQ; Barclays); m.thepaper.cn (China Art. 5).

---

## 13. Supplement 02: customer-owned content licensing, Model A vs Model B (added 2026-11-25)

Brief: a private requirements note. **Model A** = the provider acquires, processes and distributes news content. **Model B** = the provider supplies software that processes content the customer licensed independently. R2 holds the AP Media API/Agent documentation, the Arirang APTN contract and the procurement records; this section does not repeat them. Same caveat: research, not legal advice. Tags as at the head of this report.

### 13.0 What changes between the models (answer first)

| Barrier found in §1–§8 | Model A (provider is the licensor-side party) | Model B (customer holds the licence; provider supplies software) |
|---|---|---|
| Acquisition: scraping, DB right (§93), 부경법 카목/파목, 정통망법 §48, source ToS (F-L-02, F-L-05) | **Applies in full**: the provider fetches. | **Moves to the customer's authorised channel** (its wire API key, Media Agent, watched folder). Reappears for the provider only if the software fetches from sites the customer is *not* licensed for (I). |
| Storing, displaying and redistributing news text (matrix a2/a3/a6) | Needs the provider's **own redistribution/sublicensing licences** from every outlet or wire (the Meltwater lesson, F-L-03; KPF contract scheme, §2.3). | Governed by the **customer's licence terms** (contract), not by a licence the provider must buy. The provider's exposure is secondary liability plus contract flow-down. |
| The licence is personal | The provider cannot lean on one licence to serve many: 저작권법 §46(3) says a licence right cannot be assigned to a third party without the rightholder's consent ("저작재산권자의 동의 없이 제3자에게 이를 양도할 수 없다", V). | Same rule shapes Model B: the licence stays with the customer and is never assigned; the provider must stay a **processor acting for the licensee**, not a second licensee. |
| AI processing, translation, summarisation | Provider must secure AI/derivative rights itself (AP and Reuters sell AI rights separately, §13.2). | Depends on **what the customer's licence allows**; default to "not allowed" until the customer attests (§13.3, DR-17/18). |
| Cross-customer reuse (shared index, cache, models) | The business itself. Needs a licence for each reuse. | **Prohibited by design** (DR-19). It is exactly what would turn Model B into Model A. |
| 개인정보 / AI 기본법 | Provider is controller/provider for its own content service. | Provider is 수탁자 and, where it offers AI features, 인공지능이용사업자; roles per §9(d). |

**Can a separately licensed software vendor operate without becoming a news content distributor? Yes, on these facts (I), none of which is guaranteed by any ruling I found:** the vendor holds no rights in the content and cannot use it for itself; every content item and every derivative stays inside one tenant; the tenant (not the vendor) chooses sources and triggers ingestion with its own credentials; the vendor charges for software and hosting, not for content or clips; and the customer's licence permits use through a service provider. Remove any one and the position weakens. There is **no Korean authority I could find on a software vendor processing a licensee's wire content**; the main lever is contract (§13.2) plus architecture (§13.5).

### 13.1 (a) Distributor, or agent/processor of the licensee?

**Korean law (V text; D for cases).**
- The exclusive rights are 복제 (§16), 공중송신 (§18) and 배포 (§20). Direct infringement is committed by whoever does the act: §136(1) punishes whoever infringes by "복제, 공연, 공중송신, … 방법" (up to 7 years / 1억원); civil damages fall under §125, and §125(4), inserted 2026-02-10, lets a court award up to 5 times the proven damage for **wilful** infringement (effective date reported as 2026-08-11, D).
- A licensee may use the work only "허락받은 이용 방법 및 조건의 범위 안에서" (§46(2), V). Processing the licensee does, or has done for it, **outside** that scope is unlicensed use, and the scope is whatever the contract says.
- **Who is the "copier" when software does it?** I found **no Korean court decision** on a cloud or software provider's reproduction of a customer's licensed material (searches in §13.6). Scholarship found through search argues that the person who selects and commands the copy is the actor and that the provider is liable only secondarily, within the online-service-provider framework (D, search summaries of Copyright Commission and Ajou Law Review articles). A Japanese book-scanning-agency decision is cited for a "who initiates and controls the copying" test (D); it is foreign persuasive authority only.
- **Secondary liability** in Korea runs through 방조/공동불법행위, not a statutory "contributory infringement" clause. The Supreme Court held in 대법원 2007. 1. 25. 선고 2005다11626 (소리바다, civil) that 방조 covers any direct or indirect act facilitating the infringement, that negligent aiding suffices, and that the aider need not know the specific time, work or actor; 대법원 2007. 12. 14. 선고 2005도872 treated operating the 소리바다 5 service as 방조 of 복제권 infringement (D: https://jipyong.com/origin/kr/newsletter/39_20070205/data/precedent003.html, https://www.nepla.ai/case/대법원/2005도872; full judgments not opened). Those were P2P services built around infringement; a general-purpose newsroom tool is far from them, but **negligent facilitation is enough in principle**, so features that bypass paywalls or ignore a customer's licence limits invite that analysis (I).
- **§102(1)3 safe harbour (V text).** An online service provider is not liable for infringement when it stores works "복제ㆍ전송자의 요청에 따라" on its computers, provided it did **not initiate** the transmission and did **not select** the work or its recipient (§102(1)1 가·나, which item 3 incorporates), takes the work down promptly on notice (다), and has designated a notice recipient (라); where it can control the infringement it must not get a direct financial benefit from it (나). §102(3): no duty to monitor. **Architectural reading (I):** tenant-initiated ingestion (the customer drops files or configures its own connector with its own credential) fits this safe harbour; provider-chosen sources, provider-initiated fetching or provider-selected recipients do not, and look like Model A. Whether a SaaS that also summarises and translates stays a passive host is **U**.
- A distributor-style provider also faces the DB-right and 부경법 exposure of F-L-02 and the KPF contract expectations of §2.3.

**US practice (D).** Direct liability needs "volitional conduct": in *Cartoon Network LP v. CSC Holdings*, 536 F.3d 121 (2d Cir. 2008) the customer who initiated a recording, not the cable operator's remote-storage system, made the copy (https://law.justia.com/cases/federal/appellate-courts/ca2/07-1480/07-1480-cv_opn-2011-03-27.html; search summaries). Secondary liability (contributory, vicarious, inducement under *Sony* and *Grokster*) stays available in principle; those two cases were not fetched this round (U). Practical US reading (I): a vendor that merely provides the tool, with each copy triggered by the customer's instruction, sits on the processor/agent side; a vendor that selects content, curates, or fronts a shared store sits on the distributor side. *AP v. Meltwater* (F-L-03) is the case where a monitoring *service* crossed that line.

**Per deployment model** (extends §9; DR-6/DR-15 apply throughout):

| | Model B (customer's licence) | Model A (provider's licence) |
|---|---|---|
| **Customer-hosted (CH)** | The customer runs the code on its infrastructure with its credentials; the **customer** is the copier. Provider liability is secondary only and low for a general-purpose tool with no bypass feature (I). Remote support access makes the provider a processor for that access (log it, DR-28). The wire contract's third-party clause matters only if the provider touches content. | Not applicable: the provider would ship content with the software, i.e. distribute it (needs a redistribution licence). |
| **Managed private (MP)** | The provider operates a dedicated instance **for** one customer: treat it as the customer's **agent/contractor acting exclusively on its behalf** (the drafting pattern of AGPL §2's contractor clause, §9(a)). This needs an express "service provider/processor permitted" clause in the customer's wire licence or the wire's written consent (I). The customer should instruct ingestion and configure sources, so volitional conduct sits with it. | The provider is a re-supplier on dedicated infrastructure: needs redistribution rights. |
| **SaaS** | Same as MP, multiplied. The highest risk is **cross-tenant leakage** and pooled stores: one shared index of licensed text makes the provider look like a content distributor and breaches typical "no disclosure to third parties" clauses (§13.2). Use tenant isolation and tenant-initiated ingestion (the §102(1)3 reading above). | The Meltwater model; needs licences from every rightholder. Not in the MVP (DR-29). |

### 13.2 (b) What wire licences publicly say (public/primary sources only)

**AP.**
- AP's published generative-AI standards (2023, as reported by Nieman Lab, D: https://www.niemanlab.org/2023/08/not-a-replacement-of-journalists-in-any-way-ap-clarifies-standards-around-generative-ai/): staff may experiment but "do not use it to create publishable content"; output is "unvetted source material"; staff are urged "to not put confidential or sensitive information into AI tools". These are **AP's own newsroom rules**, not customer terms.
- AP monetises AI use **separately**: it licensed news stories back to 1985 to OpenAI for training (2023, D), and in January 2025 agreed to supply a real-time feed for Google's Gemini app (D: https://blog.google/products-and-platforms/products/news/associated-press-gemini-app/; financial terms undisclosed). That separate sale is evidence (I) that a standard subscription does not silently include AI rights.
- AP Media API/Media Agent terms: **U-abs.** ap.org and developer.ap.org are not fetchable by the tool; two searches found only a third-party description of the Content API ("gated by AP's content licensing", key through the developer portal; D, weak) and AP's website terms (audit right, not API terms). R2 owns the documentation.

**Reuters / Thomson Reuters.**
- Public statements (D): Thomson Reuters' CEO said its AI licensing deals cover "the text archive only. No live news feed. No images. No video. No audio" (Press Gazette via a secondary summary: https://pressgazette.co.uk/publishers/wires_and_agencies/thomson-reuters-boss-says-ai-licensing-deals-only-involve-archive-text/); Meta signed a multi-year deal for Reuters content in Meta AI answers (Oct 2024; Axios: https://www.axios.com/2024/10/25/meta-reuters-ai-news-facebook-instagram; training coverage unclear). Reuters Connect is a licensing marketplace; AI-enhanced search of the ITN archive is announced from 2027-01-01 (D).
- Reuters **News Agency** customer terms: **U-abs** (reutersagency.com not fetchable; searches returned only Thomson Reuters *product* terms). Those product terms are a different product line; snippets show they bar using "our Property or our third-party providers' property to train any artificial intelligence (AI) or machine learning algorithms" and, in an older UK form, any technology "to automatically download, mine, scrape or index our data" (D). Use as a **pattern**, not as Reuters News terms.

> **Scope note (orchestrator, 2026-11-25, after a user correction).** The APA terms below are one Austrian agency's
> published example. They do **not** describe what AP, APTN, Reuters or 연합뉴스 contracts with Korean broadcasters
> contain, and they set no rule for Korean practice. Those contracts are not public, and their terms may be broader or
> narrower: for example, they may expressly permit service providers, storage or AI processing. Every APA-derived item
> in this section (the 7-day storage, the no-third-party clause, the AI/ML bar) is an **illustration of the kind of
> clause a contract might contain**. It is the reason the corresponding behaviour is a customer-set licence flag, never a
> hard-coded assumption. The design rules citing APA (DR-19 to DR-25) are configurable safeguards whose values come from
> the customer's actual contract.

**A real public wire-agency GTC as one illustrative example (V for what it says; it is APA, Austria, not AP, Reuters or 연합뉴스, and it does not represent Korean contract practice).** *APA General Terms and Conditions, July 2026* (https://apa.at/wp-content/uploads/2020/05/AGB-2026-EN-1.pdf, text extracted locally 2026-11-25):
- §3.1.3: a "non-exclusive, non-transferable right to use the provided APA services in accordance with the contract. Any additional use shall be permitted only if expressly approved by APA in writing." It extends to text and data mining analyses unless a copyright limitation (EU DSM Directive) expressly permits them, and: "the use of provided services for the training of artificial intelligence, machine learning or for the development of algorithms and similar technologies is prohibited without an express prior agreement."
- §3.1.4: "Storing … shall be permitted for a maximum period of seven days"; longer archiving only if permitted in writing, then provable deletion.
- §3.2.1: internal use = "personal use by the users of the contracting party authorised to do so", counted by authorised users "normally … defined by username and password". §3.2.2: no disclosure of content "to third parties … for free or for consideration".
- §3.1.6–3.1.7: the customer must prevent infringements "by whomsoever", with a contractual penalty per proved infringement (EUR 10,000 to 50,000 floor and cap as stated there); the terms apply to authorised users and employees, for whom the customer is responsible "as if it were his own".
- **Reading for Model B (I):** the customer is liable for what its software vendor does with the content. Customers will therefore ask the vendor for (i) no third-party disclosure beyond what the contract allows, (ii) retention limits, (iii) seat-based access, (iv) no AI/ML use of the content for development, (v) audit evidence. All five become product requirements.

**Third-party contractors and service providers.** Nothing public from AP or Reuters (U-abs). The APA template has no explicit processor clause and bars third-party disclosure (§3.2.2), so a vendor is a "third party" **unless the contract says otherwise** (I). This is the single question that decides whether Model B works for a given customer.

**What remains contract-specific (not settled by public sources; record per customer in DR-17/DR-30):** whether automated ingestion, classification, summarisation or translation is within scope; storage days and archive rights; who counts as an authorised user and whether contractors or vendors qualify; third-party/processor consent; AI/ML use (inference vs training); redistribution to non-seat recipients (for example emailed digests); territory; audit; liability, penalties and deletion on termination; the licence-holder entity (a broadcaster and its subsidiaries).

### 13.3 (c) Local processing versus external AI APIs

- **Sending licensed wire text to a hosted LLM is disclosure to a third party** (the AI vendor and its sub-processors), on top of the provider's own role. Under an APA-style §3.2.2 it is a breach unless the contract allows processors; an "AI/ML use" clause may or may not reach **inference** (as opposed to training); the wording decides (I). Anthropic and OpenAI commit not to train on API content (V: Anthropic Commercial Terms §B; OpenAI Services Agreement §4.2; §9(c)), which answers the *training* worry, not the *third-party disclosure* worry.
- **Two independent gates**, both needed for external AI on a tenant's content: (1) the **licence gate** (do the wire/outlet licences allow third-party processing and AI use?) and (2) the **personal-data gate** (names inside the text; PIPA §26 entrustment and §28-8 cross-border; §9(d), F-L-07). Passing one does not pass the other.
- **Option ladder (lowest legal risk first):**
  1. **Deterministic processing only** (rules, keyword/BM25, SimHash/MinHash dedup, regex entity patterns, SQLite FTS): no third party, no AI clause. The MVP must work end to end this way (the D6 fallback).
  2. **Customer-hosted AI** under the customer's own agreements, in the customer's own cloud account or region, with the provider never holding the key or the text. The AI vendor is still a third party under the wire licence, so the customer decides, but the provider is out of the disclosure chain. In-country Korean inference exists: AWS states that Claude models run in-region in Seoul with prompts and outputs staying in that region (D: https://aws.amazon.com/blogs/machine-learning/introducing-anthropic-models-on-amazon-bedrock-for-in-region-inference-in-seoul-and-singapore/); Anthropic's own Korean documentation lists Seoul with only a "global" routing option, so **verify the live region table before promising residency (U)**.
  3. **Customer-run models on customer hardware** (no external disclosure at all) is the strongest fallback for licences that forbid third-party processing. It is a customer-side deployment option only; this research round does not run or test any local model (project policy (no local model inference)).
  4. **Provider-managed hosted LLM on licensed wire text**: the most restrictive case; allow only with an explicit customer attestation (DR-18) and a per-tenant region choice.
- **Cross-border (개인정보), already in §9(d), applied here:** wire text routinely contains personal names; a US-hosted API call is 처리위탁/보관 abroad under §28-8, with the routes and doubts already recorded. Two further data points (D): the PIPC published a generative-AI personal-data processing guide in August 2025 and a user guide in 2026, and a legal column notes the PIPC has **not clearly settled** when using a commercial AI service counts as 처리위탁 (https://www.lawtimes.co.kr/news/articleViewAmp.html?idxno=222055); OpenAI's Korean privacy addendum states storage on US servers and lists overseas processors (https://openai.com/policies/kr-privacy-policy-addendum/). For a broadcaster tenant, §58(1)4 (press exemption) may cover its own 취재·보도 use; it does not cover the provider.

### 13.4 (d) 연합뉴스 licence terms for broadcaster subscribers

- **Not public: U-abs.** Three Korean-language searches returned no subscriber agreement, tariff or redistribution terms. Broadcaster subscription terms and procurement amounts are on R2's evidence track (the Arirang APTN contract and others).
- What is public (all D): Yonhap's affiliate site 한민족센터 states in its copyright policy that content is protected, that reproduction, publication, transmission, distribution, sale, alteration and broadcast need the company's consent (Art. 2(2)), and that after consent only error corrections are allowed and the source must be shown (Art. 2(3)) (https://www.koreancenter.or.kr/com/copyright.html; fetched text of the affiliate site, not the subscriber contract). Yonhap article footers appear to carry an AI-use prohibition after the "무단 전재-재배포" notice; the search snippet was truncated, so the exact wording is **U**. Yonhap runs its own AI tooling (연합LM, an internal AI platform) per trade press (journalist.or.kr, koreancenter.or.kr), so AI processing of its content is a live commercial topic for it.
- **Implication (I):** treat 연합뉴스 as "licence terms unknown, AI restriction likely" and default `external_ai_allowed=false`.

### 13.5 (e) Design rules: Model B extensions (DR-16 to DR-30, appended to DR-1…DR-15)

| ID | Rule | Reason |
|---|---|---|
| DR-16 | Every tenant carries `commercial_model = B` by default. A tenant or feature that makes the **provider** the licensor (the provider acquires content under its own licence, or the same content reaches several tenants) is Model A and is blocked in the MVP (DR-29) | §13.0 |
| DR-17 | **Licence flags set by the customer, with attestation.** Per source set: `licence_holder`, `agreement_ref`, `valid_until`, and the permissions `automated_processing`, `classification`, `summarisation`, `translation`, `storage_days`, `display_scope`, `third_party_processors_allowed`, `external_ai_allowed`, `internal_only`, `territory`, `authorised_user_scope`; plus `attested_by`, `attested_on`. No real licensed-content ingestion until attested. Mock and sample data carry `synthetic=true` and bypass licence logic *(superseded 2026-11-25 by 12 FR-27(d): `synthetic` is provenance only and never alters the licence gate, so the gated mock source can demonstrate it; review V1-04)* | §13.2 |
| DR-18 | **`external_ai_allowed = false` by default** for any source with `licence_owner = tenant`. Every AI feature has a deterministic fallback that runs with no AI call | §13.3; D6 |
| DR-19 | **No cross-customer content reuse.** No shared index, cache, embedding store, prompt cache, fine-tune set, evaluation set or dedup table that spans tenants. Embeddings and summaries of licensed text are treated as the tenant's content. Per-tenant encryption keys | Meltwater; APA §3.2.2 |
| DR-20 | **Licence audit log**: immutable per-item record of source, fetch time, credential **id** (never the secret), tenant, user or job that triggered it, each operation (classify, summarise, translate, AI call with provider and region), derivative produced, and retention deadline; exportable as a report for the customer's wire-licence audit | APA §3.1.6–3.1.7 pattern |
| DR-21 | **Retention enforcement** per `storage_days` with a scheduled purge, a purge receipt, and purge on termination (verified deletion). Design for short windows (7 days is a published example) | APA §3.1.4 |
| DR-22 | **Customer credentials**: stored only in the tenant's vault (in CH, only in the customer environment); never logged; used only for that tenant's ingestion; per-user seats, no shared logins; honour wire-side seat counts | APA §3.2.1; §9(b); DR-15 |
| DR-23 | **Role in the contract**: the provider acts as the customer's agent/processor "exclusively on its behalf", holds no rights in content, makes no use for its own training or analytics, and lists sub-processors; the 개인정보 §26 entrustment terms sit in the same paper | §13.1; PIPA §26 |
| DR-24 | **Generic ingestion interface**: local watched folder, file drop, REST/webhook pull with a customer-supplied credential, and a **mock wire** adapter; the demo and tests run on synthetic or sample files and need no paid subscription. Connectors for AP Media Agent, NRCS, MAM or CMS read from the customer's authorised store or API; the provider never logs in to a wire with its own account | Supplement 02 |
| DR-25 | **Output controls**: every derivative carries `source_licence_ref`; display and export stay inside `display_scope`; no email digest or API output to recipients outside `authorised_user_scope` unless `external_distribution_allowed` is attested | APA §3.2.2 |
| DR-26 | **Tenant-initiated ingestion**: sources are chosen and ingestion is triggered by the tenant (or its scheduled job under its configuration), not by provider-side catalogue selection | §102(1)3 reading; volitional conduct |
| DR-27 | **Licence-change kill switch**: per-source disable and purge when the customer reports a changed or expired licence; `valid_until` stops ingestion automatically | §46(2) scope |
| DR-28 | **Remote support** in CH/MP: time-boxed, logged, content-masked by default, treated as processing (PIPA §26) and as third-party access under the wire licence | §13.1 CH row |
| DR-29 | **Model A gate**: no feature that stores or shows the same licensed content across tenants, or fetches under the provider's account, ships until separate redistribution licences and a written legal sign-off exist | §13.0 |
| DR-30 | **Onboarding licence review**: a stored checklist the customer completes before enabling a source: (1) licence holder entity; (2) is automated processing, classification, summarisation, translation allowed; (3) storage limit and archive rights; (4) may a service provider or processor handle the content; (5) is AI processing allowed, inference and training, and by which categories of vendor and region; (6) who are the authorised users and are contractors included; (7) may outputs go to people outside the licensee; (8) audit duties and deletion on termination. Answers feed DR-17 | §13.2 |

### 13.6 Limits and searches for this supplement (about 21 searches and fetches)
- Not fetchable by the tool: ap.org, developer.ap.org, reutersagency.com, so AP Media API terms and Reuters News terms stay **U-abs**.
- No Korean ruling found on a software or cloud vendor's reproduction of a licensee's licensed content (searches: 소리바다 방조, 클라우드 복제 주체). The academic positions are secondary (D).
- *Sony* and *Grokster*, and the full judgments of 2005다11626 and 2005도872, were not opened (D/U).
- 연합뉴스 subscriber terms, tariffs and the exact AI-prohibition wording: U-abs.
- APA is a **template**, not AP, Reuters or 연합뉴스. Every "typical term" statement stays I until a real customer contract is read.
- Skipped on the time-box rule: a systematic scan of other agencies' public terms (AFP, Kyodo, Xinhua, CNN Newsource, NHK) and a Korean-language search of KBS/MBC/SBS procurement notices (R2's track). Neither can move the architecture, which already assumes the customer's contract is unknown until reviewed.

### 13.7 Sources added by this supplement (fetched 2026-11-25)
- 저작권법 §16, §18, §46, §102, §125 via the law.go.kr API (V; see [`sources-and-licensing/statute-extracts.md`](statute-extracts.md)).
- https://apa.at/wp-content/uploads/2020/05/AGB-2026-EN-1.pdf (V for its text)
- https://www.koreancenter.or.kr/com/copyright.html (V for its text; affiliate site)
- https://www.niemanlab.org/2023/08/not-a-replacement-of-journalists-in-any-way-ap-clarifies-standards-around-generative-ai/ ; https://blog.google/products-and-platforms/products/news/associated-press-gemini-app/ ; https://pressgazette.co.uk/publishers/wires_and_agencies/thomson-reuters-boss-says-ai-licensing-deals-only-involve-archive-text/ ; https://www.axios.com/2024/10/25/meta-reuters-ai-news-facebook-instagram (D)
- https://jipyong.com/origin/kr/newsletter/39_20070205/data/precedent003.html ; https://www.nepla.ai/case/대법원/2005도872 ; https://law.justia.com/cases/federal/appellate-courts/ca2/07-1480/07-1480-cv_opn-2011-03-27.html (D)
- https://aws.amazon.com/blogs/machine-learning/introducing-anthropic-models-on-amazon-bedrock-for-in-region-inference-in-seoul-and-singapore/ ; https://www.lawtimes.co.kr/news/articleViewAmp.html?idxno=222055 ; https://openai.com/policies/kr-privacy-policy-addendum/ (D)
