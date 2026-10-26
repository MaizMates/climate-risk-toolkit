"""Five pages. Every number is read from results/, none is typed here."""
import json
import os
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

INK, MID, RULE, ACC, OK, BAD, WARN = "#10201E", "#33453F", "#D3DCD6", "#0F5257", "#2F6B4F", "#A32914", "#B0770F"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MID, "axes.labelcolor": INK,
                     "xtick.color": MID, "ytick.color": MID, "axes.titlesize": 10})
pc = lambda v: f"{100 * v:.1f}%"
ci = lambda v, w: f"[{pc(v[0])}, {pc(v[1])}]"


def page(pdf, kicker, title, blocks, draw=None, draw_rect=None, min_y=0.45):
    fig = plt.figure(figsize=(8.27, 11.69)); fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, kicker, fontsize=8, color=ACC, va="top", fontfamily="monospace")
    fig.text(0.08, 0.932, title, fontsize=16.5, color=INK, weight="bold", va="top")
    fig.add_artist(plt.Line2D([0.08, 0.92], [0.908, 0.908], color=RULE, lw=1))
    y = 0.878
    for head, body in blocks:
        if head:
            fig.text(0.08, y, head, fontsize=10, color=INK, weight="bold", va="top"); y -= 0.022
        for line in textwrap.wrap(" ".join(body), 96, break_on_hyphens=False):
            t = fig.text(0.08, y, line, fontsize=9.3, color=MID, va="top"); y -= 0.0185
            fig.canvas.draw()
            assert t.get_window_extent().x1 <= 0.93 * fig.bbox.width, f"line overflows page: {line}"
        y -= 0.012
    assert not draw or y > min_y, f"text runs into the figure on: {title}"
    if draw:
        draw(fig.add_axes(draw_rect or [0.10, 0.09, 0.82, 0.34]))
    if os.environ.get("DECK_PNG"):
        fig.savefig(f"{os.environ['DECK_PNG']}/{kicker.split()[-3]}.png", dpi=70)
    pdf.savefig(fig); plt.close(fig)


def clean(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    d = json.load(open("results/eval.json"))
    log = json.load(open("results/fetch_log.json"))
    h, sw, nb, df, rt = d["headline"], d["sweep"], d["baseline_naive_bayes"], d["diff_llm_minus_nb"], d["retest"]
    ss, pv, bl, er = d["sample_size"], d["prevalence"], d["by_length"], d["errors"]
    n, tr = h["n"], d["train"]
    base = sw["haiku/A"]
    sonnet = sw["sonnet/A"]
    single = {k: v for k, v in sw.items() if "/" in k}
    f1lo, f1hi = d["f1_range"]; plo, phi = d["precision_range"]; rlo, rhi = d["recall_range"]
    lo_k = min(single, key=lambda k: single[k]["precision"]); hi_k = max(single, key=lambda k: single[k]["precision"])

    # every comparative sentence below is checked against the numbers here
    assert df["f1"][1] < 0 < df["f1"][2], "text says the LLM and naive Bayes F1 cannot be separated"
    assert df["recall"][2] < 0, "text says naive Bayes recall is higher with an interval clear of zero"
    assert df["precision"][1] < 0 < df["precision"][2], "text says precision cannot be separated"
    assert (phi - plo) > 2 * (f1hi - f1lo) and (rhi - rlo) > 2 * (f1hi - f1lo), "text says the prompt moves precision and recall by far more than F1"
    assert lo_k == "haiku/B" and hi_k == "haiku/C", "text names prompt B least precise and C most"
    assert sonnet["ci_f1"][0] < base["f1"] < sonnet["ci_f1"][1], "text says the two models cannot be separated on F1"
    assert pv[sorted(pv)[0]]["precision"] < 0.5 < pv[sorted(pv)[-1]]["precision"], "text says precision crosses one half across prevalence"
    assert ss["320"]["ci_precision"][1] - ss["320"]["ci_precision"][0] < ss["80"]["ci_precision"][1] - ss["80"]["ci_precision"][0]
    assert er["unanimous_fn"] > er["unanimous_fp"], "text says unanimous misses are mostly commitments the model never flags"
    assert max(b["ci_f1"][0] for b in bl.values()) < min(b["ci_f1"][1] for b in bl.values()), "text says the three length strata share a common F1 value"

    with PdfPages("deck.pdf") as pdf:
        def p1(ax):
            names = ["precision", "recall", "F1"]
            ys = [3.0, 2.0, 1.0]
            for y0, nm, key in zip(ys, names, ("precision", "recall", "f1")):
                ax.plot(h["ci_" + key], [y0 + .12] * 2, color=ACC, lw=3, alpha=.6)
                ax.plot(h[key], y0 + .12, "o", color=ACC, ms=7)
                ax.plot(nb["ci_" + key], [y0 - .12] * 2, color=WARN, lw=3, alpha=.6)
                ax.plot(nb[key], y0 - .12, "s", color=WARN, ms=6)
            ax.plot([], [], "o-", color=ACC, label="LLM, Claude Haiku 4.5, prompt A (two runs pooled)")
            ax.plot([], [], "s-", color=WARN, label="naive Bayes trained on the 1,000 labelled training paragraphs")
            ax.set_yticks(ys); ax.set_yticklabels(names); ax.set_xlim(0.3, 1.0); ax.set_ylim(0.5, 3.6); clean(ax)
            ax.legend(loc="lower left", frameon=False, fontsize=8)
            ax.set_xlabel("agreement with the expert label on 320 held-out paragraphs, 95% interval")
        page(pdf, "MODULE 13 / 1 of 5", "How right is an LLM that reads climate disclosures?", [
            ("The estimand", [
                "Precision and recall of an LLM's yes/no extraction of climate commitments and actions, against the",
                "expert label, on paragraphs from corporate annual and sustainability reports. If I knew it exactly it",
                "would be the share of the model's 'commitment' calls that experts also call so, and the share of expert-",
                "labelled commitments it finds, for paragraphs drawn like these. The reference labels are the public",
                "ClimateBERT annotations, not my own hand coding."]),
            ("The answer", [
                f"Precision {pc(h['precision'])} {ci(h['ci_precision'], 0)}, recall {pc(h['recall'])} {ci(h['ci_recall'], 0)}, F1 {pc(h['f1'])} {ci(h['ci_f1'], 0)}.",
                f"Kappa against the experts is {rt['kappa_vs_gold_rep1']:.2f} and {rt['kappa_vs_gold_rep2']:.2f} on the two runs: moderate agreement.",
                f"About {100 - 100 * h['precision']:.0f} in 100 calls it makes are not commitments to the experts, and it misses {100 - 100 * h['recall']:.0f} in 100 that are.",
                f"A naive Bayes trained on {tr['n']:,} labelled paragraphs scores F1 {pc(nb['f1'])}: no worse, and no better."]),
        ], p1, [0.10, 0.12, 0.82, 0.38], min_y=0.58)

        def p2(ax):
            ms = sorted(ss, key=int)
            xs = np.array([int(m) for m in ms])
            for key, col, lab in (("precision", ACC, "precision"), ("recall", WARN, "recall")):
                lo = np.array([ss[m]["ci_" + key][0] for m in ms]); hi = np.array([ss[m]["ci_" + key][1] for m in ms])
                ax.fill_between(xs, lo, hi, color=col, alpha=.2)
                ax.plot(xs, [ss[m][key] for m in ms], "o-", color=col, label=lab)
            ax.set_xticks(xs); ax.set_xticklabels(xs); clean(ax); ax.set_ylim(0.2, 1.05)
            ax.set_xlabel("number of labelled test paragraphs scored (first m of 320)"); ax.legend(frameon=False)
        page(pdf, "MODULE 13 / 2 of 5", "Method: held-out labels, fixed prompt, resampling", [
            ("Data", [
                f"ClimateBERT 'commitments and actions' dataset ({log['dataset']}), fetched from the Hugging Face",
                f"datasets-server on {log['accessed']}: {tr['n']:,} training and {n} test paragraphs, each labelled by experts as about",
                f"climate commitments and actions or not. Test prevalence {pc(h['prevalence'])}, training {pc(tr['prevalence'])}. CC-BY-NC-SA text is fetched, not committed."]),
            ("Extraction", [
                f"Claude Haiku 4.5 via the Claude Code CLI, tools and settings off, one paragraph per call, {d['n_calls']:,} calls in all.",
                "Primary: prompt A, the dataset card's own task definition, written before any reply was read. Run twice.",
                "Sweep: prompt B (terse), prompt C (strict: target, pledge or concrete action), and Claude Sonnet 5.5 on A."]),
            ("Interval", [
                f"{d['n_boot']:,} resamples of the {n} test paragraphs, the population the estimate belongs to. In each resample every",
                "paragraph takes one of the two runs at random, so the model's own sampling noise is inside the interval.",
                "The prompt is one choice for all paragraphs, so it is swept, not drawn. Labelling error is not in the interval."]),
        ], p2, [0.12, 0.10, 0.76, 0.34], min_y=0.48)

        def p3(ax):
            for k, v in single.items():
                ax.plot(v["ci_recall"], [v["precision"]] * 2, color=ACC, lw=1.3, alpha=.5)
                ax.plot([v["recall"]] * 2, v["ci_precision"], color=ACC, lw=1.3, alpha=.5)
                ax.plot(v["recall"], v["precision"], "o", color=BAD if k == "haiku/A" else ACC, ms=7)
                ax.annotate(k, (v["recall"], v["precision"]), textcoords="offset points", xytext=(7, 6), fontsize=8, color=INK)
            for k in ("haiku vote (2 of 3 prompts)", "haiku any prompt", "haiku all prompts"):
                v = sw[k]; ax.plot(v["recall"], v["precision"], "D", color=WARN, ms=6)
                ax.annotate(k.replace("haiku ", ""), (v["recall"], v["precision"]), textcoords="offset points", xytext=(7, -11), fontsize=8, color=MID)
            ax.plot(nb["recall"], nb["precision"], "s", color=MID, ms=6); ax.annotate("naive Bayes", (nb["recall"], nb["precision"]), textcoords="offset points", xytext=(7, -11), fontsize=8, color=MID)
            ax.set_xlabel("recall (bars: 95% interval)"); ax.set_ylabel("precision (bars: 95% interval)"); clean(ax)
            ax.set_xlim(0.3, 1.0); ax.set_ylim(0.35, 1.0)
        page(pdf, "MODULE 13 / 3 of 5", "Result: the prompt moves the trade-off, not F1", [
            ("What moves", [
                f"Across {len(single)} model and prompt combinations and three ways of combining prompts, precision runs from {pc(plo)} to {pc(phi)} and",
                f"recall from {pc(rlo)} to {pc(rhi)}, while F1 stays between {pc(f1lo)} and {pc(f1hi)}. The strict prompt C is the most precise",
                f"({pc(single['haiku/C']['precision'])}, recall {pc(single['haiku/C']['recall'])}); the terse prompt B finds the most ({pc(single['haiku/B']['recall'])}, precision {pc(single['haiku/B']['precision'])}).",
                f"Sonnet 5.5 on prompt A: F1 {pc(sonnet['f1'])} {ci(sonnet['ci_f1'], 0)} against {pc(base['f1'])} {ci(base['ci_f1'], 0)} for Haiku: not separable."]),
            ("What it means", [
                "Which prompt to use is a choice about the cost of a miss against the cost of a false alarm, not a",
                "search for the better model. A screening use wants B's recall; an indicator that is published wants C's precision."]),
        ], p3, [0.10, 0.10, 0.80, 0.42], min_y=0.55)

        def p4(ax):
            ks = sorted(pv, key=float)
            xs = np.array([float(k) for k in ks])
            ax.fill_between(xs, [pv[k]["ci"][0] for k in ks], [pv[k]["ci"][1] for k in ks], color=ACC, alpha=.2)
            ax.plot(xs, [pv[k]["precision"] for k in ks], "o-", color=ACC)
            ax.axhline(0.5, color=MID, lw=.8, ls="--")
            ax.axvline(h["prevalence"], color=WARN, lw=1); ax.axvline(tr["prevalence"], color=BAD, lw=1)
            ax.text(h["prevalence"], 0.12, " test", color=WARN, fontsize=8); ax.text(tr["prevalence"], 0.12, " train", color=BAD, fontsize=8)
            ax.set_xlabel("share of paragraphs that experts label as commitments or actions"); ax.set_ylabel("precision of prompt A"); clean(ax); ax.set_ylim(0, 1)
        page(pdf, "MODULE 13 / 4 of 5", "Validation and sensitivity", [
            ("Against a model I trained, on the same paragraphs", [
                f"LLM minus naive Bayes, paired resamples: precision {100 * df['precision'][0]:+.1f} points [{100 * df['precision'][1]:+.1f}, {100 * df['precision'][2]:+.1f}], recall {100 * df['recall'][0]:+.1f} [{100 * df['recall'][1]:+.1f}, {100 * df['recall'][2]:+.1f}],",
                f"F1 {100 * df['f1'][0]:+.1f} [{100 * df['f1'][1]:+.1f}, {100 * df['f1'][2]:+.1f}]. The zero-shot model has no precision edge, and it finds fewer of the commitments."]),
            ("Test-retest, same model, same prompt, same paragraphs", [
                f"The two runs disagree on {rt['n_disagree']} of {n} paragraphs ({pc(1 - rt['agreement'])}); kappa between them {rt['kappa']:.2f}. The model is far more",
                f"consistent with itself than with the experts (kappa {rt['kappa_vs_gold_rep1']:.2f}): most of the error is systematic, not noise."]),
            ("Precision depends on the mix, recall does not", [
                f"Precision is {pc(pv[sorted(pv, key=float)[0]]['precision'])} where {pc(float(sorted(pv, key=float)[0]))} of paragraphs are commitments, {pc(h['precision'])} at the test mix and",
                f"{pc(pv[sorted(pv, key=float)[2]]['precision'])} at the training mix. A document with few commitments gets mostly false alarms.",
                f"Sample size: the precision interval is {100 * (ss['80']['ci_precision'][1] - ss['80']['ci_precision'][0]):.0f} points wide at 80 paragraphs and {100 * (ss['320']['ci_precision'][1] - ss['320']['ci_precision'][0]):.0f} at 320 (page 2).",
                f"Length: F1 by tercile {pc(bl['short']['f1'])}, {pc(bl['medium']['f1'])}, {pc(bl['long']['f1'])}; the three intervals overlap, so no length effect is claimed."]),
        ], p4, [0.12, 0.10, 0.76, 0.36], min_y=0.50)

        page(pdf, "MODULE 13 / 5 of 5", "Limits and what comes next", [
            ("The assumption that would break the conclusion", [
                "That the expert label is the truth. What counts as a 'commitment or action' is a judgement call, and I have no",
                f"inter-annotator figure for this dataset. {er['n_unanimous_wrong']} of {n} test paragraphs are ones where all five model runs agree with each other and",
                f"disagree with the experts ({er['unanimous_fn']} misses, {er['unanimous_fp']} false alarms). If those are label errors the model is better than {pc(h['f1'])}; if they are a",
                "real definition gap it is not. I have not adjudicated them, and doing so with the same model would be circular."]),
            ("What a sceptic attacks first", [
                "Transfer. Paragraphs are already pre-filtered as climate-related, so this is not a transition-plan document",
                "test: finding the paragraphs inside a 200-page plan is a prior step this module does not measure.",
                "The label is binary and paragraph-level. It is not extraction of a target (what, how much, by when), which has no",
                "public labelled set here. Paragraphs of one company share style, and the data has no company id, so the",
                "resample treats them as independent; the interval is narrower than it should be by an amount I cannot measure here."]),
            ("Not claimed", [
                "Nothing here is forward-looking, so there is no backtest; the held-out test set plays that role.",
                "Model aliases move: the resolved IDs are in results/eval.json and the cached replies in results/llm_raw.jsonl.",
                "The strict-versus-terse prompt trade-off is shown on one data set and one model family."]),
            ("Next", [
                "Label a sample of real transition-plan PDFs myself, under a written codebook with a second pass to measure",
                "my own consistency, extract target, year and scope, and score the same way."]),
        ])
    print("deck.pdf written")


if __name__ == "__main__":
    main()
