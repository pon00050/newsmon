"""Follow-up to cluster_experiment.py (deterministic, no API calls; reuses cached embeddings and gold labels).
 1. Incremental embedding clustering with a separate, lower threshold for cross-language matches (theta_x) than for
    same-language matches (theta_s): cross-lingual cosine scores from text-embedding-3-small run lower.
 2. The same metrics with the 19-item Huawei event removed, because it alone holds 171 of the 327 gold pairs.
 3. Distribution of cosine similarity for gold same-event pairs: same-language vs cross-language.
Usage: python -I -X utf8 cluster_variants.py"""
import json, itertools, collections, pathlib, datetime as dt
import numpy as np
H = pathlib.Path(__file__).parent; G = H / "gold"
gold = json.loads((G / "gold_items.json").read_text(encoding="utf-8"))
lab = json.loads((G / "gold_labels_llm.json").read_text(encoding="utf-8"))["labels"]
lab.update(json.loads((G / "gold_label_corrections.json").read_text(encoding="utf-8")))
gold.sort(key=lambda g: g["published"])
E_all = np.load(G / "embeddings.npy"); eids = json.loads((G / "embedding_ids.json").read_text())["ids"]; ix = {k: i for i, k in enumerate(eids)}
def prep(gs):
    E = np.stack([E_all[ix[g["item_id"]]] for g in gs]); E /= np.linalg.norm(E, axis=1, keepdims=True)
    return E, np.array([dt.datetime.fromisoformat(g["published"]).timestamp() for g in gs]), [g["lang"] for g in gs], [lab[g["gid"]] for g in gs]
def metrics(pred, truth, langs):
    tp = fp = fn = xt = xtp = 0
    for i, j in itertools.combinations(range(len(pred)), 2):
        st, sp = truth[i] == truth[j], pred[i] == pred[j]; tp += st and sp; fp += sp and not st; fn += st and not sp
        if st and langs[i] != langs[j]: xt += 1; xtp += sp
    P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
    cp, ct, cj = collections.Counter(pred), collections.Counter(truth), collections.Counter(zip(pred, truth)); n = len(pred)
    bp = np.mean([cj[(pred[i], truth[i])] / cp[pred[i]] for i in range(n)]); br = np.mean([cj[(pred[i], truth[i])] / ct[truth[i]] for i in range(n)])
    return {"pair_P": round(P, 3), "pair_R": round(R, 3), "pair_F1": round(2 * P * R / (P + R), 3) if P + R else 0, "bcubed_F1": round(2 * bp * br / (bp + br), 3),
            "xling_pair_recall": round(xtp / xt, 3) if xt else None}
def incr(E, ts, langs, th_s, th_x, win=48):
    cents, last, clang, pred = [], [], [], []
    for i in range(len(E)):
        best, margin = -1, -9
        for c in range(len(cents)):
            if ts[i] - last[c] > win * 3600: continue
            s = float(E[i] @ cents[c]) / np.linalg.norm(cents[c]); th = th_s if clang[c] == langs[i] else th_x
            if s - th > margin: best, margin = c, s - th
        if best >= 0 and margin >= 0:
            cents[best] = cents[best] + E[i]; last[best] = ts[i]; pred.append(best)
        else:
            cents.append(E[i].copy()); last.append(ts[i]); clang.append(langs[i]); pred.append(len(cents) - 1)
    return pred
out = {}
for name, gs in (("all", gold), ("without_huawei", [g for g in gold if lab[g["gid"]] != "huawei_convicted_us_trial"])):
    E, ts, langs, truth = prep(gs); res = {}
    for th_s in (0.55, 0.6):
        for th_x in (0.35, 0.4, 0.45, 0.5, th_s):
            res[f"s{th_s}_x{th_x}"] = metrics(incr(E, ts, langs, th_s, th_x), truth, langs)
    out[name] = res
E, ts, langs, truth = prep(gold); sims = {"same_lang_same_event": [], "cross_lang_same_event": [], "cross_lang_diff_event_top": []}
for i, j in itertools.combinations(range(len(gold)), 2):
    s = float(E[i] @ E[j])
    if truth[i] == truth[j]: sims["same_lang_same_event" if langs[i] == langs[j] else "cross_lang_same_event"].append(s)
    elif langs[i] != langs[j]: sims["cross_lang_diff_event_top"].append(s)
sims["cross_lang_diff_event_top"] = sorted(sims["cross_lang_diff_event_top"])[-200:]
out["cosine_quantiles"] = {k: {q: round(float(np.quantile(v, q)), 3) for q in (0.1, 0.25, 0.5, 0.75, 0.9)} | {"n": len(v)} for k, v in sims.items()}
(H / "results" / "clustering_variants.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(json.dumps(out, indent=1))
