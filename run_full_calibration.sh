#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON:-${project_dir}/.venv/bin/python}"

exec "${python_bin}" "${project_dir}/logic/FullCalibration.py" --node 50 --can-bitrate 125 "$@"
