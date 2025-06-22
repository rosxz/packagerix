#!/bin/bash

# Script to cat nurl fetch files based on odd/even issue numbers

if [ $# -ne 1 ]; then
    echo "Usage: $0 [odd|even]"
    echo "  odd  - Display all files with odd issue numbers"
    echo "  even - Display all files with even issue numbers"
    exit 1
fi

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NURL_DIR="$SCRIPT_DIR/nurl_fetches"

if [ ! -d "$NURL_DIR" ]; then
    echo "Error: Directory $NURL_DIR does not exist"
    exit 1
fi

case "$1" in
    odd)
        echo "=== Displaying odd issue numbers ==="
        for f in "$NURL_DIR"/*.nix; do
            if [ -f "$f" ]; then
                num=$(basename "$f" .nix)
                if (( num % 2 == 1 )); then
                    echo -e "\n--- Issue $num ---"
                    cat "$f"
                fi
            fi
        done
        ;;
    even)
        echo "=== Displaying even issue numbers ==="
        for f in "$NURL_DIR"/*.nix; do
            if [ -f "$f" ]; then
                num=$(basename "$f" .nix)
                if (( num % 2 == 0 )); then
                    echo -e "\n--- Issue $num ---"
                    cat "$f"
                fi
            fi
        done
        ;;
    *)
        echo "Error: Invalid argument. Use 'odd' or 'even'"
        exit 1
        ;;
esac
