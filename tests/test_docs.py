from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

pytestmark = pytest.mark.integration

DOCS = Path(__file__).parent.parent / "docs"


@pytest.mark.parametrize("example", list(find_examples(str(DOCS))), ids=str)
def test_docs_examples(example: CodeExample, eval_example: EvalExample) -> None:
    assert example is not None, "example must not be None"
    assert eval_example is not None, "eval_example fixture must be provided"
    eval_example.set_config(line_length=100)
    if eval_example.update_examples:
        eval_example.format(example)
        eval_example.run(example)
    else:
        eval_example.lint(example)
        eval_example.run(example)
