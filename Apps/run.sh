#!/bin/sh
set -eu

environment_name="solarphysics_env_latest"
miniforge_root="${SOLAR_MINIFORGE_ROOT:-}"
config_path=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --environment-name)
            [ "$#" -ge 2 ] || { echo "Missing value for --environment-name" >&2; exit 2; }
            environment_name="$2"
            shift 2
            ;;
        --miniforge-root)
            [ "$#" -ge 2 ] || { echo "Missing value for --miniforge-root" >&2; exit 2; }
            miniforge_root="$2"
            shift 2
            ;;
        --config-path)
            [ "$#" -ge 2 ] || { echo "Missing value for --config-path" >&2; exit 2; }
            config_path="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done

case "$environment_name" in
    solarphysics_env_latest|solarphysics_env) ;;
    *) echo "Unsupported environment '$environment_name'." >&2; exit 2 ;;
esac

if [ -z "$miniforge_root" ] && [ -n "${CONDA_EXE:-}" ]; then
    conda_parent=$(dirname "$CONDA_EXE")
    case "$(basename "$conda_parent")" in
        bin|condabin|Scripts) miniforge_root=$(dirname "$conda_parent") ;;
    esac
fi
if [ -z "$miniforge_root" ]; then
    for candidate in "$HOME/miniforge3" "$HOME/Miniforge3"; do
        if [ -d "$candidate" ]; then
            miniforge_root="$candidate"
            break
        fi
    done
fi
if [ -z "$miniforge_root" ] || [ ! -d "$miniforge_root" ]; then
    echo "Miniforge was not found. Set SOLAR_MINIFORGE_ROOT or pass --miniforge-root." >&2
    exit 2
fi

python_executable="$miniforge_root/envs/$environment_name/bin/python"
if [ ! -x "$python_executable" ]; then
    echo "Miniforge environment '$environment_name' is missing: $python_executable" >&2
    exit 2
fi

apps_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
workspace_root=$(dirname "$apps_root")
if [ -n "$config_path" ]; then
    exec "$python_executable" -m solar_apps.launcher \
        --workspace-root "$workspace_root" \
        --miniforge-root "$miniforge_root" \
        --environment-name "$environment_name" \
        --config-path "$config_path" \
        --launcher-name "Apps/run.sh" -- "$@"
fi
exec "$python_executable" -m solar_apps.launcher \
    --workspace-root "$workspace_root" \
    --miniforge-root "$miniforge_root" \
    --environment-name "$environment_name" \
    --launcher-name "Apps/run.sh" -- "$@"
