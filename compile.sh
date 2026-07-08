#!/bin/bash
# Compile every .tex file in tex_files/ to a PDF in resumes/.
# A failing file does not stop the others; the script exits non-zero
# if anything failed and prints a summary at the end.

set -u

echo "----------------------------------------"
echo "Regenerating JSON resume LaTeX source..."
echo "----------------------------------------"
python3 src/compile.py --resume templates/experiences.json --output tex_files/Simon_Chen_Resume_Compiled.tex --tex-only

mkdir -p resumes tex_files

shopt -s nullglob
files=(tex_files/*.tex)
if [ ${#files[@]} -eq 0 ]; then
    echo "No .tex files in tex_files/ — nothing to compile."
    exit 0
fi

compiled=()
failed=()

for f in "${files[@]}"; do
    filename=$(basename "$f" .tex)
    echo "----------------------------------------"
    echo "Compiling $filename..."
    echo "----------------------------------------"

    if latexmk -pdf -interaction=nonstopmode -output-directory=tex_files "$f"; then
        mv -f "tex_files/$filename.pdf" resumes/
        # Clean up intermediate build files
        latexmk -c -output-directory=tex_files "$f" >/dev/null 2>&1
        compiled+=("$filename")
    else
        echo "ERROR: $filename failed to compile (log kept at tex_files/$filename.log)"
        failed+=("$filename")
    fi
done

echo "----------------------------------------"
echo "Compiled ${#compiled[@]}/${#files[@]} file(s) into resumes/."
if [ ${#compiled[@]} -gt 0 ]; then
    for name in "${compiled[@]}"; do echo "  ok: $name.pdf"; done
fi
if [ ${#failed[@]} -gt 0 ]; then
    for name in "${failed[@]}"; do echo "  FAILED: $name"; done
fi
echo "----------------------------------------"

if [ ${#failed[@]} -gt 0 ]; then
    exit 1
fi
