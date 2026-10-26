# Notes: what was tried, what was dropped, what I got wrong

**Hand-coding the sample myself.** `ROADMAP.md` asks for a hand-coded sample. I did not have one, and the
rules of this repository forbid typed data. Producing labels for the test set in the same session as the
model under test would also have made the reference no more independent than the thing being scored. I used
the public ClimateBERT expert labels instead and say so at the top of the README. The hand-coded version
against real transition-plan PDFs is the next step, not a claim of this module.

**Extracting targets, not just yes/no.** I wanted target, year and scope. No public set labels them, so the
score would have had no reference. Dropped; the README says the label is binary.

**Running the model through a framework.** No SDK is allowed in the dependency list, and an API key was not
available in this environment. I call the Claude Code CLI in print mode. The first call cost USD 0.033
because it loaded my global instructions, hooks and 37,000 tokens of context into every paragraph, which would
also have contaminated the prompt. Switching off tools, settings sources, skills and persistence and
supplying my own system prompt took it to USD 0.002 and a clean prompt. The cost of the full run was USD 7.07.

**Parser bug that changed prompt B's result.** My first parser accepted only "yes" and "no". Prompt B asks for
"a commitment or an action", and in 33 of 320 replies the model answered "Action" or "Commitment". They were
counted as no, which made B look like the worst prompt (recall 63.3%, F1 56.4%). Reading the unparsable
replies showed the cause; with them read as yes, B has recall 83.7% and F1 65.1%. A test now pins this
(`test_parse_reply_variants`). The stored replies do not carry a parsed label for that reason: `evaluate.py`
parses them every time, so a parser fix cannot leave the file stale. Lesson: look at the unparsable count
before reading a comparison between prompts.

**A second, accidental background run.** The first extraction call was started without a timeout, ran past
the shell limit and was moved to the background. I waited for it to finish and resumed from the cache; the
extraction is resumable by key, so no call was duplicated.

**Few-shot prompting with training paragraphs.** Not run. It would answer a different question (how good is
a prompted model given labels) and would need a held-out split inside the 1,000 to stay honest. The point of
the module is the zero-shot number and how it moves with the prompt.

**Calling the LLM and naive Bayes comparable on F1.** The paired interval for F1 contains zero, so I do not
say the baseline is better. What the interval does support is that the LLM has the lower recall (the paired
interval for recall excludes zero by 0.9 points, so that is a weak statement, and I word it as one).

**Length effect.** I looked for an effect of paragraph length, because the long paragraphs are where I
expected misses. Recall is lowest in the long tercile, but with about 33 positives per tercile the F1
intervals overlap, so nothing is claimed.

**Adjudicating the 19 unanimous disagreements.** I could read them and decide who is right. I did not: a
judgement by the same kind of model, or by me after seeing the model's answer, would be circular. They are
listed by row number for anyone with an independent codebook.
