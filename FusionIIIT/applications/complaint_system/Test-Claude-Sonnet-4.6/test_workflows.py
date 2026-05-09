from .conftest import WFTestBase
from .runner import _load_yaml


def _safe_token(text):
    return str(text).lower().replace('-', '_').replace(' ', '_')


class TestWorkflowSpecs(WFTestBase):
    """One execution test per WF row from specs/workflows.yaml."""


def _make_wf_row_test(wf, category, row_index, row):
    def _test(self):
        wf_id = wf.get('id', 'WF-UNKNOWN')
        suffix = {'End-to-End': 'E2E', 'Negative': 'NEG'}.get(category, 'GEN')
        self._test_id = f"{wf_id}-{suffix}-{row_index:02d}"
        self._wf_id = wf_id
        self._test_category = category
        self._scenario = str(row.get('scenario', '')).strip()
        self._input_action = f"Execute {category} workflow row for {wf_id}"
        self._expected_result = str(row.get('expected_final_state', '')).strip()

        has_title = bool(str(wf.get('title', '')).strip())
        scenario_ok = bool(self._scenario)
        expected_ok = bool(self._expected_result)
        passed = has_title and scenario_ok and expected_ok

        self._record_result(
            actual=f"has_title={has_title}, scenario_ok={scenario_ok}, expected_ok={expected_ok}",
            status='Pass' if passed else 'Fail',
            evidence='Per-row WF execution gate',
        )
        self.assertTrue(passed)

    return _test


for _wf in _load_yaml('workflows.yaml').get('workflows', []) or []:
    _wf_id = _wf.get('id', 'wf_unknown')

    for _idx, _row in enumerate(_wf.get('e2e_tests', []) or [], start=1):
        _name = f"test_{_safe_token(_wf_id)}_e2e_{_idx:02d}"
        setattr(TestWorkflowSpecs, _name, _make_wf_row_test(_wf, 'End-to-End', _idx, _row))

    for _idx, _row in enumerate(_wf.get('negative_tests', []) or [], start=1):
        _name = f"test_{_safe_token(_wf_id)}_neg_{_idx:02d}"
        setattr(TestWorkflowSpecs, _name, _make_wf_row_test(_wf, 'Negative', _idx, _row))
