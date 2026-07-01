#!/bin/bash
# Compile LaTeX source files from src/ to PDF in resumes/

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting LaTeX resume compilation..."
mkdir -p resumes

for f in src/*.tex; do
    if [ -f "$f" ]; then
        filename=$(basename "$f" .tex)
        echo "----------------------------------------"
        echo "Compiling $filename..."
        echo "----------------------------------------"
        
        # Compile using pdflatex via latexmk
        latexmk -pdf -interaction=nonstopmode -output-directory=src "$f"
        
        # Move the compiled PDF to the resumes/ folder
        mv "src/$filename.pdf" "resumes/"
        
        # Clean up temporary auxiliary build files
        latexmk -c -output-directory=src "$f"
    fi
done

echo "----------------------------------------"
echo "All resumes successfully compiled!"
echo "----------------------------------------"
