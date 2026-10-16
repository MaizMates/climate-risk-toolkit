"""Locate the EBA Pillar 3 ESG templates in a bank's report text and score their completeness.

Pure functions on page text; nothing here fetches. A page belongs to template T when T's title (or
its "Template N" / "ESG N" label) sits in the page's heading zone and the page carries table
content. The score of a template is its fill rate: numeric cells over numeric plus placeholder cells.
"""
import re

TEMPLATES = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10"]
MANDATORY = [t for t in TEMPLATES if t != "T9"]  # T9 (BTAR) is reported separately; see README

# full titles; a short line that carries one is a heading even without a "Template N" label
TITLES = {
    "T1": [r"credit quality of exposures by sector", r"qualit[aà] creditizia delle esposizioni per settore"],
    "T2": [r"loans collateri[sz]ed by immovable", r"prestiti garantiti da immobili"],
    "T3": [r"^alignment metrics$", r"alignment metrics\W*(?:table|tab)?\W*$", r"transition risk\W+alignment metrics"],
    "T4": [r"exposures to top 20 carbon", r"top 20 carbon[- ]intensive firms"],
    "T5": [r"exposures subject to physical risk", r"esposizioni soggette a rischio fisico"],
    "T6": [r"summary of key performance indicators", r"summary (?:of )?gar"],
    "T7": [r"assets for the calculation of (?:the )?gar", r"attivi per il calcolo del gar"],
    "T8": [r"^gar ?\(%\)", r"^gar % ?[-:–]", r"\bgar [-–] kpis"],
    "T9": [r"calculation of (?:the )?btar", r"^btar ?(?:%|\()", r"summary table [-–] btar"],
    "T10": [r"other climate change mitigating"],
}
_KEY = re.compile(r"climate|transition|physical|gar\b|taxonomy|alignment|carbon|mitigating|energy|btar|esg|clim|fisico|transizione|banking|portafoglio|sintesi|summary|indicat|azioni|attivi|assets|kpi", re.I)
_LABEL = re.compile(r"^(?:template|tabella|esg|modello)\s?(\d{1,2})(?:\.\d)?(?![\d,])\s*(?:[:.\-–—]|\s)\s*(.*)$", re.I)
_PREFIX = re.compile(r"^(?:table|tabella)\s*[\d.]+\s*[.:–-]\s*(?=(?:template|tabella|esg|modello))", re.I)
_PAREN = re.compile(r"\(template\s?(\d{1,2})(?:\.\d)?\s+reg", re.I)
_OTHER = re.compile(r"^(?:EU\s?)?(?:CR|CCR|LIQ|KM|OV|MR|SEC|IRRBB|OR|REM|CQ|AE|LR|CC|CCA|CCyB|TLAC)\d", re.I)
MAX_RUN = {"T3": 5, "T4": 3, "T6": 3, "T10": 3, "T9": 6}  # pages a heading may claim; default 20
DEFAULT_RUN = 20
_VERB = re.compile(r"^(?:is|are|provides?|shows?|represents?|discloses?|presents?|contains?|has|requires?|aims?|includes?|covers?|allows?)\b", re.I)
OMIT = re.compile(r"not (?:yet )?(?:applicable|published|disclosed|required|available)|postponed|will be (?:published|disclosed)|"
                  r"non (?:applicabile|pubblicat|ancora)|no data|not in scope|exempt|deferred|voluntary|excluded|removed|omitted|no longer|separate annex", re.I)
PLACEHOLDERS = {"-", "–", "—", "n/a", "n.a.", "na", "nd", "n.d.", "n/d", "nm", "n.m."}
MIN_PAGE_CELLS = 5      # a table page carries at least this many numeric or placeholder cells
MIN_TEMPLATE_CELLS = 6   # a template needs this many cells over all its pages to count as published


def normalise(text):
    """Collapse letter-spaced text ('T h i s') and unify dashes and spaces."""
    t = text.replace("\xa0", " ").replace("‑", "-").replace("‐", "-").replace("‑", "-")
    t = re.sub(r"(?<![^\W\d_])((?:[^\W\d_] ){3,}[^\W\d_])(?![^\W\d_])",
               lambda m: m.group(1).replace(" ", ""), t)
    return t


_NUM = re.compile(r"^\(?[-+−]?\d[\d.,']*%?\)?$")
_YEAR = re.compile(r"^(?:19|20)\d\d$")


def is_number(tok, exclude_years=True, zero_is_blank=False):
    if not _NUM.match(tok):
        return False
    core = tok.strip("()%+-−")
    if exclude_years and _YEAR.match(core):
        return False
    if zero_is_blank and re.fullmatch(r"0+(?:[.,]0+)?", core):
        return False
    return True


def is_placeholder(tok, zero_is_blank=False):
    if tok.lower() in PLACEHOLDERS:
        return True
    return zero_is_blank and re.fullmatch(r"0+(?:[.,]0+)?%?", tok) is not None


def cell_counts(text, exclude_years=True, zero_is_blank=False, exclude_row_codes=False, strict=True):
    """(numeric, placeholder) cells in table-like lines of text.

    A table-like line is made only of cell tokens, or has at least two and they are at least half of
    its tokens. A sentence with a few numbers in it is skipped. strict=False drops the "half of its
    tokens" condition; locating tables uses that, because rows with long labels are still table rows.
    """
    text = re.sub(r"(?i)\bnot (?:available|applicable)\b", "n/a", text)
    num = ph = 0
    for line in normalise(text).split("\n"):
        toks = line.split()
        if exclude_row_codes and len(toks) > 1 and re.fullmatch(r"0?\d{1,3}", toks[0]):
            toks = toks[1:]
        kinds = ["p" if is_placeholder(t, zero_is_blank) else "n" if is_number(t, exclude_years, zero_is_blank) else "w"
                 for t in toks]
        cells = [k for k in kinds if k != "w"]
        if cells and (len(cells) == len(toks) or (len(cells) >= 2 and (not strict or 2 * len(cells) >= len(toks)))):
            num += cells.count("n")
            ph += cells.count("p")
    return num, ph


_NOTPUB = re.compile(r"not applicable|not published|not disclosed|postponed|not required|non applicabile", re.I)
_CONTENTS = re.compile(r"\S.{20,}\s\d{1,3}\s*$")  # a contents-list entry ends in a page number


def heading_hits(text, strict=True):
    """Templates headed on this page: label lines ('Template 4 - ...', 'Tabella 4: ...', 'ESG4 - ...') or short title lines."""
    hits = set()
    for line in normalise(text).split("\n"):
        line = line.strip()
        if not line or len(line) > 220:
            continue
        if strict and (_NOTPUB.search(line) or _CONTENTS.match(line)):
            continue
        line = _PREFIX.sub("", line)
        m = _PAREN.search(line)
        if m and 1 <= int(m.group(1)) <= 10:
            hits.add(f"T{int(m.group(1))}")
            continue
        m = _LABEL.match(line)
        if m:  # a labelled line is a heading or prose about the template, never a bare title
            if not _VERB.match(m.group(2)) and (not m.group(2).strip() or _KEY.search(m.group(2))) and 1 <= int(m.group(1)) <= 10:
                hits.add(f"T{int(m.group(1))}")
            continue
        if len(line) > 130:
            continue
        flat = line.lower()
        for t, pats in TITLES.items():
            if line[:1].isupper() and any(re.search(p, flat) for p in pats):
                hits.add(t)
    return hits


def cells_on(text, **kw):
    n, p = cell_counts(text, **{**kw, "strict": False})
    return n + p


def locate(pages, min_page=MIN_PAGE_CELLS, min_tpl=MIN_TEMPLATE_CELLS, run_scale=1.0, **kw):
    """{template: [page indices]}. A heading starts a run; the run takes the heading page when it is a
    table and then every following table page that carries no heading of its own."""
    cells = [cells_on(p, **kw) for p in pages]
    heads = [heading_hits(p) for p in pages]
    toc = [len(heading_hits(p, strict=False)) >= 4 for p in pages]
    other = [any(_OTHER.match(l.strip()) for l in normalise(p).split("\n")) for p in pages]
    found = {t: set() for t in TEMPLATES}
    for i, hs in enumerate(heads):
        if toc[i]:
            continue
        for t in hs:
            j = i
            if cells[i] < min_page:
                j = i + 1
            while (j < len(pages) and j < i + max(1, round(MAX_RUN.get(t, DEFAULT_RUN) * run_scale)) and cells[j] >= min_page
                   and (j == i or not (heads[j] or other[j]))):
                found[t].add(j)
                j += 1
    return {t: sorted(v) if sum(cells[k] for k in v) >= min_tpl else [] for t, v in found.items()}


def _mentions(t):
    n = t[1:]
    return [rf"(?:template|tabella|esg)\s?{n}(?![\d,]|\.\d\d)"] + [p.replace("^", "").replace("$", "") for p in TITLES[t]]


def omission_stated(pages, t):
    """True if some page mentions template t within 400 characters of a non-publication phrase."""
    for p in pages:
        flat = re.sub(r"\s+", " ", normalise(p))
        for pat in _mentions(t):
            for m in re.finditer(pat, flat, re.I):
                if OMIT.search(flat[max(0, m.start() - 400): m.end() + 400]):
                    return True
    return False


def score_template(pages, idx, **kw):
    n = ph = 0
    for i in idx:
        a, b = cell_counts(pages[i], **kw)
        n, ph = n + a, ph + b
    return n, ph


def bank_status(pages, min_page=MIN_PAGE_CELLS, min_tpl=MIN_TEMPLATE_CELLS, run_scale=1.0, **kw):
    """Per template: status, pages, cell counts and fill rate."""
    loc = locate(pages, min_page, min_tpl, run_scale, **kw)
    out = {}
    for t in TEMPLATES:
        idx = loc[t]
        if idx:
            n, ph = score_template(pages, idx, **kw)
            out[t] = {"status": "published", "pages": [i + 1 for i in idx], "numeric": n,
                      "placeholder": ph, "fill": n / (n + ph) if n + ph else 0.0}
        else:
            out[t] = {"status": "omitted_stated" if omission_stated(pages, t) else "not_found",
                      "pages": [], "numeric": 0, "placeholder": 0, "fill": 0.0}
    return out
