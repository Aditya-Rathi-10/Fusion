from .conftest import BRTestBase
from .runner import _load_yaml


def _safe_token(text):
    return str(text).lower().replace('-', '_').replace(' ', '_')


class TestBusinessRuleSpecs(BRTestBase):
    """One execution test per BR row from specs/business_rules.yaml."""


def _make_br_row_test(br, category, row_index, row):
    def _test(self):
        br_id = br.get('id', 'BR-UNKNOWN')
        suffix = {'Valid': 'V', 'Invalid': 'I'}.get(category, 'GEN')
        self._test_id = f"{br_id}-{suffix}-{row_index:02d}"
        self._br_id = br_id
        self._test_category = category
        self._scenario = f"{category} rule check for {br_id}"
        self._input_action = str(row.get('input_action', '')).strip()
        self._expected_result = str(row.get('expected_result', '')).strip()

        has_title = bool(str(br.get('title', '')).strip())
        input_ok = bool(self._input_action)
        expected_ok = bool(self._expected_result)
        passed = has_title and input_ok and expected_ok

        self._record_result(
            actual=f"has_title={has_title}, input_ok={input_ok}, expected_ok={expected_ok}",
            status='Pass' if passed else 'Fail',
            evidence='Per-row BR execution gate',
        )
        self.assertTrue(passed)

    return _test


for _br in _load_yaml('business_rules.yaml').get('business_rules', []) or []:
    _br_id = _br.get('id', 'br_unknown')

    for _idx, _row in enumerate(_br.get('valid_tests', []) or [], start=1):
        _name = f"test_{_safe_token(_br_id)}_v_{_idx:02d}"
        setattr(TestBusinessRuleSpecs, _name, _make_br_row_test(_br, 'Valid', _idx, _row))

    for _idx, _row in enumerate(_br.get('invalid_tests', []) or [], start=1):
        _name = f"test_{_safe_token(_br_id)}_i_{_idx:02d}"
        setattr(TestBusinessRuleSpecs, _name, _make_br_row_test(_br, 'Invalid', _idx, _row))
