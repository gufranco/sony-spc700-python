## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] `mypy` reports nothing
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `conformance/hardware.test.py` still holds every figure to the manual

## If this changes what the processor does

Both runners, and both outputs pasted:

```bash
python3 conformance/singlestep.py ~/.cache/conformance-suites/spc700/spc700/v1
python3 conformance/cycles.py     ~/.cache/conformance-suites/spc700/spc700/v1
```

A core can pass either one while failing the other. Every store on this part
reads its destination and discards the byte, and the state comparison passed
256,000 cases without that read for as long as it was missing, because the byte
goes nowhere.

## If this changes a number the manual prints

Say which page, and say whether you read it off the rendered page or off the
extracted text. The text layer interleaves the table columns and will hand you a
plausible wrong figure without complaint; every row in `hardware.json` was read
from an image at 200 dots per inch, and the three that disagree with the
recording were read again at 450.

## What it does not carry

- [ ] No firmware, no ROM, and no fragment of either
- [ ] Nothing that says where to obtain them
