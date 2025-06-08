import pytest
from unittest.mock import patch, MagicMock, call

from src.main import main
from src.code_analyzer import DEFAULT_ANALYSES_TO_RUN, ALL_ANALYSES, ANALYSIS_FLAKE8, ANALYSIS_PYTHON_AST # Import constants

@pytest.fixture
def mock_process_single_pr(mocker):
    return mocker.patch('src.main.process_single_pr')

VALID_PR_URL_1 = "https://github.com/test/repo/pull/1"
VALID_PR_URL_2 = "https://github.com/test/repo/pull/2"
VALID_PR_URL_3 = "https://github.com/test/repo/pull/3"

SUCCESS_RESULT_1 = (VALID_PR_URL_1, "PR Title 1", VALID_PR_URL_1, ["Suggestion A for PR1", "Suggestion B for PR1"], None)
SUCCESS_RESULT_2 = (VALID_PR_URL_2, "PR Title 2", VALID_PR_URL_2, ["Suggestion C for PR2"], None)
FAILURE_RESULT_3 = (VALID_PR_URL_3, None, None, None, "Simulated processing error for PR3")

def test_main_multiple_prs_all_success(mock_process_single_pr, capsys):
    def side_effect_func(pr_url, analyses_to_run): # Add analyses_to_run
        if pr_url == VALID_PR_URL_1: return SUCCESS_RESULT_1
        elif pr_url == VALID_PR_URL_2: return SUCCESS_RESULT_2
        return (pr_url, "Unknown Title", pr_url, [], f"Mock error: Unexpected URL {pr_url}")
    mock_process_single_pr.side_effect = side_effect_func

    test_urls = [VALID_PR_URL_1, VALID_PR_URL_2]
    with patch('sys.argv', ['src/main.py'] + test_urls): # Default analyses
        main()
    captured = capsys.readouterr()

    # Check calls with default analyses
    expected_calls = [
        call(VALID_PR_URL_1, DEFAULT_ANALYSES_TO_RUN),
        call(VALID_PR_URL_2, DEFAULT_ANALYSES_TO_RUN)
    ]
    mock_process_single_pr.assert_has_calls(expected_calls, any_order=True)
    assert mock_process_single_pr.call_count == len(test_urls)

    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out; assert "Title: PR Title 1" in captured.out
    assert f"Review for PR: {VALID_PR_URL_2}" in captured.out; assert "Title: PR Title 2" in captured.out
    assert "All PRs Processed. Review Summaries:" in captured.out

def test_main_multiple_prs_mixed_results(mock_process_single_pr, capsys):
    def side_effect_func(pr_url, analyses_to_run): # Add analyses_to_run
        if pr_url == VALID_PR_URL_1: return SUCCESS_RESULT_1
        elif pr_url == VALID_PR_URL_3: return FAILURE_RESULT_3
        return (pr_url, "Unknown Title", pr_url, [], f"Mock error: Unexpected URL {pr_url}")
    mock_process_single_pr.side_effect = side_effect_func

    test_urls = [VALID_PR_URL_1, VALID_PR_URL_3]
    with patch('sys.argv', ['src/main.py', '--analyses', 'all'] + test_urls): # Test with 'all'
        main()
    captured = capsys.readouterr()
    expected_calls = [
        call(VALID_PR_URL_1, ALL_ANALYSES),
        call(VALID_PR_URL_3, ALL_ANALYSES)
    ]
    mock_process_single_pr.assert_has_calls(expected_calls, any_order=True)
    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out; assert "Status: COMPLETED" in captured.out
    assert f"Review for PR: {VALID_PR_URL_3}" in captured.out; assert "Status: FAILED" in captured.out

def test_main_single_pr_url_still_works(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = SUCCESS_RESULT_1
    with patch('sys.argv', ['src/main.py', VALID_PR_URL_1]):
        main()
    captured = capsys.readouterr()
    mock_process_single_pr.assert_called_once_with(VALID_PR_URL_1, DEFAULT_ANALYSES_TO_RUN)
    assert f"Review for PR: {VALID_PR_URL_1}" in captured.out

def test_main_no_pr_url_argument_still_causes_argparse_exit(capsys):
    with patch('sys.argv', ['src/main.py']):
        with pytest.raises(SystemExit) as e: main()
    assert e.value.code == 2
    captured = capsys.readouterr()
    assert "usage: main.py" in captured.err
    assert "the following arguments are required: pr_urls" in captured.err

# --- Tests for --analyses CLI argument parsing ---
def test_main_analyses_cli_arg_default(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title", VALID_PR_URL_1, ["Some suggestion"], None)
    with patch('sys.argv', ['main.py', VALID_PR_URL_1]): # No --analyses means default
        main()
    args, _ = mock_process_single_pr.call_args
    assert args[0] == VALID_PR_URL_1
    assert sorted(args[1]) == sorted(DEFAULT_ANALYSES_TO_RUN)

def test_main_analyses_cli_arg_default_explicit(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title", VALID_PR_URL_1, ["Some suggestion"], None)
    with patch('sys.argv', ['main.py', '--analyses', 'default', VALID_PR_URL_1]):
        main()
    args, _ = mock_process_single_pr.call_args
    assert args[0] == VALID_PR_URL_1
    assert sorted(args[1]) == sorted(DEFAULT_ANALYSES_TO_RUN)

def test_main_analyses_cli_arg_specific(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title",VALID_PR_URL_1, ["Some suggestion"], None)
    specific_analyses = [ANALYSIS_FLAKE8, ANALYSIS_PYTHON_AST]
    with patch('sys.argv', ['main.py', '--analyses', f'{ANALYSIS_FLAKE8},{ANALYSIS_PYTHON_AST}', VALID_PR_URL_1]):
        main()
    args, _ = mock_process_single_pr.call_args
    assert sorted(args[1]) == sorted(specific_analyses)

def test_main_analyses_cli_arg_all(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title",VALID_PR_URL_1, ["Some suggestion"], None)
    with patch('sys.argv', ['main.py', '--analyses', 'all', VALID_PR_URL_1]):
        main()
    args, _ = mock_process_single_pr.call_args
    assert sorted(args[1]) == sorted(ALL_ANALYSES)

def test_main_analyses_cli_arg_none(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title",VALID_PR_URL_1, ["Some suggestion"], None)
    with patch('sys.argv', ['main.py', '--analyses', 'none', VALID_PR_URL_1]):
        main()
    args, _ = mock_process_single_pr.call_args
    assert args[1] == []

def test_main_analyses_cli_arg_invalid_ignored(mock_process_single_pr, capsys):
    mock_process_single_pr.return_value = (VALID_PR_URL_1, "Title", VALID_PR_URL_1, ["Some suggestion"], None)
    with patch('sys.argv', ['main.py', '--analyses', 'flake8,invalid_analysis,python_ast', VALID_PR_URL_1]):
        main()
    args, _ = mock_process_single_pr.call_args
    assert sorted(args[1]) == sorted([ANALYSIS_FLAKE8, ANALYSIS_PYTHON_AST])
    captured = capsys.readouterr()
    assert "Warning: Unknown analysis type(s) 'invalid_analysis' ignored" in captured.out
