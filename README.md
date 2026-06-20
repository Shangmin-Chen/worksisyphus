# job-hunt

## Compiling LaTeX Resumes

Uses `latexmk` from MacTeX. Compile the resume LaTeX file from `resumes_latex/` to PDF in `resumes/`:

```bash
cd resumes_latex
latexmk -pdf -interaction=nonstopmode full_time_resume.tex
mv full_time_resume.pdf ../resumes/
latexmk -c
```

## Which Resume to Use

- **full_time_resume.pdf**: The primary, comprehensive resume targeting Software Engineering, Full-Stack, and systems/infrastructure roles. 

### Key Highlights:
- **Education**: Boston University (B.A. in Computer Science, Graduated June 2026)
- **Projects**:
  - **Persephone**: Low-latency production prediction-market trading system integrated with Kalshi (Python, Cython, Rust, FastAPI, React/TypeScript).
  - **Hermes Letters**: Ephemeral end-to-end invite-only letter-sharing platform (Next.js, TypeScript, Supabase, Drizzle ORM, PostgreSQL).
- **Experience**:
  - **RESET Standard** (Software Engineering Intern): React/Vite/Tailwind and Ruby on Rails service engineering with RabbitMQ/Redis pipelines.
  - **Ezesports** (Software Engineer): Supabase-backed Next.js platform migration deployed on Cloudflare Pages.
