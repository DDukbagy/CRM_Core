#!/usr/bin/env bash
for port in "$@"; do
  hex=$(printf '%04X' "$port")
  for inode in $(awk -v h=":$hex" '$2 ~ h"$" && $4=="0A" {print $10}' /proc/net/tcp /proc/net/tcp6 2>/dev/null); do
    for fd in /proc/[0-9]*/fd/*; do
      if [ "$(readlink "$fd" 2>/dev/null)" = "socket:[$inode]" ]; then
        pid=${fd#/proc/}; pid=${pid%%/*}; pgid=$(awk '{print $5}' /proc/$pid/stat 2>/dev/null)
        [ -n "$pgid" ] && kill -TERM -- "-$pgid" 2>/dev/null; kill -9 "$pid" 2>/dev/null
      fi
    done
  done
done
