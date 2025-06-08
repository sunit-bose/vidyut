import argparse
import concurrent.futures
from typing import Tuple, Optional, List, Dict
from pathlib import Path # Ensure Path is imported at top level if used globally
import sys # Ensure sys is imported at top level for path manipulation

# Conditional imports for constants from code_analyzer
# This structure ensures that even if main.py is imported as a module elsewhere,
# these constants are attempted to be imported.
# And if run as a script, the path adjustment happens before this.

# Initial path adjustment for script execution
if __package__ is None or __package__ == '':
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

from src.pr_parser import get_pr_details
from src.code_analyzer import analyze_code_changes, ALL_ANALYSES, DEFAULT_ANALYSES_TO_RUN
from src.suggestion_generator import generate_suggestions


MAX_WORKERS = 4

def process_single_pr(pr_url: str, analyses_to_run: List[str]) -> Tuple[str, Optional[str], Optional[str], Optional[List[str]], Optional[str]]:
    try:
        print(f"Thread: Starting processing for {pr_url}")
        pr_data = get_pr_details(pr_url)
        if not pr_data:
            return pr_url, None, None, None, f"Failed to fetch PR details (as reported by get_pr_details)."

        pr_title = pr_data.get('title', 'N/A')
        html_url_from_data = pr_data.get('html_url', pr_url)

        print(f"Thread: Analyzing code for {pr_title} ({pr_url}) with analyses: {analyses_to_run}...")
        analysis_results = analyze_code_changes(pr_data, analyses_to_run)

        suggestions = generate_suggestions(analysis_results)

        print(f"Thread: Finished processing for {pr_title} ({pr_url})")
        return pr_url, pr_title, html_url_from_data, suggestions, None
    except Exception as e:
        print(f"Thread: Unexpected error while processing {pr_url}: {e}")
        return pr_url, None, None, None, f"Unexpected error during processing of {pr_url}: {str(e)}"

def main():
    # ArgumentParser setup moved inside main() to ensure ALL_ANALYSES is defined
    # when the help string is constructed, regardless of execution context.
    parser = argparse.ArgumentParser(description="AI Agent for PR Review - Concurrent Processing")
    parser.add_argument("pr_urls", nargs='+', help="One or more GitHub Pull Request URLs to review.")
    parser.add_argument(
        "--analyses",
        type=str,
        default=None,
        help="Comma-separated list of analyses to run (e.g., 'python_ast,flake8'). "
             f"Available: {', '.join(ALL_ANALYSES)}. "
             "Special values: 'all', 'none', 'default'."
    )

    args = parser.parse_args()
    pr_urls_to_process = args.pr_urls

    requested_analyses_str = args.analyses
    analyses_to_run = []

    if requested_analyses_str is None or requested_analyses_str.lower() == 'default':
        analyses_to_run = DEFAULT_ANALYSES_TO_RUN
    elif requested_analyses_str.lower() == 'all':
        analyses_to_run = ALL_ANALYSES
    elif requested_analyses_str.lower() == 'none':
        analyses_to_run = []
    else:
        user_choices = [choice.strip().lower() for choice in requested_analyses_str.split(',')]
        valid_choices = []
        invalid_choices = []
        for choice in user_choices:
            if choice in ALL_ANALYSES:
                valid_choices.append(choice)
            else:
                invalid_choices.append(choice)
        if invalid_choices:
            print(f"Warning: Unknown analysis type(s) '{', '.join(invalid_choices)}' ignored. Available: {', '.join(ALL_ANALYSES)}")
        analyses_to_run = valid_choices

    print(f"Analyses to run: {analyses_to_run if analyses_to_run else 'None selected (or explicitly chosen via ''none'')'}")
    print(f"Starting review for {len(pr_urls_to_process)} PR(s) with up to {MAX_WORKERS} concurrent workers.")
    print("---" * 10)

    processed_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(process_single_pr, url, analyses_to_run): url for url in pr_urls_to_process
        }
        for future in concurrent.futures.as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                result_tuple = future.result()
                processed_results.append(result_tuple)
            except Exception as exc:
                print(f"Main: {original_url} generated an exception during future.result(): {exc}")
                processed_results.append((original_url, None, None, None, f"Critical exception during execution: {exc}"))

    print("\n" + "---" * 10)
    print("All PRs Processed. Review Summaries:")
    print("---" * 10 + "\n")

    for res_pr_url, res_pr_title, res_html_url, res_suggestions, res_error_message in processed_results:
        print(f"Review for PR: {res_pr_url}")
        if res_pr_title:
            print(f"  Title: {res_pr_title}")
        actual_link = res_html_url if res_html_url else res_pr_url
        print(f"  Link: {actual_link}")
        if res_error_message:
            print(f"  Status: FAILED"); print(f"  Error: {res_error_message}")
        elif not res_suggestions or (len(res_suggestions) == 1 and "No specific suggestions" in res_suggestions[0]):
            print("  Status: COMPLETED (No specific actionable suggestions generated)")
            if res_suggestions and "No specific suggestions" not in res_suggestions[0]:
                 for i, suggestion in enumerate(res_suggestions, 1): print(f"    {i}. {suggestion}")
        else:
            print("  Status: COMPLETED"); print("  Suggestions:")
            for i, suggestion in enumerate(res_suggestions, 1): print(f"    {i}. {suggestion}")
        print("---" * 10 + "\n")

if __name__ == "__main__":
    main()
