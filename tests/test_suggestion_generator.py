import pytest
from src.suggestion_generator import generate_suggestions

# The placeholder test_example_suggestion_generator is automatically removed by overwriting the file.

def test_generate_suggestions_input_none(capsys):
    """Test with None as analysis_results."""
    result_none = generate_suggestions(None)
    assert result_none == [] # Expected to return an empty list on None input
    captured_none = capsys.readouterr()
    assert "Error: No analysis results provided for suggestion generation." in captured_none.out

def test_generate_suggestions_empty_dict_input():
    """Test with an empty dictionary as analysis_results."""
    result_empty_dict = generate_suggestions({})
    # For an empty dict:
    # - .get('impact_areas', []) is [] -> no impact-specific suggestions.
    # - .get('reuse_suggestions', []) is [] -> no reuse suggestions.
    # - .get('solid_violations', []) is [] -> no SOLID suggestions.
    # - Since analysis_results.get('impact_areas') (which is None, then defaults to []) is empty,
    #   the security and testing reminders are NOT added.
    # - The suggestions list remains empty, so the default "No specific suggestions..." message is added.
    assert result_empty_dict == ["No specific suggestions based on the current analysis. General best practices still apply."]

def test_generate_suggestions_no_findings():
    """Test when analysis results have keys but all corresponding lists are empty."""
    analysis_results = {
        'impact_areas': [],
        'reuse_suggestions': [],
        'solid_violations': []
    }
    result = generate_suggestions(analysis_results)
    # Similar to empty dict: no specific findings, no impact-driven reminders.
    assert result == ["No specific suggestions based on the current analysis. General best practices still apply."]

def test_generate_suggestions_with_impact_areas_only():
    """Test with only impact areas found."""
    analysis_results = {
        'impact_areas': ['File modified: main.py'],
        'reuse_suggestions': [],
        'solid_violations': []
    }
    result = generate_suggestions(analysis_results)

    assert "Impact Noted: File modified: main.py. Consider adding specific unit tests for the affected logic." in result
    # Impact areas are present, so security and testing reminders should be added.
    assert "Security Reminder: Review changes for potential security vulnerabilities (e.g., input validation, proper authentication/authorization, SQL injection, XSS)." in result
    assert "Testing Reminder: Ensure comprehensive unit tests cover the new changes and edge cases." in result
    assert len(result) == 3 # 1 impact + 2 reminders

def test_generate_suggestions_with_reuse_suggestions_only():
    """Test with only reuse suggestions found."""
    analysis_results = {
        'impact_areas': [], # No impact areas
        'reuse_suggestions': ['Abstract common logic in utils.py'],
        'solid_violations': []
    }
    result = generate_suggestions(analysis_results)

    assert "Code Reuse: Abstract common logic in utils.py" in result
    # No impact areas, so security/testing reminders are NOT added.
    # The suggestions list is not empty, so the default "No specific suggestions..." is NOT added.
    assert len(result) == 1

def test_generate_suggestions_with_solid_violations_only():
    """Test with only SOLID violations found."""
    analysis_results = {
        'impact_areas': [], # No impact areas
        'reuse_suggestions': [],
        'solid_violations': ['Class MyClass violates SRP.']
    }
    result = generate_suggestions(analysis_results)

    assert "Design Pattern: Class MyClass violates SRP." in result
    # No impact areas, so security/testing reminders are NOT added.
    assert len(result) == 1

def test_generate_suggestions_all_types_of_findings():
    """Test with a mix of all types of findings."""
    analysis_results = {
        'impact_areas': ['Critical function updated: process_payment()'],
        'reuse_suggestions': ['Consider refactoring duplicated code in module_a and module_b.'],
        'solid_violations': ['Dependency Inversion Principle might be violated in service_locator.py.']
    }
    result = generate_suggestions(analysis_results)

    assert "Impact Noted: Critical function updated: process_payment(). Consider adding specific unit tests for the affected logic." in result
    assert "Code Reuse: Consider refactoring duplicated code in module_a and module_b." in result
    assert "Design Pattern: Dependency Inversion Principle might be violated in service_locator.py." in result
    # Impact areas are present, so security and testing reminders are added.
    assert "Security Reminder: Review changes for potential security vulnerabilities (e.g., input validation, proper authentication/authorization, SQL injection, XSS)." in result
    assert "Testing Reminder: Ensure comprehensive unit tests cover the new changes and edge cases." in result
    assert len(result) == 5 # 1 impact + 1 reuse + 1 SOLID + 2 reminders

# The test `test_generate_suggestions_default_message_if_only_reminders_would_be_added_but_no_impact`
# was noted as being covered by `test_generate_suggestions_no_findings`.
# The logic is that reminders are only added if 'impact_areas' is non-empty.
# If 'impact_areas' is empty, and other findings are also empty, then the "No specific suggestions..."
# message is indeed the one that gets returned, which is correctly tested by
# `test_generate_suggestions_no_findings` and `test_generate_suggestions_empty_dict_input`.
