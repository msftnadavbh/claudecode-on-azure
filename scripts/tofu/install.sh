#!/usr/bin/env bash
set -euo pipefail

version=1.12.3
archive="tofu_${version}_linux_amd64.zip"
sha256="46b48c3438c65cf479fc076c9281422ffa2f493548d1e813d154c835c5986a08"
bin_dir="${RUNNER_TEMP:-/tmp}/tofu-bin"

mkdir -p "${bin_dir}"
curl --fail --location --silent --show-error \
  "https://github.com/opentofu/opentofu/releases/download/v${version}/${archive}" \
  --output "${bin_dir}/${archive}"
printf '%s  %s\n' "${sha256}" "${bin_dir}/${archive}" | sha256sum --check --status
unzip -q -o "${bin_dir}/${archive}" -d "${bin_dir}"
echo "${bin_dir}" >> "${GITHUB_PATH:?GITHUB_PATH must be set}"
