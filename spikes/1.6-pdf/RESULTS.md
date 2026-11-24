# Spike 1.6 — PDF parsing (partial: parsing, detection, LLM quality done; vision probe pending)

## Parsing in a subprocess (pypdf)
- 6 PDFs, all < 0.2 s (mostly interpreter start-up). Busy-loop worker killed at the 1.0 s timeout, no zombie left.

## Unreadable detection (text_quality.py)
| file | chars/page | bad chars | readable words | verdict |
|---|---|---|---|---|
| sample_cv | 819 | 0.0% | 97.9% | ok |
| real_cv | 1208 | 0.0% | 98.7% | ok |
| canva_cv | 1365 | 0.0% | 97.5% | ok |
| two_column | 1641 | 0.0% | 97.9% | ok |
| garbled | 694 | 77.1% | 0.0% | unreadable |
| scanned | 0 | 0.0% | 0.0% | scanned |
Thresholds (100 chars/page, 5% bad chars, 60% readable words) have huge margins. Language-agnostic (es/pt/ru/pl checked).
Known blind spot: a shifted alphabet ("Nbsujob") would pass. Not seen in any real PDF; the extraction and the user confirmation at the build_profile stop are the safety nets.

## LLM extraction vs hand labels (gpt-6-luna, effort low, ~1k tokens in / 0.5-1k out per CV)
| source | experiences | fields | bullets in right job | skills | languages | quotes verbatim | leaked DOB/DNI |
|---|---|---|---|---|---|---|---|
| sample, pypdf | 4/4 | 4/4 | 12/12 | 21/21 | 3/3 | 14/14 | no |
| two column, pypdf | 4/4 | 4/4 | 12/12 | 21/21 | 3/3 | 14/14 | no |
| **canva, pypdf** | 3/3 | 3/3 | **4/9** | 14/14 | 3/3 | 11/11 | no |
| canva, pdfminer | 3/3 | 3/3 | **9/9** | 14/14 | 3/3 | 11/11 | no |
| real (es), pypdf | 3/3 | 3/3 | 2/2 | 11/11 | 1/1 | 4/4 | n/a (redacted) |
| real (es), pdfminer | 3/3 | 3/3 | 2/2 | 11/11 | 1/1 | 3/3 | n/a (redacted) |

## Findings
1. **pypdf reading order breaks evidence silently on design-tool CVs.** Canva + pypdf: Pampa's bullets landed under Nimbus and Freelance's under Pampa; no error, profile looks complete. pdfminer.six (MIT) fixes it (9/9). Plan B is needed.
2. Vision fallback not needed by the Plan C criterion: after Plan B, 0 of 4 text-based CVs fail (< 2). Scanned PDFs still return CV_SCANNED.
3. Real CV (details kept local): dates sit on a separate line from each job; both engines paired them correctly, and a non-tech course in the education section was not taken as a job.
4. **Language levels are the weak point of real CVs.** Real wording says an exam was *taken* (not passed) or that a *course* for a certificate was attended; the LLM listed both as certificates, one entry each. A certificate-to-CEFR table would overclaim. Levels from certificates must be confirmed by the user (already in the build_profile stop), and entries must be deduplicated per language.
5. pypdf glues two-column personal data into one line; line-based redaction removed a wanted line once. Redaction by line is fragile.
6. Scorer bug found and fixed during the run (newlines inside quotes): comparisons ignore whitespace and case.

## Go / no-go (written before running)
- text < 5 s: GO (pypdf). Not yet timed for pdfminer in the subprocess.
- timeout kills the process: GO.
- scanned and garbled detected: GO.
- >= 90% experiences/skills vs manual count on text-based CVs: GO with pdfminer; pypdf alone fails on Canva (bullets 44%).
- language levels correct: PARTIAL, see finding 4.

## pdfminer.six in the subprocess (same worker, `--engine pdfminer`)
- Same set, same verdicts as pypdf; 0.15-0.18 s per file; busy-loop worker killed at 1.0 s, no zombie.
- Unmapped glyphs come out as literal "(cid:N)" text, not control chars: bad-char ratio was 0% and only the readable-words check caught garbled.pdf. Now "(cid:N)" counts as bad (garbled: 96.9% bad, 0% words).
- Needs `pdfminer.six` as a project dependency (MIT) if adopted; it is not in pyproject.toml today.

## Open
- Optional vision probe on scanned.pdf (<= 10 min, <= $0.10).
- Decision to record in CLAUDE.md: text engine. Recommendation: pdfminer.six as the main engine (orders text by page position; same speed, same detection). Replaces "pypdf" in the tech stack row and the PDF decision.
