from crow_rc1_workbench import Rc1WorkbenchBuilder


def test_rc1_aggregation_does_not_assert_release():
    caps = {name: {"summary": {}} for name in Rc1WorkbenchBuilder.REQUIRED}
    result = Rc1WorkbenchBuilder().build("p", caps)
    assert result["summary"]["complete"] is True
    assert result["metadata"]["release_asserted"] is False
