from pathlib import Path
from typing import Literal
from pydantic import BaseModel, model_validator
import yaml

class HiddenTest(BaseModel):
    path: str          # test file, relative to the fixture repo root
    tests: list[str]   # test names that fail on buggy_tag and pass on fixed_tag


class Case(BaseModel):
    id: str
    buggy_tag: str
    fixed_tag: str
    category: Literal["fix", "security", "behaviour"]  # also a pytest marker: `-m security`
    root_path: str  # package dir the tests run in, relative to the fixture repo root
    expected_outcome: Literal["fix", "no_change"] = "fix"  # no_change: the agent must leave the tree alone
    hidden_test: HiddenTest | None = None  # required when expected_outcome is "fix"
    dir: Path # filled in by the loader, not the YAML

    @model_validator(mode="after")
    def _fix_needs_hidden_test(self) -> "Case":
        if self.expected_outcome == "fix" and self.hidden_test is None:
            raise ValueError(f"{self.id}: a fix case needs a hidden_test")
        return self

    @property
    def sentry_payload_path(self) -> Path:
        return self.dir / "sentry.json"
    


CASES_DIR = Path(__file__).parent.parent / "cases"

def load_cases() -> list[Case]:
    cases = []
    for case_dir in sorted(CASES_DIR.iterdir()):
        data = yaml.safe_load((case_dir / "case.yaml").read_text())
        cases.append(Case(**data, dir=case_dir))
    return cases
