#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON:-${project_dir}/.venv/bin/python}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${project_dir}/.cache/matplotlib}"
mkdir -p "${MPLCONFIGDIR}"

exec "${python_bin}" -S "${project_dir}/utils/protected_python.py" "$@"
