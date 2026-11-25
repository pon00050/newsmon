"""Breakdown of near-duplicate pairs (title+summary, char-4-gram Jaccard >= 0.5) by kind:
same registrable domain (e.g. iheart.com station subdomains), same publisher RSS (revisions such as Yonhap '(종합)'),
cross-publisher. Also tests whether stripping a ' | site name' title suffix changes pair counts.
Usage: python -I -X utf8 syndication_breakdown.py <corpus_dir> <out_json>"""
import json, sys, re, itertools, unicodedata, collections, pathlib
C = pathlib.Path(sys.argv[1])
items = [json.loads(l) for l in open(C / "items.jsonl", encoding="utf-8")]
seen, U = set(), []
for it in items:
    if it["url"] not in seen:
        seen.add(it["url"]); U.append(it)
def reg(src):
    s = src.lower().split(":")[0]; parts = s.split(".")
    return ".".join(parts[-3:]) if len(parts) > 2 and parts[-2] in ("co", "com", "ac") else ".".join(parts[-2:]) if "." in s else s
def norm(t, strip_suffix=False):
    if strip_suffix: t = re.sub(r"\s[|\-–]\s[^|\-–]{2,40}$", "", t)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", t or "").lower()).strip()
def sh(t): return {t[i:i + 4] for i in range(max(1, len(t) - 3))}
out = {}
for strip in (False, True):
    S = [sh(norm(f"{u['title']} {u['summary']}", strip)) for u in U]
    kinds = collections.Counter(); ex = collections.defaultdict(list)
    for i, j in itertools.combinations(range(len(U)), 2):
        a, b = S[i], S[j]; inter = len(a & b)
        if not inter: continue
        jac = inter / len(a | b)
        if jac < 0.5: continue
        si, sj = U[i]["source"], U[j]["source"]
        if si == sj: k = f"same_source:{U[i]['origin']}"
        elif reg(si) == reg(sj): k = "same_registrable_domain"
        else: k = f"cross_publisher:{U[i]['origin']}-{U[j]['origin']}:{U[i]['lang']}"
        kinds[k] += 1
        if len(ex[k]) < 4: ex[k].append([round(jac, 2), si, U[i]["title"][:70], sj, U[j]["title"][:70]])
    out["strip_title_suffix" if strip else "raw"] = {"pair_counts": dict(kinds), "examples": dict(ex)}
    pub = collections.Counter(reg(u["source"]) for u in U if u["origin"] == "gdelt")
    out["gdelt_items_by_registrable_domain_top"] = pub.most_common(8)
    out["gdelt_items"] = sum(pub.values()); out["gdelt_distinct_hosts"] = len({u["source"] for u in U if u["origin"] == "gdelt"}); out["gdelt_distinct_registrable"] = len(pub)
pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1))
