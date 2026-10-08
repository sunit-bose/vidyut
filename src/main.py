import argparse
import concurrent.futures
import os
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

from src.pr_parser import get_pr_details, post_pr_comment
from src.code_analyzer import analyze_code_changes, ALL_ANALYSES, DEFAULT_ANALYSES_TO_RUN
from src.suggestion_generator import generate_suggestions


MAX_WORKERS = 4

# Suggestion types that are informational only and must NEVER cause a build/CI failure,
# no matter how high their reported confidence. AI-generated-code detection is a heuristic
# signal for reviewers, not a policy violation, so it is excluded here unconditionally
# even if a caller mistakenly asks to fail on it via --fail-on.
NEVER_FAIL_SUGGESTION_TYPES = {"ai_generated_code"}

# Suggestion types that represent a genuinely critical/actionable problem and are
# reasonable defaults to fail CI on.
DEFAULT_FAIL_ON_TYPES = ["security_concern"]


def _build_pr_comment_markdown(pr_title: Optional[str], suggestions: Optional[List[Dict]]) -> str:
    """Builds a concise Markdown summary of suggestions, suitable for posting as a single PR comment."""
    lines = ["## 🤖 PR Review Agent Summary", ""]
    if pr_title and pr_title != 'N/A':
        lines.append(f"**PR:** {pr_title}")
        lines.append("")

    if not suggestions or (len(suggestions) == 1 and suggestions[0].get("type") == "info"):
        lines.append("No specific actionable suggestions were generated.")
        return "\n".join(lines)

    current_file = None
    for sugg in suggestions:
        sugg_type = sugg.get("type")
        if sugg_type == "file_marker":
            current_file = sugg.get("file_path")
            lines.append(f"\n### 📄 `{current_file}` ({sugg.get('language')})")
        elif sugg_type == "linting":
            lines.append(f"- L{sugg.get('line_number')} [{sugg.get('linter')}:{sugg.get('code')}] {sugg.get('message')}")
        elif sugg_type == "security_concern":
            lines.append(f"- 🛡️ **Security ({sugg.get('severity', 'warning').upper()}):** {sugg.get('message')}")
        elif sugg_type == "react_issue":
            lines.append(f"- ⚛️ **React:** {sugg.get('message')}")
        elif sugg_type == "dependency_note":
            lines.append(f"- 🔗 {sugg.get('message')}")
        elif sugg_type == "test_suggestion":
            lines.append(f"- 🧪 {sugg.get('message')}")
        elif sugg_type == "pom_dependency_change":
            lines.append(f"- 📦 {sugg.get('message')}")
        elif sugg_type == "ai_generated_code":
            lines.append(f"- 🤖 *Informational (does not affect CI status):* AI-generated-code heuristic matched (confidence {sugg.get('confidence')}): {sugg.get('message')}")
        elif sugg_type == "file_impact":
            lines.append(f"- ⚡ {sugg.get('message')}")
    return "\n".join(lines)


def determine_build_status(processed_results: List[Tuple], fail_on_types: List[str]) -> Tuple[bool, List[str]]:
    """
    Decides whether the overall run should be treated as a CI failure.

    Policy:
      - A critical per-PR processing error always counts as a failure.
      - Any suggestion whose 'type' is in `fail_on_types` counts as a failure.
      - 'ai_generated_code' NEVER counts as a failure, even if present in
        fail_on_types, since AI-detection is informational/heuristic only.

    Returns:
        (should_fail, reasons): reasons is a human-readable list explaining why.
    """
    effective_fail_on = set(fail_on_types) - NEVER_FAIL_SUGGESTION_TYPES
    reasons = []
    for pr_url, _pr_title, _html_url, suggestions, error_message in processed_results:
        if error_message:
            reasons.append(f"{pr_url}: critical processing error - {error_message}")
            continue
        for sugg in (suggestions or []):
            if sugg.get("type") in effective_fail_on:
                reasons.append(f"{pr_url}: [{sugg.get('type')}] {sugg.get('message', '')} (File: {sugg.get('file_path', 'N/A')})")
    return (len(reasons) > 0, reasons)


# Updated type hint for the fourth element of the tuple to List[Dict]
def process_single_pr(
    pr_url: str,
    analyses_to_run: List[str],
    checkstyle_config_path: Optional[str] = None,
    flake8_options_str: Optional[str] = None,  # New parameter
    github_token: Optional[str] = None,
    post_comment: bool = False
) -> Tuple[str, Optional[str], Optional[str], Optional[List[Dict]], Optional[str]]:
    try:
        print(f"Thread: Starting processing for {pr_url}")
        pr_data = get_pr_details(pr_url, github_token=github_token)
        if not pr_data:
            return pr_url, None, None, None, f"Failed to fetch PR details (as reported by get_pr_details)."

        pr_title = pr_data.get('title', 'N/A')
        html_url_from_data = pr_data.get('html_url', pr_url)

        print(f"Thread: Analyzing code for {pr_title} ({pr_url}) with analyses: {analyses_to_run}...")
        analysis_results = analyze_code_changes(
            pr_data,
            analyses_to_run,
            checkstyle_config_path=checkstyle_config_path,
            flake8_options_str=flake8_options_str,  # New argument
            github_token=github_token
        )

        suggestions = generate_suggestions(analysis_results)

        if post_comment:
            owner = pr_data.get('owner'); repo = pr_data.get('repo'); pr_number = pr_data.get('number')
            if owner and repo and pr_number:
                comment_body = _build_pr_comment_markdown(pr_title, suggestions)
                post_pr_comment(owner, repo, pr_number, comment_body, github_token)
            else:
                print(f"Thread: Cannot post comment for {pr_url}: missing owner/repo/PR number.")

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
    parser.add_argument(
        "--checkstyle-config",
        type=str,
        default=None,
        help="Path to a custom Checkstyle configuration XML file. If not provided, uses default."
    )
    parser.add_argument(
        "--flake8-options",
        type=str,
        default=None,
        help="Custom options string for Flake8 (e.g., '--ignore E501,W503 --max-line-length=88')."
    )
    parser.add_argument(
        "--github-token",
        type=str,
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub token for authenticated API requests (raises rate limits, required for private "
             "repos and for --post-comment). Defaults to the GITHUB_TOKEN environment variable, which "
             "GitHub Actions provides automatically."
    )
    parser.add_argument(
        "--post-comment",
        action="store_true",
        help="Post a single consolidated summary comment on each reviewed PR. Requires --github-token "
             "(or GITHUB_TOKEN) with 'pull-requests: write' permission."
    )
    parser.add_argument(
        "--fail-on",
        type=str,
        default="security_concern",
        help="Comma-separated suggestion type(s) that should cause this command to exit non-zero "
             "(e.g. for failing a CI check). Default: 'security_concern'. Use 'none' to never fail. "
             "NOTE: 'ai_generated_code' can never be included here - AI-generated-code detection is "
             "informational only (by design) and will never fail the build, regardless of confidence."
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

    fail_on_str = args.fail_on
    if fail_on_str is None or fail_on_str.lower() == 'none':
        fail_on_types = []
    else:
        fail_on_types = [t.strip() for t in fail_on_str.split(',') if t.strip()]
    requested_never_fail = [t for t in fail_on_types if t in NEVER_FAIL_SUGGESTION_TYPES]
    if requested_never_fail:
        print(f"Warning: --fail-on included {requested_never_fail}, but these types never fail the "
              f"build by design (AI-generated-code detection is informational only). Ignoring them for "
              f"failure purposes.")

    if args.post_comment and not args.github_token:
        print("Warning: --post-comment was requested but no GitHub token was provided "
              "(use --github-token or set GITHUB_TOKEN). Comments will not be posted.")

    print(f"Analyses to run: {analyses_to_run if analyses_to_run else 'None selected (or explicitly chosen via ''none'')'}")
    print(f"Fail-on suggestion types: {fail_on_types if fail_on_types else 'None (will not fail based on findings)'}")
    print(f"Starting review for {len(pr_urls_to_process)} PR(s) with up to {MAX_WORKERS} concurrent workers.")
    print("---" * 10)

    processed_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(
                process_single_pr,
                url,
                analyses_to_run,
                args.checkstyle_config,
                args.flake8_options,  # New argument
                args.github_token,
                args.post_comment
            ): url
            for url in pr_urls_to_process
        }
        for future in concurrent.futures.as_completed(future_to_url):
            original_url = future_to_url[future]
            try:
                result_tuple = future.result()
                processed_results.append(result_tuple)
            except Exception as exc:
                print(f"Main: {original_url} generated an exception during future.result(): {exc}")
                processed_results.append((original_url, None, None, None, f"Critical exception during execution: {exc}"))

    print("\n" + "===" * 20)
    print("🚀 AI PR Review - Processing Complete 🚀")
    print("===" * 20 + "\n")

    if not processed_results:
        print("No PRs were processed.")
        return

    total_prs_processed = len(processed_results)
    critical_failure_count = 0
    completed_cleanly_count = 0
    completed_with_analysis_issues_count = 0
    no_suggestions_generated_count = 0 # Renamed for clarity

    # Keywords indicative of analysis tool/step failures within suggestions
    ANALYSIS_ISSUE_KEYWORDS = [
        "error", "warning", "not found", "failed", "syntaxerror",
        "exception", "could not", "operational error", "parse_error",
        "xml_parse_error", "command not found", "unable to parse"
    ]

    for res_pr_url, res_pr_title, res_html_url, res_suggestions, res_error_message in processed_results:
        print("---" * 15) # Separator before each PR's review
        print(f"🔍 Review for PR: {res_pr_url}")
        if res_pr_title and res_pr_title != 'N/A':
            print(f"   Title: {res_pr_title}")
        actual_link = res_html_url if res_html_url else res_pr_url
        print(f"   Link: {actual_link}")

        if res_error_message:
            critical_failure_count += 1
            print(f"   Status: ❌ FAILED")
            print(f"   Error: {res_error_message}")
        else:
            has_analysis_issues = False
            if res_suggestions:
                for sugg_check in res_suggestions:
                    if sugg_check.get("type") == "error":
                        has_analysis_issues = True
                        break
                    # Check messages of file_impact for error keywords
                    if sugg_check.get("type") == "file_impact":
                        msg_lower = sugg_check.get("message", "").lower()
                        if any(keyword in msg_lower for keyword in ANALYSIS_ISSUE_KEYWORDS):
                            has_analysis_issues = True
                            break

            if has_analysis_issues:
                completed_with_analysis_issues_count += 1
                print(f"   Status: ⚠️ COMPLETED (with analysis issues)")
            elif not res_suggestions or \
                 (len(res_suggestions) == 1 and res_suggestions[0].get("type") == "info" and "No specific suggestions" in res_suggestions[0].get("message", "")):
                no_suggestions_generated_count +=1
                print(f"   Status: ✅ COMPLETED (No specific actionable suggestions generated)")
                if res_suggestions: # Print the "no specific suggestions" message
                    print(f"     ℹ️ Info: {res_suggestions[0].get('message')}")
            else:
                completed_cleanly_count += 1
                print(f"   Status: ✅ COMPLETED (Suggestions generated)")

            # Print suggestions if any (even with analysis issues)
            if res_suggestions and not (len(res_suggestions) == 1 and res_suggestions[0].get("type") == "info" and "No specific suggestions" in res_suggestions[0].get("message", "")):
                print("   Suggestions:")
                for sugg in res_suggestions:
                    sugg_type = sugg.get("type")
                    file_path = sugg.get("file_path", "")

                    if sugg_type == "file_marker":
                        print(f"\n  📄 File: {sugg.get('file_path')} ({sugg.get('language')})")
                    elif sugg_type == "linting":
                        print(f"    L{sugg.get('line_number')}:{sugg.get('column_number', '')} [{sugg.get('linter', '')}:{sugg.get('code', '')}] {sugg.get('severity', 'INFO').upper()} - {sugg.get('message')}")
                    elif sugg_type == "dependency_note":
                        print(f"    🔗 Dependency ({sugg.get('language', '')}): {sugg.get('message')}")
                    elif sugg_type == "test_suggestion":
                        print(f"    🧪 Test Suggestion ({sugg.get('language', '')}): {sugg.get('message')}")
                    elif sugg_type == "security_concern":
                        print(f"    🛡️ Security ({sugg.get('severity', 'WARNING').upper()}): {sugg.get('message')} (File: {file_path})")
                    elif sugg_type in ["python_test_stub", "java_test_stub"]:
                        lang_display = "Python" if sugg_type == "python_test_stub" else "Java"
                        print(f"    🤖 Generated {lang_display} Test Stub:")
                        print(f"       Target: {sugg.get('target_definition_type')} '{sugg.get('target_definition_name')}' in {file_path}")
                        print(f"       Suggested Test File: {sugg.get('suggested_test_filename')}")
                        stub_code = sugg.get('details', '# No code provided')
                        print(f"       Code:\n```\n{stub_code}\n```")
                    elif sugg_type == "pom_dependency_change":
                        print(f"    📦 POM Dependency: {sugg.get('message')} (File: {file_path})")
                    elif sugg_type == "general_summary":
                        print(f"    🌐 Overall ({sugg.get('category', 'General')}): {sugg.get('message')}")
                    elif sugg_type == "file_impact":
                        print(f"    ⚡ Impact: {sugg.get('message')} (File: {file_path})")
                    elif sugg_type == "info":
                        if file_path and file_path not in sugg.get('message', ''):
                            print(f"    ℹ️ Info: {sugg.get('message')} (File: {file_path})")
                        else:
                            print(f"    ℹ️ Info: {sugg.get('message')}")
                    elif sugg_type == "error":
                        print(f"    ❌ ERROR (Suggestion Gen): {sugg.get('message')}")
                    elif sugg_type == "ai_generated_code":
                        print(f"    🤖 AI Generated Code Detection: {sugg.get('message')} (Confidence: {sugg.get('confidence')})")
                    elif sugg_type == "react_definition":
                        print(f"    ⚛️ React Definition: {sugg.get('definition_type')} `{sugg.get('definition_name')}` with props: {sugg.get('props')}")
                    elif sugg_type == "react_issue":
                        print(f"    ⚛️ React Issue ({sugg.get('severity', 'warning').upper()}): {sugg.get('message')} (File: {file_path})")
                    else:
                        print(f"    ❓ Unknown Suggestion: {sugg}")
            elif not res_suggestions and not has_analysis_issues and not res_error_message :
                 print(f"     ℹ️ Info: No suggestions or errors reported for this PR.")


        print("\n" + "---" * 15 + "\n")

    print("=" * 40)
    print("📊 Overall Processing Summary 📊")
    print("=" * 40)
    print(f"Total PRs Processed: {total_prs_processed}")
    print(f"   critically failed: {critical_failure_count}")
    print(f"  completed with analysis issues: {completed_with_analysis_issues_count}")
    print(f"  completed with no specific suggestions: {no_suggestions_generated_count}")
    print(f"  completed cleanly with suggestions: {completed_cleanly_count}")
    print("=" * 40)

    should_fail, fail_reasons = determine_build_status(processed_results, fail_on_types)
    print("\n" + "=" * 40)
    print("🚦 Build Status 🚦")
    print("=" * 40)
    if should_fail:
        print("❌ FAILING build due to:")
        for reason in fail_reasons:
            print(f"   - {reason}")
        print("\nNote: AI-generated-code detections never cause a failure, regardless of confidence; "
              "they are informational only.")
        sys.exit(1)
    else:
        print("✅ PASSING (no findings matched the configured --fail-on types).")


if __name__ == "__main__":
    main()
