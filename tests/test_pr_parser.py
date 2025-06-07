import pytest
import requests # Import requests to allow mocking its exceptions
import base64
from unittest.mock import MagicMock # For more detailed mocking of response objects
from src.pr_parser import get_pr_details, get_file_content_at_ref

# Basic valid PR URL for testing regex and structure
VALID_PR_URL = "https://github.com/owner/repo/pull/123"
VALID_OWNER = "owner"
VALID_REPO = "repo"
VALID_HEAD_SHA = "test_head_sha_12345"
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
        'head': {'sha': VALID_HEAD_SHA} # Added for head_sha
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
    def side_effect_func(url, headers, params=None): # Added params for get_file_content_at_ref calls
        mock_resp = mocker.Mock(spec=requests.Response) # Use spec for better mocking
        mock_resp.raise_for_status = mocker.Mock()
        mock_resp.status_code = 200 # Default to success

        if url == API_BASE_URL:
            mock_resp.json = mocker.Mock(return_value=mock_pr_response_json)
        elif url == DIFF_URL:
            mock_resp.text = mock_diff_text
        elif url == FILES_API_URL:
            mock_resp.json = mocker.Mock(return_value=mock_files_response_json)
        # Add handling for get_file_content_at_ref if it's called by other tests using this fixture
        elif "contents/" in url:
             # This is a generic placeholder, specific tests for get_file_content_at_ref will set their own side_effects
            mock_resp.json = mocker.Mock(return_value={'type': 'file', 'content': base64.b64encode(b"default content").decode('utf-8')})
        else:
            mock_resp.status_code = 404
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(f"Unexpected URL: {url}")
        return mock_resp

    mock_requests_get.side_effect = side_effect_func

    result = get_pr_details(VALID_PR_URL)

    assert result is not None
    assert result['title'] == 'Test PR Title'
    assert result['author'] == 'testuser'
    assert result['owner'] == VALID_OWNER
    assert result['repo'] == VALID_REPO
    assert result['head_sha'] == VALID_HEAD_SHA
    assert result['diff'] == mock_diff_text
    assert len(result['files_changed']) == 2
    assert result['files_changed'][0]['filename'] == 'file1.py'
    assert result['files_changed'][0]['patch'] == '@@ -1 +1 @@\n-old\n+new'

    expected_calls = [
        mocker.call(API_BASE_URL, headers={"Accept": "application/vnd.github.v3+json"}),
        mocker.call(DIFF_URL, headers={"Accept": "application/vnd.github.v3.diff"}),
        mocker.call(FILES_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
    ]
    # For these specific calls in get_pr_details, 'params' argument is not used.
    mock_requests_get.assert_has_calls([
        mocker.call(API_BASE_URL, headers={"Accept": "application/vnd.github.v3+json"}),
        mocker.call(DIFF_URL, headers={"Accept": "application/vnd.github.v3.diff"}),
        mocker.call(FILES_API_URL, headers={"Accept": "application/vnd.github.v3+json"})
    ], any_order=False)


def test_get_pr_details_invalid_url(capsys):
    result = get_pr_details("invalid-url")
    assert result is None
    captured = capsys.readouterr()
    assert "Invalid GitHub PR URL: invalid-url" in captured.out


def test_get_pr_details_github_api_error(mock_requests_get, capsys, mocker):
    mock_requests_get.side_effect = requests.exceptions.HTTPError("API Error")

    result = get_pr_details(VALID_PR_URL)

    assert result is None
    captured = capsys.readouterr()
    assert f"Error fetching PR data for {VALID_PR_URL}: API Error" in captured.out

def test_get_pr_details_network_error(mock_requests_get, capsys, mocker):
    mock_requests_get.side_effect = requests.exceptions.RequestException("Network Error")

    result = get_pr_details(VALID_PR_URL)

    assert result is None
    captured = capsys.readouterr()
    assert f"Error fetching PR data for {VALID_PR_URL}: Network Error" in captured.out

def test_get_pr_details_unexpected_error_key_error(mock_requests_get, capsys, mocker):
    mock_response_malformed = mocker.Mock(spec=requests.Response)
    mock_response_malformed.raise_for_status = mocker.Mock()
    mock_response_malformed.status_code = 200
    mock_response_malformed.json = mocker.Mock(return_value={"unexpected_structure": True})

    mock_requests_get.return_value = mock_response_malformed

    result = get_pr_details(VALID_PR_URL)
    assert result is None
    captured = capsys.readouterr()
    assert f"An unexpected error occurred while processing {VALID_PR_URL}" in captured.out

# --- Tests for get_file_content_at_ref ---

def test_get_file_content_success(mock_requests_get, mocker):
    owner, repo, path, ref = "user", "project", "file.txt", "testsha"
    original_content = "Hello World"
    encoded_content = base64.b64encode(original_content.encode('utf-8')).decode('utf-8')
    mock_api_response = {'type': 'file', 'content': encoded_content, 'encoding': 'base64'}

    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    mock_response_obj.json.return_value = mock_api_response
    mock_response_obj.raise_for_status = mocker.MagicMock()
    mock_response_obj.status_code = 200
    mock_requests_get.return_value = mock_response_obj

    headers = {"Accept": "application/vnd.github.v3+json"}
    content = get_file_content_at_ref(owner, repo, path, ref, headers)

    assert content == original_content
    expected_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    mock_requests_get.assert_called_once_with(expected_url, headers=headers, params={'ref': ref})

def test_get_file_content_not_file_type(mock_requests_get, mocker):
    owner, repo, path, ref = "user", "project", "dir", "testsha"
    mock_api_response = {'type': 'dir', 'name': 'dir'}

    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    mock_response_obj.json.return_value = mock_api_response
    mock_response_obj.raise_for_status = mocker.MagicMock()
    mock_response_obj.status_code = 200
    mock_requests_get.return_value = mock_response_obj

    content = get_file_content_at_ref(owner, repo, path, ref, {})
    assert content is None

def test_get_file_content_http_404_error(mock_requests_get, mocker):
    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    error_response_mock = mocker.MagicMock(spec=requests.Response)
    error_response_mock.status_code = 404
    mock_response_obj.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=error_response_mock
    )
    mock_requests_get.return_value = mock_response_obj

    content = get_file_content_at_ref("u", "r", "p", "s", {})
    assert content is None

def test_get_file_content_other_http_error(mock_requests_get, mocker):
    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    error_response_mock = mocker.MagicMock(spec=requests.Response)
    error_response_mock.status_code = 500
    mock_response_obj.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=error_response_mock
    )
    mock_requests_get.return_value = mock_response_obj

    content = get_file_content_at_ref("u", "r", "p", "s", {})
    assert content is None

def test_get_file_content_unicode_decoding_error(mock_requests_get, mocker):
    owner, repo, path, ref = "user", "project", "file.txt", "testsha"
    invalid_utf8_bytes = b'\xff\xfe\x00'
    encoded_content_invalid_utf8 = base64.b64encode(invalid_utf8_bytes).decode('utf-8')

    mock_api_response = {'type': 'file', 'content': encoded_content_invalid_utf8, 'encoding': 'base64'}

    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    mock_response_obj.json.return_value = mock_api_response
    mock_response_obj.raise_for_status = mocker.MagicMock()
    mock_response_obj.status_code = 200
    mock_requests_get.return_value = mock_response_obj

    content = get_file_content_at_ref(owner, repo, path, ref, {})
    assert content is None

def test_get_file_content_base64_actual_decode_error(mock_requests_get, mocker):
    owner, repo, path, ref = "user", "project", "file.txt", "testsha"
    not_base64_content = "This is not valid base64 content string %$#"
    mock_api_response = {'type': 'file', 'content': not_base64_content, 'encoding': 'base64'}

    mock_response_obj = mocker.MagicMock(spec=requests.Response)
    mock_response_obj.json.return_value = mock_api_response
    mock_response_obj.raise_for_status = mocker.MagicMock()
    mock_response_obj.status_code = 200
    mock_requests_get.return_value = mock_response_obj

    content = get_file_content_at_ref(owner, repo, path, ref, {})
    assert content is None
