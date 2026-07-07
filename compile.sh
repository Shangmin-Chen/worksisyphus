#!/bin/bash
# Compile LaTeX templates from templates/ to PDF in resumes/

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting LaTeX resume templates compilation..."
mkdir -p resumes

# Compile resumes
for f in templates/resumes/*.tex; do
    if [ -f "$f" ]; then
        filename=$(basename "$f" .tex)
        echo "----------------------------------------"
        echo "Compiling resume template: $filename..."
        echo "----------------------------------------"
        
        # Compile using pdflatex via latexmk
        latexmk -pdf -interaction=nonstopmode -output-directory=templates/resumes "$f"
        
        # Move the compiled PDF to the resumes/ folder
        mv "templates/resumes/$filename.pdf" "resumes/"
        
        # Clean up temporary auxiliary build files
        latexmk -c -output-directory=templates/resumes "$f"
    fi
done

# Compile cover letters
for f in templates/cover_letters/*.tex; do
    if [ -f "$f" ]; then
        filename=$(basename "$f" .tex)
        echo "----------------------------------------"
        echo "Compiling cover letter template: $filename..."
        echo "----------------------------------------"
        
        # Compile using pdflatex via latexmk
        latexmk -pdf -interaction=nonstopmode -output-directory=templates/cover_letters "$f"
        
        # Move the compiled PDF to the resumes/ folder
        mv "templates/cover_letters/$filename.pdf" "resumes/"
        
        # Clean up temporary auxiliary build files
        latexmk -c -output-directory=templates/cover_letters "$f"
    fi
done

echo "----------------------------------------"
echo "Compiling JSON resume..."
echo "----------------------------------------"
python src/compile.py --resume templates/resume.json --output resumes/Simon_Chen_Resume_Compiled.tex

echo "----------------------------------------"
echo "All resumes successfully compiled!"
echo "----------------------------------------"
