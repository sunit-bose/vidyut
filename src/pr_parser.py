import requests
import re
import base64 # Add this import

def get_pr_details(pr_url):
    """
    Fetches and parses PR data from a GitHub PR URL.

    Args:
        pr_url (str): The URL of the GitHub Pull Request.

    Returns:
        dict: A dictionary containing PR details (e.g., title, description, files changed, diff).
              Returns None if the URL is invalid or fetching fails.
    """
    # Example PR URL: https://github.com/owner/repo/pull/123
    match = re.match(r"https://github.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not match:
        print(f"Invalid GitHub PR URL: {pr_url}")
        return None

    owner, repo, pull_number = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pull_number}"
    diff_url = f"{pr_url}.diff" # Standard way to get diff

    headers = {"Accept": "application/vnd.github.v3+json"}
    pr_data = {}

    try:
        # Get PR metadata
        response = requests.get(api_url, headers=headers)
        response.raise_for_status() # Raises an exception for 4XX or 5XX status codes
        pr_json = response.json()

        # Store owner, repo, and head_sha for later use (e.g., fetching file content)
        pr_data['owner'] = owner
        pr_data['repo'] = repo
        pr_data['head_sha'] = pr_json.get('head', {}).get('sha')

        pr_data['title'] = pr_json.get('title')
        pr_data['description'] = pr_json.get('body')
        pr_data['author'] = pr_json.get('user', {}).get('login')
        pr_data['html_url'] = pr_json.get('html_url')
        pr_data['created_at'] = pr_json.get('created_at')
        pr_data['updated_at'] = pr_json.get('updated_at')
        pr_data['state'] = pr_json.get('state') # e.g., open, closed, merged
        pr_data['commits_url'] = pr_json.get('commits_url')
        pr_data['comments_url'] = pr_json.get('comments_url')

        # Get PR diff
        diff_response = requests.get(diff_url, headers={"Accept": "application/vnd.github.v3.diff"})
        diff_response.raise_for_status()
        pr_data['diff'] = diff_response.text

        # Get list of files changed
        files_api_url = f"{api_url}/files"
        files_response = requests.get(files_api_url, headers=headers)
        files_response.raise_for_status()
        files_json = files_response.json()

        pr_data['files_changed'] = []
        for file_info in files_json:
            pr_data['files_changed'].append({
                'filename': file_info.get('filename'),
                'status': file_info.get('status'), # e.g., 'added', 'modified', 'removed'
                'additions': file_info.get('additions'),
                'deletions': file_info.get('deletions'),
                'changes': file_info.get('changes'),
                'patch': file_info.get('patch') # The actual changes for this file
            })

        return pr_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR data for {pr_url}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing {pr_url}: {e}")
        return None

if __name__ == '__main__':
    # Example usage:
    # Replace with a real PR URL for testing
    # example_pr_url = "https://github.com/octocat/Spoon-Knife/pull/3"
    # For testing without making actual calls during this phase, we'll skip direct execution.
    # print("Testing with an example PR URL (requires a valid PR to work):")
    # details = get_pr_details(example_pr_url)
    # if details:
    #     print(f"Title: {details['title']}")
    #     print(f"Author: {details['author']}")
    #     print(f"Files changed: {len(details['files_changed'])}")
    #     for file_detail in details['files_changed']:
    #         print(f"  - {file_detail['filename']} ({file_detail['status']})")
    #     # print(f"Diff preview: {details['diff'][:500]}") # Example: Print first 500 chars of diff
    # else:
    #     print("Could not retrieve PR details.")
    pass


def get_file_content_at_ref(owner: str, repo: str, file_path: str, ref: str, headers: dict) -> str | None:
    """
    Fetches the content of a file from a GitHub repository at a specific ref (commit SHA, branch, tag).

    Args:
        owner (str): The owner of the repository.
        repo (str): The name of the repository.
        file_path (str): The path to the file within the repository.
        ref (str): The commit SHA, branch name, or tag name.
        headers (dict): Headers to use for the API request (e.g., for auth, Accept).

    Returns:
        str: The decoded content of the file, or None if an error occurs.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    params = {'ref': ref}

    try:
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        file_api_data = response.json()

        if file_api_data.get('type') == 'file' and 'content' in file_api_data:
            content_base64 = file_api_data['content']
            # GitHub API sometimes includes newlines in the base64 encoded string.
            # These need to be removed before decoding.
            content_base64_cleaned = content_base64.replace('\n', '')
            decoded_content_bytes = base64.b64decode(content_base64_cleaned)
            decoded_content_str = decoded_content_bytes.decode('utf-8') # Assuming utf-8
            return decoded_content_str
        elif file_api_data.get('type') == 'symlink':
            # Handle symlinks if necessary, e.g., try to resolve target or report as symlink
            print(f"File {file_path} at {ref} is a symlink. Content not directly fetched by this function.")
            return None # Or fetch target content if API supports it and it's desired
        else:
            print(f"Could not retrieve file content for {file_path} at {ref}. API Type: {file_api_data.get('type')}, Data: {file_api_data}")
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"File not found via API: {file_path} at ref {ref} (HTTP 404). URL: {api_url}?ref={ref}")
        else:
            print(f"HTTP error fetching file {file_path} at {ref}: {e}. URL: {api_url}?ref={ref}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching file {file_path} at {ref}: {e}. URL: {api_url}?ref={ref}")
        return None
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        print(f"Error decoding file content for {file_path} at {ref}: {e}")
        return None
    except Exception as e: # Catch-all for other unexpected errors
        print(f"An unexpected error occurred fetching content for {file_path} at {ref}: {e}. URL: {api_url}?ref={ref}")
        return None
