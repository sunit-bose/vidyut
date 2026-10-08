from src.main import determine_build_status

def test_no_findings_passes():
    results = [("url1", "Title", "url1", [{"type": "info", "message": "nothing"}], None)]
    should_fail, reasons = determine_build_status(results, ["security_concern"])
    assert should_fail is False
    assert reasons == []

def test_security_concern_fails_by_default():
    results = [("url1", "Title", "url1", [{"type": "security_concern", "message": "hardcoded secret", "file_path": "a.py"}], None)]
    should_fail, reasons = determine_build_status(results, ["security_concern"])
    assert should_fail is True
    assert any("security_concern" in r for r in reasons)

def test_critical_processing_error_always_fails():
    results = [("url1", None, None, None, "Failed to fetch PR details.")]
    should_fail, reasons = determine_build_status(results, [])
    assert should_fail is True
    assert any("critical processing error" in r for r in reasons)

def test_ai_generated_code_never_fails_even_if_requested():
    results = [("url1", "Title", "url1", [{"type": "ai_generated_code", "confidence": 0.95, "message": "Found reference to Claude."}], None)]
    # Caller mistakenly asks to fail on ai_generated_code; policy must ignore it.
    should_fail, reasons = determine_build_status(results, ["ai_generated_code", "security_concern"])
    assert should_fail is False
    assert reasons == []

def test_fail_on_empty_list_never_fails_on_findings():
    results = [("url1", "Title", "url1", [{"type": "security_concern", "message": "x"}], None)]
    should_fail, reasons = determine_build_status(results, [])
    assert should_fail is False

def test_react_issue_fails_when_requested():
    results = [("url1", "Title", "url1", [{"type": "react_issue", "message": "missing key prop", "file_path": "List.jsx"}], None)]
    should_fail, reasons = determine_build_status(results, ["react_issue"])
    assert should_fail is True
