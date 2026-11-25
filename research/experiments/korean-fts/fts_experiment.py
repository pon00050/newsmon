"""Experiment 3: is SQLite FTS5 adequate for Korean/Chinese search in an MVP?
Tokenizers compared on the KO and ZH items of the R6 corpus (title + summary):
  A unicode61 (default)            B unicode61 with prefix query (term*)
  C trigram                        D CJK char-bigram pre-tokenised (deterministic, Lucene-CJKAnalyzer style) in unicode61
  E jieba pre-tokenised (ZH only; dictionary + HMM, non-neural)
Ground truth per query = documents whose text contains the query string as a substring (Python `in`).
Known-answer queries must hit; nonsense queries must return 0.
Usage: python -I -X utf8 fts_experiment.py <items.jsonl> <out_dir>"""
import json, re, sqlite3, sys, time, pathlib, unicodedata
import jieba
jieba.setLogLevel(60)
items = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
out = pathlib.Path(sys.argv[2])
seen, docs = set(), {"ko": [], "zh": []}
for it in items:
    if it["lang"] in docs:
        t = unicodedata.normalize("NFC", f"{it['title']} {it['summary']}".strip())
        if t and t not in seen:
            seen.add(t); docs[it["lang"]].append(t)
CJK = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯一-鿿㐀-䶿]+")
def bigrams(text):
    out_ = []
    for tok in re.findall(r"[ᄀ-ᇿ㄰-㆏가-힯一-鿿㐀-䶿]+|[A-Za-z0-9]+", text):
        if CJK.fullmatch(tok):
            out_ += [tok] if len(tok) == 1 else [tok[i:i + 2] for i in range(len(tok) - 1)]
        else:
            out_.append(tok.lower())
    return " ".join(out_)
def bigram_query(q):  # phrase of consecutive bigrams
    b = bigrams(q).split(); return '"' + " ".join(b) + '"'
def jieba_tok(text): return " ".join(w for w in jieba.cut(text) if w.strip())
QUERIES = {
 "ko": {"known": ["트럼프", "우크라이나", "러시아", "김정은", "북한", "미국", "중국", "대통령", "이스라엘", "젤렌스키"],
        "nonsense": ["퀭뷁줆", "zxqvbnm", "똠얌꿍칼국수"]},
 "zh": {"known": ["特朗普", "乌克兰", "俄罗斯", "中国", "美国", "华为", "北约", "日本", "以色列", "习近平"],
        "nonsense": ["龘靐齉", "zxqvbnm", "鑫淼焱垚"]},
}
results = []
for lang, D in docs.items():
    con = sqlite3.connect(":memory:")
    con.execute("create virtual table u using fts5(t, tokenize='unicode61')")
    con.execute("create virtual table g using fts5(t, tokenize='trigram')")
    con.execute("create virtual table b using fts5(t, tokenize='unicode61')")
    con.executemany("insert into u(rowid,t) values(?,?)", enumerate(D))
    con.executemany("insert into g(rowid,t) values(?,?)", enumerate(D))
    con.executemany("insert into b(rowid,t) values(?,?)", [(i, bigrams(d)) for i, d in enumerate(D)])
    if lang == "zh":
        con.execute("create virtual table j using fts5(t, tokenize='unicode61')")
        con.executemany("insert into j(rowid,t) values(?,?)", [(i, jieba_tok(d)) for i, d in enumerate(D)])
    methods = {
        "A_unicode61": lambda q: con.execute("select rowid from u where u match ?", (f'"{q}"',)).fetchall(),
        "B_unicode61_prefix": lambda q: con.execute("select rowid from u where u match ?", (f'"{q}"*',)).fetchall(),
        "C_trigram_match": lambda q: con.execute("select rowid from g where g match ?", (f'"{q}"',)).fetchall(),
        "C2_trigram_LIKE": lambda q: con.execute("select rowid from g where t like ?", (f"%{q}%",)).fetchall(),
        "D_bigram_pretok": lambda q: con.execute("select rowid from b where b match ?", (bigram_query(q),)).fetchall(),
    }
    if lang == "zh":
        methods["E_jieba_pretok"] = lambda q: con.execute("select rowid from j where j match ?", ('"' + jieba_tok(q) + '"',)).fetchall()
    for kind in ("known", "nonsense"):
        for q in QUERIES[lang][kind]:
            truth = {i for i, d in enumerate(D) if q.lower() in d.lower()}
            for m, f in methods.items():
                t0 = time.perf_counter()
                try:
                    hits = {r[0] for r in f(q)}; err = None
                except sqlite3.Error as e:
                    hits, err = set(), str(e)
                ms = (time.perf_counter() - t0) * 1000
                tp = len(hits & truth)
                results.append({"lang": lang, "kind": kind, "query": q, "qlen": len(q), "method": m, "truth": len(truth),
                    "hits": len(hits), "tp": tp, "recall": round(tp / len(truth), 3) if truth else None,
                    "precision": round(tp / len(hits), 3) if hits else None, "ms": round(ms, 2), "error": err})
    print(lang, "docs", len(D))
(out / "fts_results.json").write_text(json.dumps({"docs": {k: len(v) for k, v in docs.items()}, "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
# summary table
import collections
agg = collections.defaultdict(lambda: [0, 0, 0, 0, 0])  # tp, truth, hits, nonsense_hits, zero_recall_queries
for r in results:
    a = agg[(r["lang"], r["method"])]
    if r["kind"] == "known":
        a[0] += r["tp"]; a[1] += r["truth"]; a[2] += r["hits"]; a[4] += (r["truth"] > 0 and r["tp"] == 0)
    else:
        a[3] += r["hits"]
lines = ["| lang | method | micro-recall (tp/truth) | micro-precision | known queries with 0 hits | nonsense hits |", "|---|---|---|---|---|---|"]
for (lang, m), a in sorted(agg.items()):
    lines.append(f"| {lang} | {m} | {a[0]}/{a[1]} = {a[0]/a[1]:.3f} | {(a[0]/a[2]) if a[2] else float('nan'):.3f} | {a[4]} | {a[3]} |")
lines += ["", "| lang | query | len | truth | " + " | ".join(sorted({r['method'] for r in results})) + " |"]
lines.append("|---|---|---|---|" + "---|" * len({r['method'] for r in results}))
byq = collections.defaultdict(dict)
for r in results: byq[(r["lang"], r["kind"], r["query"], r["qlen"], r["truth"])][r["method"]] = f"{r['tp']}/{r['hits']}"
for (lang, kind, q, ql, tr), d in byq.items():
    lines.append(f"| {lang} | {q}{' (nonsense)' if kind=='nonsense' else ''} | {ql} | {tr} | " + " | ".join(d.get(m, "n/a") for m in sorted({r['method'] for r in results})) + " |")
(out / "fts_summary.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
