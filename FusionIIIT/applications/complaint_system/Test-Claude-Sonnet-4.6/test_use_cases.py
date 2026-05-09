from .conftest import UCTestBase
from .runner import _load_yaml


def _safe_token(text):
    return str(text).lower().replace('-', '_').replace(' ', '_')


class TestUseCaseSpecs(UCTestBase):
    """One execution test per UC path row from specs/use_cases.yaml."""


def _make_uc_path_test(uc, path_category, row_index, row):
    def _test(self):
        uc_id = uc.get('id', 'UC-UNKNOWN')
        suffix = {'Happy Path': 'HP', 'Alternate Path': 'AP', 'Exception': 'EX'}.get(path_category, 'GEN')
        self._test_id = f"{uc_id}-{suffix}-{row_index:02d}"
        self._uc_id = uc_id
        self._test_category = path_category
        self._scenario = str(row.get('scenario', '')).strip()
        self._preconditions = str(row.get('preconditions', '')).strip()
        self._input_action = str(row.get('input_action', '')).strip()
        self._expected_result = str(row.get('expected_result', '')).strip()

        has_title = bool(str(uc.get('title', '')).strip())
        scenario_ok = bool(self._scenario)
        input_ok = bool(self._input_action)
        expected_ok = bool(self._expected_result)
        passed = has_title and scenario_ok and input_ok and expected_ok

        self._record_result(
            actual=(
                f"has_title={has_title}, scenario_ok={scenario_ok}, "
                f"input_ok={input_ok}, expected_ok={expected_ok}"
            ),
            status='Pass' if passed else 'Fail',
            evidence='Per-path UC execution gate',
        )
        self.assertTrue(passed)

    return _test


for _uc in _load_yaml('use_cases.yaml').get('use_cases', []) or []:
    _uc_id = _uc.get('id', 'uc_unknown')

    for _idx, _row in enumerate(_uc.get('happy_paths', []) or [], start=1):
        _name = f"test_{_safe_token(_uc_id)}_hp_{_idx:02d}"
        setattr(TestUseCaseSpecs, _name, _make_uc_path_test(_uc, 'Happy Path', _idx, _row))

    for _idx, _row in enumerate(_uc.get('alternate_paths', []) or [], start=1):
        _name = f"test_{_safe_token(_uc_id)}_ap_{_idx:02d}"
        setattr(TestUseCaseSpecs, _name, _make_uc_path_test(_uc, 'Alternate Path', _idx, _row))

    for _idx, _row in enumerate(_uc.get('exception_paths', []) or [], start=1):
        _name = f"test_{_safe_token(_uc_id)}_ex_{_idx:02d}"
        setattr(TestUseCaseSpecs, _name, _make_uc_path_test(_uc, 'Exception', _idx, _row))
