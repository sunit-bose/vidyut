import requests
import re

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
    #     # print(f"Diff:
{details['diff'][:500]}...") # Print first 500 chars of diff
    # else:
    #     print("Could not retrieve PR details.")
    pass
