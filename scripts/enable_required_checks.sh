#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-master}"

REMOTE_URL="$(git remote get-url origin)"
if [[ "${REMOTE_URL}" =~ github.com[:/]([^/]+)/([^.]+)(\.git)?$ ]]; then
  OWNER="${BASH_REMATCH[1]}"
  REPO="${BASH_REMATCH[2]}"
else
  echo "Failed to parse owner/repo from origin: ${REMOTE_URL}" >&2
  exit 1
fi

PAYLOAD="$(cat <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["e2e-mock", "e2e-backend"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": false
}
JSON
)"

set +e
RESP="$(
  gh api \
    -X PUT \
    "repos/${OWNER}/${REPO}/branches/${BRANCH}/protection" \
    --input - 2>&1 <<<"${PAYLOAD}"
)"
STATUS=$?
set -e

if [[ ${STATUS} -ne 0 ]]; then
  if grep -qi "Upgrade to GitHub Pro or make this repository public" <<<"${RESP}"; then
    echo "GitHub plan limitation detected." >&2
    echo "Branch protection/rulesets for private repositories require GitHub Pro/Team/Enterprise, or a public repository." >&2
    echo "After upgrading (or making the repo public), rerun:" >&2
    echo "  ./scripts/enable_required_checks.sh ${BRANCH}" >&2
    exit 2
  fi

  echo "${RESP}" >&2
  exit ${STATUS}
fi

echo "Applied required checks on ${OWNER}/${REPO}:${BRANCH}"
echo "- e2e-mock"
echo "- e2e-backend"
