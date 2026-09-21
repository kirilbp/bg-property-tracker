#!/bin/bash
# Reusable commit+push helper with the same conflict-retry logic scrape.yml
# and the other automated workflows in this repo use (see docs/decisions.md,
# 2026-09-20 entry: "git-push retry loop: rebase can't even start if tree
# still dirty after commit") - handles concurrent pushes from the many
# other automated jobs that write to this repo, including the residual-
# commit fix for when the tree is unexpectedly still dirty right after the
# main commit (which used to make this retry loop fail before a real
# rebase attempt even started).
#
# Usage: commit_and_push.sh "<commit message>" <path> [<path> ...]
set -e

if [ $# -lt 2 ]; then
  echo "Usage: $0 \"<commit message>\" <path> [<path> ...]" >&2
  exit 1
fi

MSG="$1"
shift

git config user.name "property-bot"
git config user.email "bot@users.noreply.github.com"

pushed=false
for attempt in 1 2 3 4 5; do
  git add "$@"
  git diff --cached --quiet || git commit -m "$MSG"
  # See docs/decisions.md 2026-09-20: rebase can refuse to even start if
  # the tree is unexpectedly still dirty after the commit above - commit
  # whatever's left rather than let that block the retry loop entirely.
  if [ -n "$(git status --porcelain)" ]; then
    echo "Tree still dirty after the commit above - committing the remainder before rebase"
    git add -A
    git commit -m "$MSG (residual)"
  fi
  if ! git pull --rebase origin main; then
    echo "Rebase hit a content conflict - keeping main's version of the conflicted files and continuing"
    git diff --name-only --diff-filter=U | xargs -r git checkout --ours --
    git diff --name-only --diff-filter=U | xargs -r git add
    if ! GIT_EDITOR=true git rebase --continue; then
      echo "rebase --continue still failed after auto-resolving conflicts - aborting this attempt and retrying from a clean state"
      git rebase --abort || true
      sleep $((attempt * 5))
      continue
    fi
  fi
  if git push; then
    pushed=true
    break
  fi
  echo "Push rejected (attempt $attempt/5) - re-pulling and retrying"
  sleep $((attempt * 5))
done

if [ "$pushed" != "true" ]; then
  echo "::error::Failed to push after 5 attempts - giving up"
  exit 1
fi
echo "Pushed successfully."
