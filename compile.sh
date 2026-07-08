#!/bin/bash
# Rebuild the canonical resume through the deterministic compiler.
# This script intentionally does not compile arbitrary .tex files.

set -u

mkdir -p resumes tex_files

python3 src/compile.py \
    --resume templates/experiences.json \
    --output tex_files/Simon_Chen_Resume_Compiled.tex \
    --pdf-output resumes/Simon_Chen_Resume_Compiled.pdf
