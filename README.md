# job-hunt

## Compiling LaTeX Resumes

Uses `latexmk` from MacTeX. Compile all LaTeX files from `resumes_latex/` to PDFs in `resumes/`:

```bash
cd resumes_latex
for tex_file in *.tex; do
    latexmk -pdf -interaction=nonstopmode "$tex_file"
    mv "${tex_file%.tex}.pdf" "../resumes/"
done
latexmk -c
```

Or compile a specific resume:
```bash
cd resumes_latex
latexmk -pdf -interaction=nonstopmode master_resume.tex
mv master_resume.pdf ../resumes/
latexmk -c
```

## Which Resume to Use

- **fullstack_engineer_resume.pdf**: Use for full-stack, software engineering, or general developer positions. Highlights Audio Transcription Platform, Fitness Tracking App, and Crime Analytics projects.

- **backend_engineer_resume.pdf**: Use for backend, systems, infrastructure, or blockchain roles. Features Audio Transcription Platform, Decentralized ML Marketplace, and backend-focused experience.

- **mobile_engineer_resume.pdf**: Use for mobile development positions (iOS/Android). Showcases Fitness Tracking App, Audio Transcription Platform, and Crime Analytics with mobile emphasis.

- **master_resume.pdf**: Complete resume with all 4 projects. Use when job description doesn't fit specific categories or for academic/research positions.
