import pytest
import requests # Import requests to allow mocking its exceptions
from src.pr_parser import get_pr_details

# Basic valid PR URL for testing regex and structure
VALID_PR_URL = "https://github.com/owner/repo/pull/123"
API_BASE_URL = "https://api.github.com/repos/owner/repo/pulls/123"
DIFF_URL = f"{VALID_PR_URL}.diff"
FILES_API_URL = f"{API_BASE_URL}/files"

@pytest.fixture
def mock_requests_get(mocker):
    # Correctly patch 'requests.get' as it's imported in src.pr_parser
    return mocker.patch('src.pr_parser.requests.get')

def test_get_pr_details_success(mock_requests_get, mocker): # Added mocker fixture for general mocking utilities
    # Mock successful responses for PR details, diff, and files
    mock_pr_response_json = {
        'title': 'Test PR Title',
        'body': 'Test PR description.',
        'user': {'login': 'testuser'},
        'html_url': VALID_PR_URL,
        'created_at': '2023-01-01T10:00:00Z',
        'updated_at': '2023-01-01T11:00:00Z',
        'state': 'open',
        'commits_url': f"{API_BASE_URL}/commits",
        'comments_url': f"{API_BASE_URL}/comments",
    }
    mock_diff_text = "diff --git a/file.py b/file.py\n--- a/file.py\n+++ b/file.py\n@@ -1 +1 @@\n-old\n+new"
    mock_files_response_json = [
        {
            'filename': 'file1.py',
            'status': 'modified',
            'additions': 1,
            'deletions': 1,
            'changes': 2,
            'patch': '@@ -1 +1 @@\n-old\n+new'
        },
        {
            'filename': 'file2.txt',
            'status': 'added',
            'additions': 10,
            'deletions': 0,
            'changes': 10,
            'patch': '...patch for file2.txt...'
        }
    ]

    # This function will be the side_effect for the mocked requests.get
    def side_effect_func(url, headers):
        mock_resp = mocker.Mock(spec=requests.Response) # Use spec for better mocking
        mock_resp.raise_for_status = mocker.Mock()
        mock_resp.status_code = 200 # Default to success

        if url == API_BASE_URL:
            mock_resp.json = mocker.Mock(return_value=mock_pr_response_json)
        elif url == DIFF_URL:
            # For .text attribute, directly set it on the mock object
            # The text attribute is not a function, so don't mock it as one.
            mock_resp.text = mock_diff_text
        elif url == FILES_API_URL:
            mock_resp.json = mocker.Mock(return_value=mock_files_response_json)
        else:
            # If an unexpected URL is called, make raise_for_status actually raise an error
            mock_resp.status_code = 404
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"Unexpected URL: {url}")
        return mock_resp

    mock_requests_get.side_effect = side_effect_func

    result = get_pr_details(VALID_PR_URL)

    assert result is not None
    assert result['title'] == 'Test PR Title'
    assert result['author'] == 'testuser'
    assert result['diff'] == mock_diff_text
    assert len(result['files_changed']) == 2
    assert result['files_changed'][0]['filename'] == 'file1.py'
    assert result['files_changed'][0]['patch'] == '@@ -1 +1 @@\n-old\n+new'

    expected_calls = [
        mocker.call(API_BASE_URL, headers={"Accept": "application/vnd.github.v3+json"}),
        mocker.call(DIFF_URL, headers={"Accept": "application/vnd.github.v3.diff"}),
        mocker.call(FILES_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
    ]
    mock_requests_get.assert_has_calls(expected_calls, any_order=False)


def test_get_pr_details_invalid_url(capsys): # Added capsys to check print output
    result = get_pr_details("invalid-url")
    assert result is None
    captured = capsys.readouterr()
    assert "Invalid GitHub PR URL: invalid-url" in captured.out


def test_get_pr_details_github_api_error(mock_requests_get, capsys, mocker): # Added mocker
    # Simulate an HTTP error (e.g., 404 Not Found) from the GitHub API for the first call
    # Simulate an HTTP error by having requests.get itself raise the exception
    mock_requests_get.side_effect = requests.exceptions.HTTPError("API Error")

    result = get_pr_details(VALID_PR_URL)

    assert result is None
    captured = capsys.readouterr()
    assert f"Error fetching PR data for {VALID_PR_URL}: API Error" in captured.out

def test_get_pr_details_network_error(mock_requests_get, capsys, mocker): # Added mocker
    # Simulate a generic network error (e.g., DNS failure, connection timeout)
    mock_requests_get.side_effect = requests.exceptions.RequestException("Network Error")

    result = get_pr_details(VALID_PR_URL)

    assert result is None
    captured = capsys.readouterr()
    assert f"Error fetching PR data for {VALID_PR_URL}: Network Error" in captured.out

def test_get_pr_details_unexpected_error_key_error(mock_requests_get, capsys, mocker):
    # Simulate an unexpected error, e.g., a KeyError due to malformed JSON response
    # Only the first call (PR metadata) is mocked to return malformed data
    mock_response_malformed = mocker.Mock(spec=requests.Response)
    mock_response_malformed.raise_for_status = mocker.Mock()
    mock_response_malformed.status_code = 200
    # This malformed JSON will likely cause a KeyError when 'title' or other keys are accessed
    mock_response_malformed.json = mocker.Mock(return_value={"unexpected_structure": True})

    mock_requests_get.return_value = mock_response_malformed

    result = get_pr_details(VALID_PR_URL)
    assert result is None
    captured = capsys.readouterr()
    # The exact error message might depend on what key is accessed first.
    # Let's check for the generic "An unexpected error occurred" message.
    assert f"An unexpected error occurred while processing {VALID_PR_URL}" in captured.out
    # A more specific check could be: assert "KeyError" in captured.out if we know it's a KeyError
    # For now, the generic message is sufficient as per the function's exception handling.

# The placeholder test_example_pr_parser is automatically removed by overwriting the file.
