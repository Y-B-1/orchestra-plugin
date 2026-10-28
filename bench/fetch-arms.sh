#!/usr/bin/env bash
# Fetches the comparison arms into bench/arms at pinned versions. Safe to rerun: an arm that exists is kept.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
arms="$here/arms"
mkdir -p "$arms"

fetch() {  # dir, url, commit
  local dir=$1 url=$2 commit=$3
  if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ]; then echo "ok   $dir"; return; fi
  rm -rf "$dir"
  git init -q "$dir"
  git -C "$dir" fetch -q --depth 1 "$url" "$commit"
  git -C "$dir" checkout -q FETCH_HEAD
  echo "got  $dir at $commit"
}

fetch "$arms/pocock" https://github.com/mattpocock/skills.git 59db609eb1e18aaf59b63284d0e52255aff0c63c
fetch "$arms/pstack-src" https://github.com/michael-denyer/pstack-claude.git 36885ea631d2afd9482cf9333cc4bbc829b3b02d
test -d "$arms/pstack-src/plugins/pstack"

if [ -f "$arms/orchestra-2.15.3/plugin.json" ]; then
  echo "ok   $arms/orchestra-2.15.3"
else
  rm -rf "$arms/orchestra-2.15.3"
  mkdir -p "$arms/orchestra-2.15.3"
  git -C "$repo" archive v2.15.3 plugins/orchestra | tar -x -C "$arms/orchestra-2.15.3" --strip-components=2
  echo "got  $arms/orchestra-2.15.3 from tag v2.15.3"
fi
