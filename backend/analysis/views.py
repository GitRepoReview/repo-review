import re

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from analysis import github_client as gh
from analysis import reports

OWNER_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
REPO_RE = re.compile(r"[A-Za-z0-9._-]{1,100}")


def health(request):
    return JsonResponse({"status": "ok"})


def _error(status: int, code: str, message: str, **extra) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": code, "message": message, **extra}}, status=status
    )


@require_GET
def report(request, owner, repo):
    if not (OWNER_RE.fullmatch(owner) and REPO_RE.fullmatch(repo)) or repo in (
        ".",
        "..",
    ):
        return _error(
            400, "invalid_repo", "Expected a GitHub repository as owner/repo."
        )
    try:
        data = reports.get_report(owner, repo, timezone.now())
    except gh.RepoNotFound:
        return _error(404, "not_found", f"GitHub has no repository {owner}/{repo}.")
    except gh.EmptyRepo:
        return _error(422, "empty_repo", f"{owner}/{repo} has no commits to analyse.")
    except gh.RateLimited as exc:
        return _error(
            429,
            "rate_limited",
            "GitHub request budget is used up. Try again after the reset.",
            reset_at=exc.limit.reset_at.isoformat(),
        )
    except gh.UpstreamError:
        return _error(
            502, "upstream_error", "GitHub did not answer properly. Try again later."
        )
    return JsonResponse(data)
