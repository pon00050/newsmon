"""Experiment 1: (a) URL canonicalisation + exact content hash; (b) near-duplicate / syndication detection,
MinHash-LSH (datasketch) vs SimHash, on title+summary and on full text.
Usage: python -I -X utf8 dedup_experiment.py <corpus_dir> <out_dir>
Shingles: character 4-grams of NFKC-lowercased, whitespace-collapsed text (language-agnostic; works for KO/ZH
without a tokenizer). Exact Jaccard over all pairs is computed as the reference the approximate methods are scored
against (algorithmic recall); 'is it really a duplicate' precision comes from a hand-checked sample (labels.json)."""
import json, sys, re, hashlib, itertools, unicodedata, time, pathlib, random, collections
import urllib.parse
from courlan import normalize_url
from datasketch import MinHash, MinHashLSH
C, O = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
items = [json.loads(l) for l in open(C / "items.jsonl", encoding="utf-8")]
res = {"n_rows": len(items)}
# ---------- (a) URL canonicalisation ----------
TRACK = re.compile(r"^(utm_|fbclid|gclid|ocid|cmpid|ref$|ref_|rss|from$|input$|plink$|cooper$|mc_|ito$|at_)", re.I)
def canon(u):
    if not u: return None
    try: u = normalize_url(u, strict=False)
    except Exception: pass
    p = urllib.parse.urlsplit(u)
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    host = host[2:] if host.startswith("m.") else host
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if not TRACK.match(k)]
    path = re.sub(r"/amp/?$|\.amp$", "", p.path).rstrip("/") or "/"
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(sorted(q)), ""))
raw = [it["url"] for it in items]
can = [canon(u) for u in raw]
res["url_raw_distinct"] = len(set(raw)); res["url_canonical_distinct"] = len(set(can))
res["rows_with_url_seen_in_other_feed"] = sum(1 for u, n in collections.Counter(can).items() if n > 1)
merged_examples = []
grp = collections.defaultdict(set)
for r_, c_ in zip(raw, can): grp[c_].add(r_)
for c_, rs in grp.items():
    if len(rs) > 1 and len(merged_examples) < 8: merged_examples.append(sorted(rs))
res["canonicalisation_merged_examples"] = merged_examples
res["canonical_groups_with_multiple_raw_urls"] = sum(1 for rs in grp.values() if len(rs) > 1)
# keep one record per canonical URL
uniq = {}
for it, c_ in zip(items, can):
    it["canonical_url"] = c_
    uniq.setdefault(c_, it)
U = list(uniq.values())
def norm(t): return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t or "").lower()).strip()
for it in U:
    it["ts"] = norm(f"{it['title']} {it['summary']}")
    it["content_sha1"] = hashlib.sha1(it["ts"].encode()).hexdigest()
hc = collections.Counter(it["content_sha1"] for it in U)
res["unique_canonical_urls"] = len(U)
res["exact_content_dup_groups_title_summary"] = sum(1 for n in hc.values() if n > 1)
res["exact_content_dup_examples"] = [[(it["source"], it["canonical_url"], it["title"][:60]) for it in U if it["content_sha1"] == h][:3]
                                     for h, n in hc.items() if n > 1][:5]
# ---------- (b) near-dup ----------
def shingles(t, n=4):
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))}
def simhash(sh):
    v = [0] * 64
    for s in sh:
        h = int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big")
        for b in range(64): v[b] += 1 if (h >> b) & 1 else -1
    return sum(1 << b for b in range(64) if v[b] > 0)
def run(docs, label, min_chars):
    docs = [d for d in docs if len(d["text"]) >= min_chars]
    S = [shingles(d["text"]) for d in docs]
    t0 = time.perf_counter()
    J = {}
    for i, j in itertools.combinations(range(len(docs)), 2):
        a, b = S[i], S[j]; inter = len(a & b)
        if inter:
            jac = inter / len(a | b)
            if jac >= 0.2: J[(i, j)] = jac
    t_exact = time.perf_counter() - t0
    out = {"label": label, "docs": len(docs), "exact_pairs_time_s": round(t_exact, 2)}
    # MinHash LSH
    t0 = time.perf_counter()
    M = []
    for s in S:
        m = MinHash(num_perm=128, seed=1); m.update_batch([x.encode() for x in s]); M.append(m)
    t_sig = time.perf_counter() - t0
    out["minhash"] = {}
    for th in (0.5, 0.7, 0.9):
        t0 = time.perf_counter()
        lsh = MinHashLSH(threshold=th, num_perm=128)
        for i, m in enumerate(M): lsh.insert(str(i), m)
        cand = set()
        for i, m in enumerate(M):
            for k in lsh.query(m):
                k = int(k)
                if k != i: cand.add((min(i, k), max(i, k)))
        tq = time.perf_counter() - t0
        truth = {p for p, v in J.items() if v >= th}
        tp = len(cand & truth)
        out["minhash"][th] = {"candidates": len(cand), "exact_pairs_ge_th": len(truth), "recall_vs_exact": round(tp / len(truth), 3) if truth else None,
                              "precision_vs_exact": round(tp / len(cand), 3) if cand else None, "index+query_s": round(tq + t_sig, 3)}
    # SimHash
    t0 = time.perf_counter(); H = [simhash(s) for s in S]; t_sh = time.perf_counter() - t0
    out["simhash"] = {}
    ham = {}
    for i, j in itertools.combinations(range(len(docs)), 2):
        d = bin(H[i] ^ H[j]).count("1")
        if d <= 12: ham[(i, j)] = d
    for k in (3, 6, 10):
        cand = {p for p, d in ham.items() if d <= k}
        for th in (0.5, 0.7, 0.9):
            truth = {p for p, v in J.items() if v >= th}; tp = len(cand & truth)
            out["simhash"][f"k<={k}|J>={th}"] = {"candidates": len(cand), "recall_vs_exact": round(tp / len(truth), 3) if truth else None,
                                                 "precision_vs_exact": round(tp / len(cand), 3) if cand else None}
    out["simhash_sign_s"] = round(t_sh, 3)
    # pairs for hand check: Jaccard bands
    bands = collections.defaultdict(list)
    for (i, j), v in J.items():
        b = "0.9+" if v >= 0.9 else "0.7-0.9" if v >= 0.7 else "0.5-0.7" if v >= 0.5 else "0.3-0.5" if v >= 0.3 else None
        if b: bands[b].append((i, j, v))
    out["pairs_by_jaccard_band"] = {b: len(v) for b, v in bands.items()}
    random.seed(11); sample = []
    for b, v in sorted(bands.items()):
        for i, j, jv in random.sample(v, min(8, len(v))):
            sample.append({"band": b, "jaccard": round(jv, 3), "simhash_ham": bin(H[i] ^ H[j]).count("1"),
                           "a": {"src": docs[i]["source"], "lang": docs[i]["lang"], "url": docs[i]["url"], "text": docs[i]["text"][:300]},
                           "b": {"src": docs[j]["source"], "lang": docs[j]["lang"], "url": docs[j]["url"], "text": docs[j]["text"][:300]},
                           "cross_source": docs[i]["source"] != docs[j]["source"]})
    out["cross_source_pairs_J>=0.5"] = sum(1 for (i, j), v in J.items() if v >= 0.5 and docs[i]["source"] != docs[j]["source"])
    return out, sample
ts_docs = [{"text": it["ts"], "source": it["source"], "lang": it["lang"], "url": it["canonical_url"]} for it in U]
r1, s1 = run(ts_docs, "title+summary", 20)
ft = [json.loads(l) for l in open(C / "fulltext.jsonl", encoding="utf-8")] if (C / "fulltext.jsonl").exists() else []
ft_docs = [{"text": norm(r.get("text", "")), "source": r["host"], "lang": r["lang"], "url": r["url"]} for r in ft if r.get("chars", 0) > 300]
r2, s2 = run(ft_docs, "full_text", 300) if len(ft_docs) > 2 else ({"label": "full_text", "docs": 0}, [])
res["near_dup"] = [r1, r2]
(O / "dedup_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
(O / "handcheck_sample.json").write_text(json.dumps({"title+summary": s1, "full_text": s2}, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if "examples" not in k}, ensure_ascii=False, indent=1))
