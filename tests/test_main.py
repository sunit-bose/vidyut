import pytest
from unittest.mock import patch, MagicMock, call

# Assuming tests are run from the project root and PYTHONPATH is set up
# (e.g., by pytest) such that 'src' is importable.
from src.main import main

@pytest.fixture
def mock_process_single_pr(mocker):
    # Patch process_single_pr where it's looked up by main.py (in its own module's namespace)
    return mocker.patch('src.main.process_single_pr')

VALID_PR_URL_1 = "https://github.com/test/repo/pull/1"
VALID_PR_URL_2 = "https://github.com/test/repo/pull/2"
VALID_PR_URL_3 = "https://github.com/test/repo/pull/3"

# Example successful return value from process_single_pr
# (pr_url, pr_title, html_url, suggestions_list, error_message)
SUCCESS_RESULT_1 = (
    VALID_PR_URL_1,
    "PR Title 1",
    VALID_PR_URL_1, # html_url
    ["Suggestion A for PR1", "Suggestion B for PR1"],
    None # No error
)
SUCCESS_RESULT_2 = (
    VALID_PR_URL_2,
    "PR Title 2",
    VALID_PR_URL_2, # html_url
    ["Suggestion C for PR2"],
    None # No error
)
# Example failure return value from process_single_pr
FAILURE_RESULT_3 = (
    VALID_PR_URL_3,
    None, # No title on failure
    None, # No html_url on failure
    None, # No suggestions on failure
    "Simulated processing error for PR3" # Error message
)

def test_main_multiple_prs_all_success(mock_process_single_pr, capsys):
    """Test processing multiple PR URLs where all calls to process_single_pr succeed."""

    # Configure the mock to return different results based on input URL
    def side_effect_func(pr_url):
        if pr_url == VALID_PR_URL_1:
            return SUCCESS_RESULT_1
        elif pr_url == VALID_PR_URL_2:
            return SUCCESS_RESULT_2
        # Fallback for any unexpected URL call during the test
        return (pr_url, "Unknown Title", pr_url, [], f"Mock error: Unexpected URL {pr_url}")

    mock_process_single_pr.side_effect = side_effect_func

    test_urls = [VALID_PR_URL_1, VALID_PR_URL_2]
    # Patch sys.argv to simulate command line arguments. main.py is script name.
    with patch('sys.argv', ['src/main.py'] + test_urls):
        main()

    captured = capsys.readouterr()

    # Check that process_single_pr was called for each URL
    # The order of calls can vary due to ThreadPoolExecutor, so any_order=True
    expected_calls = [call(VALID_PR_URL_1), call(VALID_PR_URL_2)]
    mock_process_single_pr.assert_has_calls(expected_calls, any_order=True)
    assert mock_process_single_pr.call_count == len(test_urls)


    # Check for PR1's output (order in output depends on thread completion)
    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out
    assert "Title: PR Title 1" in captured.out
    assert f"Link: {VALID_PR_URL_1}" in captured.out # Check actual link
    assert "Status: COMPLETED" in captured.out
    assert "1. Suggestion A for PR1" in captured.out
    assert "2. Suggestion B for PR1" in captured.out

    # Check for PR2's output
    assert f"Review for PR: {VALID_PR_URL_2}" in captured.out
    assert "Title: PR Title 2" in captured.out
    assert f"Link: {VALID_PR_URL_2}" in captured.out
    assert "Status: COMPLETED" in captured.out
    assert "1. Suggestion C for PR2" in captured.out

    assert "All PRs Processed. Review Summaries:" in captured.out
    # Note: The "Thread: Starting processing..." messages are printed by the original
    # process_single_pr. Since we've mocked process_single_pr, these prints
    # won't occur from the mock. So, we don't assert them here.


def test_main_multiple_prs_mixed_results(mock_process_single_pr, capsys):
    """Test processing multiple PR URLs with a mix of success and failure."""
    def side_effect_func(pr_url):
        if pr_url == VALID_PR_URL_1:
            return SUCCESS_RESULT_1
        elif pr_url == VALID_PR_URL_3: # This one will "fail" as per FAILURE_RESULT_3
            return FAILURE_RESULT_3
        return (pr_url, "Unknown Title", pr_url, [], f"Mock error: Unexpected URL {pr_url}")

    mock_process_single_pr.side_effect = side_effect_func

    test_urls = [VALID_PR_URL_1, VALID_PR_URL_3]
    with patch('sys.argv', ['src/main.py'] + test_urls):
        main()

    captured = capsys.readouterr()

    expected_calls = [call(VALID_PR_URL_1), call(VALID_PR_URL_3)]
    mock_process_single_pr.assert_has_calls(expected_calls, any_order=True)
    assert mock_process_single_pr.call_count == len(test_urls)

    # Check output for PR1 (Success)
    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out
    assert "Title: PR Title 1" in captured.out
    assert "Status: COMPLETED" in captured.out
    assert "1. Suggestion A for PR1" in captured.out

    # Check output for PR3 (Failure)
    assert f"Review for PR: {VALID_PR_URL_3}" in captured.out
    # For failure, title might not be present in the output if it's None in FAILURE_RESULT_3
    assert "Title: PR Title 3" not in captured.out
    assert "Link: https://github.com/test/repo/pull/3" in captured.out # Link should be the input URL
    assert "Status: FAILED" in captured.out
    assert "Error: Simulated processing error for PR3" in captured.out
    # Ensure suggestions for PR1 are not mixed with PR3's error output incorrectly
    assert "Suggestion A for PR1" in captured.out

def test_main_single_pr_url_still_works(mock_process_single_pr, capsys):
    """Test that providing a single PR URL still works correctly with the new concurrent setup."""
    mock_process_single_pr.return_value = SUCCESS_RESULT_1 # Mock for the single URL

    with patch('sys.argv', ['src/main.py', VALID_PR_URL_1]):
        main()

    captured = capsys.readouterr()
    mock_process_single_pr.assert_called_once_with(VALID_PR_URL_1)
    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out
    assert "Title: PR Title 1" in captured.out
    assert "1. Suggestion A for PR1" in captured.out
    assert f"Starting review for 1 PR(s)" in captured.out # Check count

def test_main_no_pr_url_argument_still_causes_argparse_exit(capsys):
    """Ensure argparse still handles no PR URLs correctly and exits."""
    with patch('sys.argv', ['src/main.py']): # No URL arguments provided
        with pytest.raises(SystemExit) as e:
             main()

    assert e.type == SystemExit
    # Argparse typically exits with code 2 for CLI argument errors
    assert e.value.code == 2

    captured = capsys.readouterr()
    # Argparse prints usage to stderr for errors.
    # The script name in usage message is taken from sys.argv[0]
    assert "usage: main.py" in captured.err # main.py or src/main.py depending on patch
    assert "the following arguments are required: pr_urls" in captured.err # 'pr_urls' is the new arg name

# Previous tests that mocked get_pr_details, analyze_code_changes, generate_suggestions
# individually for main.py are effectively superseded by these tests, as that logic
# is now encapsulated in process_single_pr, which is what we are mocking here.
# If those old tests were testing the internal logic of those functions via main.py,
# that's now better done by testing process_single_pr directly (if it were more complex)
# or by relying on the dedicated unit tests for pr_parser, code_analyzer, etc.
