#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/home/ubuntu/custom-ai-bot/.env}"
KEY_NAME="TAGO_SERVICE_KEY"

mkdir -p "$(dirname "$ENV_FILE")"

# Read secret without echo
read -r -s -p "${KEY_NAME}: " KEY_VALUE
printf "\n"

if [[ -z "${KEY_VALUE}" ]]; then
  echo "Error: empty key" >&2
  exit 2
fi

TMP_FILE="${ENV_FILE}.tmp"

if [[ -f "$ENV_FILE" ]]; then
  # Remove any existing key line
  grep -v "^${KEY_NAME}=" "$ENV_FILE" > "$TMP_FILE" || true
else
  : > "$TMP_FILE"
fi

echo "${KEY_NAME}=${KEY_VALUE}" >> "$TMP_FILE"

mv "$TMP_FILE" "$ENV_FILE"
chmod 600 "$ENV_FILE"

unset KEY_VALUE

echo "Saved ${KEY_NAME} to ${ENV_FILE} (chmod 600)."
echo "Note: Don't share 'docker compose config' output; it will reveal env values."
