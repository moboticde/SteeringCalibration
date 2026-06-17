#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${PYTHON:-${project_dir}/.venv/bin/python}"

exec "${python_bin}" -S "${project_dir}/protected_python.py" "$@"
