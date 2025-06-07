import pytest
from unittest.mock import patch, MagicMock

# Assuming tests are run from the project root, and PYTHONPATH is set up (e.g., by pytest)
# such that 'src' is importable.
from src.main import main

@pytest.fixture
def mock_get_pr_details(mocker):
    # Patching where the function is looked up: in the 'src.main' module's namespace.
    return mocker.patch('src.main.get_pr_details')

@pytest.fixture
def mock_analyze_code_changes(mocker):
    return mocker.patch('src.main.analyze_code_changes')

@pytest.fixture
def mock_generate_suggestions(mocker):
    return mocker.patch('src.main.generate_suggestions')

VALID_PR_URL = "https://github.com/test/repo/pull/1"

# Helper to create a minimal valid pr_data dictionary
def create_mock_pr_data(title='Test PR', author='testuser', files_changed_count=1, html_url=VALID_PR_URL):
    files = []
    if files_changed_count > 0:
        files = [{'filename': f'file{i}.py', 'status': 'modified', 'additions':1, 'deletions':1, 'changes':2, 'patch':'...'} for i in range(files_changed_count)]

    return {
        'title': title,
        'author': author,
        'files_changed': files,
        'html_url': html_url,
        # Add other keys that main.py might use for printing or conditions.
        # These were present in the original snippet for pr_parser.py:
        'body': 'Test PR description.',
        'user': {'login': author}, # pr_parser stores user login under 'author' after processing
        'created_at': '2023-01-01T10:00:00Z',
        'updated_at': '2023-01-01T11:00:00Z',
        'state': 'open',
        'commits_url': f"https://api.github.com/repos/test/repo/pulls/1/commits",
        'comments_url': f"https://api.github.com/repos/test/repo/pulls/1/comments",
        'diff': 'mock diff content' # Added, as pr_parser would fetch this
    }

def test_main_successful_flow(
    mock_get_pr_details,
    mock_analyze_code_changes,
    mock_generate_suggestions,
    capsys
):
    """Test the main CLI flow with successful operations."""
    mock_pr_data = create_mock_pr_data(files_changed_count=1)
    mock_analysis_results = {'impact_areas': ['Impact 1'], 'reuse_suggestions':['Reuse 1'], 'solid_violations':['SOLID 1']}
    mock_suggestions = ["Suggestion 1: Test", "Suggestion 2: Secure"]

    mock_get_pr_details.return_value = mock_pr_data
    mock_analyze_code_changes.return_value = mock_analysis_results
    mock_generate_suggestions.return_value = mock_suggestions

    # Patch sys.argv for argparse. Argv[0] is conventionally the script name.
    with patch('sys.argv', ['src/main.py', VALID_PR_URL]):
        main()

    captured = capsys.readouterr()

    mock_get_pr_details.assert_called_once_with(VALID_PR_URL)
    mock_analyze_code_changes.assert_called_once_with(mock_pr_data)
    mock_generate_suggestions.assert_called_once_with(mock_analysis_results)

    assert f"Starting review for PR: {VALID_PR_URL}" in captured.out
    assert f"Successfully fetched details for PR: {mock_pr_data['title']}" in captured.out
    assert f"Author: {mock_pr_data['author']}" in captured.out
    assert f"Files changed: {len(mock_pr_data['files_changed'])}" in captured.out
    assert "Analyzing code changes..." in captured.out
    assert "Code analysis complete." in captured.out # This message is always printed
    assert "Generating suggestions..." in captured.out
    assert "Suggestions generated." in captured.out # This message is always printed
    assert "--- PR Review Suggestions ---" in captured.out
    assert f"PR Title: {mock_pr_data['title']}" in captured.out
    assert f"PR URL: {mock_pr_data['html_url']}" in captured.out
    assert "1. Suggestion 1: Test" in captured.out
    assert "2. Suggestion 2: Secure" in captured.out
    assert "--- End of Review ---" in captured.out

def test_main_pr_fetch_fails(mock_get_pr_details, mock_analyze_code_changes, mock_generate_suggestions, capsys):
    mock_get_pr_details.return_value = None # Simulate failure to fetch PR details

    with patch('sys.argv', ['src/main.py', VALID_PR_URL]):
        main()

    captured = capsys.readouterr()
    mock_get_pr_details.assert_called_once_with(VALID_PR_URL)
    assert "Failed to fetch PR details. Exiting." in captured.out
    mock_analyze_code_changes.assert_not_called()
    mock_generate_suggestions.assert_not_called()

def test_main_analysis_returns_empty_structure(mock_get_pr_details, mock_analyze_code_changes, mock_generate_suggestions, capsys):
    """ Test when analysis returns an empty structure but not None.
        The main.py code has a check `if not analysis_results:`, which would be false for an empty dict.
        The current main.py does not explicitly check for empty analysis results to exit.
        It prints "Code analysis complete." and proceeds.
    """
    mock_pr_data = create_mock_pr_data()
    # Simulate analysis returning an "empty" but valid structure
    mock_empty_analysis_results = {'impact_areas': [], 'reuse_suggestions':[], 'solid_violations':[]}
    mock_suggestions_from_empty_analysis = ["No specific suggestions based on the current analysis. General best practices still apply."]


    mock_get_pr_details.return_value = mock_pr_data
    mock_analyze_code_changes.return_value = mock_empty_analysis_results
    mock_generate_suggestions.return_value = mock_suggestions_from_empty_analysis


    with patch('sys.argv', ['src/main.py', VALID_PR_URL]):
        main()

    captured = capsys.readouterr()
    mock_get_pr_details.assert_called_once_with(VALID_PR_URL)
    mock_analyze_code_changes.assert_called_once_with(mock_pr_data)
    mock_generate_suggestions.assert_called_once_with(mock_empty_analysis_results)

    # Check that the flow continues even with "empty" analysis
    assert "Code analysis complete." in captured.out
    assert "Suggestions generated." in captured.out
    assert mock_suggestions_from_empty_analysis[0] in captured.out


def test_main_suggestion_generation_returns_empty_list(
    mock_get_pr_details,
    mock_analyze_code_changes,
    mock_generate_suggestions,
    capsys
):
    """ Test when suggestion generation returns an empty list.
        main.py has: `if not suggestions: print("No suggestions were generated. Exiting.")`
        However, the `generate_suggestions` function itself is designed to return a default message
        if its internal list is empty. So, for it to return truly [] would be unusual unless it errored.
        The test in main.py for `if not suggestions:` might be for a case where generate_suggestions
        itself returns None or an empty list due to an internal unhandled issue.
        Let's assume generate_suggestions could return [] if it internally fails before adding default.
    """
    mock_pr_data = create_mock_pr_data()
    mock_analysis_results = {'impact_areas': ['Impact 1'], 'reuse_suggestions':[], 'solid_violations':[]}

    mock_get_pr_details.return_value = mock_pr_data
    mock_analyze_code_changes.return_value = mock_analysis_results
    mock_generate_suggestions.return_value = [] # Simulate generate_suggestions returning an empty list

    with patch('sys.argv', ['src/main.py', VALID_PR_URL]):
        main()

    captured = capsys.readouterr()
    mock_generate_suggestions.assert_called_once_with(mock_analysis_results)

    # Based on main.py: `if not suggestions:` (after calling generate_suggestions)
    # it prints `No suggestions were generated.` and then `No suggestions available to display.`
    # It does *not* print "Exiting" and then stop the whole "--- PR Review Suggestions ---" block.
    # It will proceed to print the suggestions header, and then "No suggestions available to display."
    assert "No suggestions were generated, or suggestion generation failed." in captured.out # This is from main.py
    assert "--- PR Review Suggestions ---" in captured.out
    assert "No suggestions available to display." in captured.out


def test_main_no_pr_url_argument(capsys):
    # Patch sys.argv to simulate calling the script without the pr_url argument.
    # Argv[0] is script name.
    with patch('sys.argv', ['src/main.py']):
        with pytest.raises(SystemExit) as e:
             main() # This will call parser.parse_args() which will exit.

    assert e.type == SystemExit
    # Argparse exits with code 2 for argument errors.
    assert e.value.code == 2

    captured = capsys.readouterr()
    # Argparse prints usage to stderr for errors.
    assert "usage: main.py" in captured.err # main.py is what argparse sees due to sys.argv[0]
    assert "the following arguments are required: pr_url" in captured.err

# The placeholder test_example_main is automatically removed by overwriting the file.
