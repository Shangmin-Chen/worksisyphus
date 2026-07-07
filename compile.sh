#!/bin/bash
# Compile LaTeX files from tex_files/ to PDF in resumes/

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting LaTeX resumes/cover letters compilation..."
mkdir -p resumes
mkdir -p tex_files

echo "----------------------------------------"
echo "Compiling JSON resume..."
echo "----------------------------------------"
python src/compile.py --resume templates/experiences.json --output tex_files/Simon_Chen_Resume_Compiled.tex --tex-only

# Compile all .tex files in tex_files/
for f in tex_files/*.tex; do
    if [ -f "$f" ]; then
        filename=$(basename "$f" .tex)
        echo "----------------------------------------"
        echo "Compiling $filename..."
        echo "----------------------------------------"
        
        # Compile using pdflatex via latexmk
        latexmk -pdf -interaction=nonstopmode -output-directory=tex_files "$f"
        
        # Move the compiled PDF to the resumes/ folder
        mv "tex_files/$filename.pdf" "resumes/"
        
        # Clean up temporary auxiliary build files
        latexmk -c -output-directory=tex_files "$f"
    fi
done

echo "----------------------------------------"
echo "All files successfully compiled!"
echo "----------------------------------------"
