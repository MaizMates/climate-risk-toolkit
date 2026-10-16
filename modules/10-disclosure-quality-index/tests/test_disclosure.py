"""Checks that fail loudly if the template locator or the index arithmetic breaks.

Fixed inputs, so this tests the logic and not any publisher's uptime.

    python3 tests/test_disclosure.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import disclosure as D
import index as I


def table(n_rows, head=""):
    return head + "\n" + "\n".join("Agriculture 1,234 56 - 7.5% 89" for _ in range(n_rows))


def test_cell_counts_separates_values_from_placeholders():
    assert D.cell_counts("Sector 10 20 - 30 n/a") == (3, 2), "values and placeholders must be counted apart"


def test_prose_numbers_are_not_cells():
    assert D.cell_counts("The bank financed 12 projects in 2024 across 3 regions") == (0, 0), "a sentence is not a table row"


def test_years_are_not_values():
    assert D.cell_counts("2024 2025 100 200")[0] == 2, "column-header years must not inflate the fill rate"


def test_zero_is_a_value_unless_configured():
    assert D.cell_counts("A 0 0 5")[0] == 3
    assert D.cell_counts("A 0 0 5", zero_is_blank=True) == (1, 2), "zero_is_blank must move zeros to placeholders"


def test_letter_spaced_text_is_collapsed():
    assert "alignment metrics" in D.normalise("a l i g n m e n t  m e t r i c s").replace("  ", " ") or \
        "alignmentmetrics" in D.normalise("a l i g n m e n t m e t r i c s")


def test_template_10_is_not_template_1():
    assert D.heading_hits("Template 10 - Other climate change mitigating actions") == {"T10"}, "T10 label read as T1"


def test_prose_sentence_is_not_a_heading():
    assert D.heading_hits("Template 4 shows aggregated exposures towards the top 20 carbon-intensive firms") == set()


def test_contents_entry_is_not_a_heading():
    assert D.heading_hits("Template 6 - Summary of GAR KPIs and climate indicators 178") == set(), "contents lines start false runs"


def test_non_publication_line_is_not_a_heading():
    assert D.heading_hits("Template 9 Mitigating actions - Assets for the calculation of BTAR not applicable") == set()


def test_table_prefix_is_stripped():
    assert D.heading_hits("Table 12.6 - Template 6 - Summary of GAR KPIs") == {"T6"}
    assert D.heading_hits("Table 98. ESG3: Banking book - Climate change transition risk: Alignment metrics") == {"T3"}


def test_run_ends_at_the_next_heading():
    pages = [table(10, "Template 1 - Banking book - climate"), table(10), table(10, "Template 2 - Banking book - climate")]
    loc = D.locate(pages)
    assert loc["T1"] == [0, 1] and loc["T2"] == [2], "a run must stop where another template starts"


def test_run_cap_stops_an_unbounded_run():
    pages = [table(10, "Template 4 - Banking book - climate")] + [table(10)] * 10
    assert len(D.locate(pages)["T4"]) == D.MAX_RUN["T4"], "a one-page template must not swallow the rest of the report"


def test_heading_without_table_is_not_published():
    pages = ["Template 3 - Banking book - climate\nWe do not publish this yet.", "plain prose " * 50]
    assert D.locate(pages)["T3"] == [], "a heading with no cells is not a published template"


def test_omission_is_detected_and_distinguished():
    pages = ["Template 9 - BTAR is not applicable for us"]
    assert D.bank_status(pages)["T9"]["status"] == "omitted_stated"
    assert D.bank_status(["nothing here"])["T9"]["status"] == "not_found"


def test_index_scores_unpublished_as_zero():
    st = {t: {"status": "published", "fill": 1.0} for t in D.TEMPLATES}
    st["T4"] = {"status": "not_found", "fill": 0.0}
    assert abs(I.bank_index(st) - 8 / 9) < 1e-12, "one missing template of nine must cost 1/9"


def test_dropping_stated_omissions_changes_the_denominator_only_for_stated_ones():
    st = {t: {"status": "published", "fill": 1.0} for t in D.TEMPLATES}
    st["T6"] = {"status": "omitted_stated", "fill": 0.0}
    st["T7"] = {"status": "not_found", "fill": 0.0}
    assert abs(I.bank_index(st) - 7 / 9) < 1e-12
    assert abs(I.bank_index(st, omit="drop") - 7 / 8) < 1e-12, "silent absence must still count as zero"


def test_spearman_of_reversed_order_is_minus_one():
    assert abs(I.spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1) < 1e-12


def test_parser_error_on_known_synthetic_tables_is_small():
    import synth
    rows = synth.run(n=25, seed=1)
    err = sum(abs(r["measured"] - r["truth"]) for r in rows) / len(rows)
    assert err < 0.08, f"parser mean absolute error {err:.3f} on SYNTHETIC tables with known fill"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "checks passed")
