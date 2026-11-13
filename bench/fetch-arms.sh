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
# pstack-src: the 3.0.0 round (36885ea). pstack47: pstack 0.9.108 (47c6f80), the 3.3.0 round.
fetch "$arms/pstack-src" https://github.com/michael-denyer/pstack-claude.git 36885ea631d2afd9482cf9333cc4bbc829b3b02d
test -d "$arms/pstack-src/plugins/pstack"
fetch "$arms/pstack47-src" https://github.com/michael-denyer/pstack-claude.git 47c6f8020ad3a4dc533f220eb362a144bfac2153
rm -rf "$arms/pstack47"
cp -R "$arms/pstack47-src/plugins/pstack" "$arms/pstack47"

for version in 2.15.3 3.0.0 3.2.0; do  # Orchestra arms from their release tags
  dir="$arms/orchestra-$version"
  if [ -f "$dir/plugin.json" ]; then
    echo "ok   $dir"
  else
    rm -rf "$dir"
    mkdir -p "$dir"
    git -C "$repo" archive "v$version" plugins/orchestra | tar -x -C "$dir" --strip-components=2
    echo "got  $dir from tag v$version"
  fi
done
