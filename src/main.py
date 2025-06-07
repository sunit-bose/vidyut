import argparse
import concurrent.futures
from typing import Tuple, Optional, List # Added for type hinting

# To allow running this as a script from the root directory (e.g., python -m src.main)
# and also to handle potential imports if this were part of a larger package.
if __package__ is None or __package__ == '':
    # When run as a script, adjust path to import siblings
    import sys
    from pathlib import Path
    # Ensure the project root is in sys.path for `src.` imports
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    from src.pr_parser import get_pr_details
    from src.code_analyzer import analyze_code_changes
    from src.suggestion_generator import generate_suggestions
else:
    # When imported as part of a package
    from .pr_parser import get_pr_details
    from .code_analyzer import analyze_code_changes
    from .suggestion_generator import generate_suggestions

MAX_WORKERS = 4 # Process up to 4 PRs concurrently

def process_single_pr(pr_url: str) -> Tuple[str, Optional[str], Optional[str], Optional[List[str]], Optional[str]]:
    """
    Processes a single PR: fetches details, analyzes, and generates suggestions.
    Returns a tuple: (pr_url, pr_title, html_url, suggestions_list, error_message)
    pr_title, html_url, and suggestions_list will be None if an error occurs that prevents their retrieval.
    error_message will be None if successful.
    """
    try:
        # Note: print statements within this threaded function might interleave in the console.
        # For cleaner output, consider logging or returning all info to main thread for printing.
        print(f"Thread: Starting processing for {pr_url}") # Thread-specific print

        pr_data = get_pr_details(pr_url)
        if not pr_data:
            # get_pr_details already prints an error, so we just return it
            return pr_url, None, None, None, f"Failed to fetch PR details (as reported by get_pr_details)."

        pr_title = pr_data.get('title', 'N/A')
        html_url_from_data = pr_data.get('html_url', pr_url) # Fallback to input pr_url if not in data

        # print(f"Thread: Analyzing code for {pr_title} ({pr_url})") # Example of more thread prints
        analysis_results = analyze_code_changes(pr_data)
        # analyze_code_changes currently returns an empty structure if pr_data is invalid,
        # and prints its own error. This is acceptable for now.

        # print(f"Thread: Generating suggestions for {pr_title} ({pr_url})")
        suggestions = generate_suggestions(analysis_results)

        print(f"Thread: Finished processing for {pr_title} ({pr_url})")
        return pr_url, pr_title, html_url_from_data, suggestions, None
    except Exception as e:
        # Catch any other unexpected errors during the processing of a single PR
        # This is a safety net. Specific errors should ideally be caught within called functions.
        print(f"Thread: Unexpected error while processing {pr_url}: {e}")
        return pr_url, None, None, None, f"Unexpected error during processing of {pr_url}: {str(e)}"


def main():
    # Path adjustment for script execution (idempotent if already done)
    if __package__ is None or __package__ == '':
        current_file_path = Path(__file__).resolve()
        project_root = current_file_path.parent.parent
        if str(project_root) not in sys.path:
            sys.path.append(str(project_root))
        # Re-import with adjusted path if necessary (for the script execution case)
        # This is mostly for linters if they don't pick up the initial adjustment.
        from src.pr_parser import get_pr_details
        from src.code_analyzer import analyze_code_changes
        from src.suggestion_generator import generate_suggestions


    parser = argparse.ArgumentParser(description="AI Agent for PR Review - Concurrent Processing")
    parser.add_argument("pr_urls", nargs='+', help="One or more GitHub Pull Request URLs to review.")

    args = parser.parse_args()
    pr_urls_to_process = args.pr_urls

    print(f"Starting review for {len(pr_urls_to_process)} PR(s) with up to {MAX_WORKERS} concurrent workers.")
    print("---" * 10)

    # Store results as a list of tuples (original_url, title, html_url, suggestions, error_msg)
    processed_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit all PRs to the executor, mapping future to the original URL
        future_to_url = {executor.submit(process_single_pr, url): url for url in pr_urls_to_process}

        for future in concurrent.futures.as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                # result is (pr_url_from_func, pr_title, html_url, suggestions, error_message)
                # pr_url_from_func should be same as original_url
                result_tuple = future.result()
                processed_results.append(result_tuple)
            except Exception as exc:
                # This catches exceptions from the future.result() call itself,
                # not usually from within process_single_pr if that function has its own broad try-except.
                print(f"Main: {original_url} generated an exception during future.result(): {exc}")
                processed_results.append((original_url, None, None, None, f"Critical exception during execution: {exc}"))

    print("\n" + "---" * 10)
    print("All PRs Processed. Review Summaries:")
    print("---" * 10 + "\n")

    # Sort results by the original order of URLs if desired, though as_completed doesn't guarantee order.
    # For now, print as they completed. To sort:
    # url_order_map = {url: i for i, url in enumerate(pr_urls_to_process)}
    # processed_results.sort(key=lambda x: url_order_map.get(x[0], float('inf')))


    for res_pr_url, res_pr_title, res_html_url, res_suggestions, res_error_message in processed_results:
        print(f"Review for PR: {res_pr_url}") # This is the URL passed to process_single_pr
        if res_pr_title:
            print(f"  Title: {res_pr_title}")
        # Use res_html_url which might be more accurate if get_pr_details found it
        actual_link = res_html_url if res_html_url else res_pr_url
        print(f"  Link: {actual_link}")


        if res_error_message:
            print(f"  Status: FAILED")
            print(f"  Error: {res_error_message}")
        elif not res_suggestions or \
             (len(res_suggestions) == 1 and "No specific suggestions" in res_suggestions[0]):
            print("  Status: COMPLETED (No specific actionable suggestions generated)")
            if res_suggestions and "No specific suggestions" not in res_suggestions[0]:
                 # If it's not the "No specific..." message but still considered "no actionable"
                 for i, suggestion in enumerate(res_suggestions, 1):
                    print(f"    {i}. {suggestion}")
        else:
            print("  Status: COMPLETED")
            print("  Suggestions:")
            for i, suggestion in enumerate(res_suggestions, 1):
                print(f"    {i}. {suggestion}")
        print("---" * 10 + "\n")

if __name__ == "__main__":
    # Example: python -m src.main <url1> <url2>
    main()
