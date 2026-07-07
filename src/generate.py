#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def load_dotenv() -> dict[str, str]:
    """Load key-value pairs from a local .env file if it exists."""
    env = {}
    path = Path(".env")
    if path.is_file():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip().strip("'\"")
    return env


def call_gemini(prompt: str, api_key: str) -> str:
    """Call the Gemini 2.5 Flash API with the provided prompt."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidates = res_data.get("candidates", [])
            if not candidates:
                raise ValueError(f"Empty candidates in response: {res_data}")
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return text
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        raise RuntimeError(f"Gemini API HTTP Error {e.code}: {err_msg}")
    except Exception as e:
        raise RuntimeError(f"Failed to communicate with Gemini API: {e}")


def clean_latex_response(text: str) -> str:
    """Extract raw LaTeX text from the LLM response, stripping markdown code blocks."""
    text = text.strip()
    if text.startswith("```latex"):
        text = text[8:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def compile_latex_to_pdf(output_tex: Path) -> Path:
    """Compile a .tex file to PDF using latexmk or pdflatex and move it to resumes/."""
    parent_dir = output_tex.parent
    filename = output_tex.stem
    pdf_dest = Path("resumes") / f"{filename}.pdf"
    Path("resumes").mkdir(parents=True, exist_ok=True)
    
    try:
        subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-output-directory=" + str(parent_dir), str(output_tex)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pdf_src = parent_dir / f"{filename}.pdf"
        if pdf_src.is_file():
            shutil.move(pdf_src, pdf_dest)
        subprocess.run(
            ["latexmk", "-c", "-output-directory=" + str(parent_dir), str(output_tex)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        try:
            print("latexmk failed/unavailable, falling back to pdflatex...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory=" + str(parent_dir), str(output_tex)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pdf_src = parent_dir / f"{filename}.pdf"
            if pdf_src.is_file():
                shutil.move(pdf_src, pdf_dest)
        except Exception as e:
            print(f"Compilation warning: could not compile PDF (error: {e})")
            
    return pdf_dest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate tailored resumes and cover letters using Gemini AI."
    )
    parser.add_argument(
        "--mode",
        choices=["resume", "cover-letter", "both"],
        required=True,
        help="What to generate: 'resume', 'cover-letter', or 'both'",
    )
    parser.add_argument(
        "--jd",
        required=True,
        help="Job Description text or path to a file containing the Job Description",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Gemini API Key (overrides GEMINI_API_KEY environment variable or .env file)",
    )
    parser.add_argument(
        "--experiences",
        type=Path,
        default=Path("templates/experiences.json"),
        help="Path to experiences.json master data; default: templates/experiences.json",
    )
    parser.add_argument(
        "--resume-template",
        type=Path,
        default=Path("templates/resumes/jakes_resume_template.tex"),
        help="Path to LaTeX resume template; default: templates/resumes/jakes_resume_template.tex",
    )
    parser.add_argument(
        "--cover-letter-template",
        type=Path,
        default=Path("templates/cover_letters/default_cover_letter.tex"),
        help="Path to LaTeX cover letter template; default: templates/cover_letters/default_cover_letter.tex",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tex_files"),
        help="Output directory for generated .tex files; default: tex_files",
    )
    parser.add_argument(
        "--output-name",
        default="tailored",
        help="Base name for the generated files; default: tailored",
    )

    args = parser.parse_args()

    # Load API Key
    env = load_dotenv()
    api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: Gemini API Key is required. Please set GEMINI_API_KEY in your environment, a .env file, or pass it via --api-key.")
        return 1

    # Load Job Description
    jd_content = args.jd
    jd_path = Path(args.jd)
    if jd_path.is_file():
        with open(jd_path, "r", encoding="utf-8") as f:
            jd_content = f.read()

    # Load Experiences JSON
    if not args.experiences.is_file():
        print(f"Error: Experiences JSON file not found at {args.experiences}")
        return 1
    with open(args.experiences, "r", encoding="utf-8") as f:
        experiences_data = f.read()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tailored Resume Generation
    if args.mode in ["resume", "both"]:
        if not args.resume_template.is_file():
            print(f"Error: Resume template file not found at {args.resume_template}")
            return 1
        with open(args.resume_template, "r", encoding="utf-8") as f:
            resume_template_content = f.read()

        print("Generating tailored LaTeX resume via Gemini AI...")
        prompt = f"""
You are an expert resume writer. Your task is to generate a tailored resume in LaTeX format.
We are using the following base LaTeX template:
---
{resume_template_content}
---

And here is the candidate's master experience database in JSON format:
---
{experiences_data}
---

Here is the Job Description for the role they are applying for:
---
{jd_content}
---

Generate a tailored LaTeX resume that:
1. Adapts the LaTeX template, replacing 'Jake Ryan' and Southwestern University details with the candidate's details (Simon Chen, Boston University, etc.) from the JSON.
2. Selects the most relevant experiences, projects, and skills from the master JSON database that match the target Job Description.
3. Tailors/rewrites the selected bullet points to highlight skills, keywords, and achievements aligned with the Job Description.
4. Fits exactly on a single page, keeping descriptions punchy and professional. Select the top 2-3 most relevant experiences and the top 2-3 most relevant projects.
5. Preserves all the LaTeX packages, formats, custom commands, and environment setups of the original template.
6. Returns ONLY the valid LaTeX code. Do NOT wrap it in code blocks or include markdown formatting.
"""
        try:
            raw_response = call_gemini(prompt, api_key)
            latex_code = clean_latex_response(raw_response)
            
            output_tex_path = args.output_dir / f"{args.output_name}_resume.tex"
            with open(output_tex_path, "w", encoding="utf-8") as f:
                f.write(latex_code)
            
            print(f"Tailored LaTeX resume saved: {output_tex_path}")
            print("Compiling tailored resume to PDF...")
            pdf_path = compile_latex_to_pdf(output_tex_path)
            print(f"Tailored resume PDF compiled successfully: {pdf_path}")
        except Exception as e:
            print(f"Error generating tailored resume: {e}")
            if args.mode == "resume":
                return 1

    # 2. Tailored Cover Letter Generation
    if args.mode in ["cover-letter", "both"]:
        if not args.cover_letter_template.is_file():
            print(f"Error: Cover letter template file not found at {args.cover_letter_template}")
            return 1
        with open(args.cover_letter_template, "r", encoding="utf-8") as f:
            cover_letter_template_content = f.read()

        print("Generating tailored cover letter via Gemini AI...")
        prompt = f"""
You are an expert career consultant. Your task is to generate a tailored cover letter in LaTeX format.
We are using the following base LaTeX template:
---
{cover_letter_template_content}
---

And here is the candidate's master experience database in JSON format:
---
{experiences_data}
---

Here is the Job Description for the role they are applying for:
---
{jd_content}
---

Generate a tailored LaTeX cover letter that:
1. Fills in the cover letter template placeholders (date, recipient address, role, company).
2. Incorporates details from the candidate's master experiences database that directly match the core requirements of the Job Description.
3. Expresses professional interest and maps the candidate's background cleanly to the target role.
4. Preserves all the LaTeX formatting, packages, and custom commands of the original cover letter template.
5. Returns ONLY the valid LaTeX code. Do NOT wrap it in code blocks or include markdown formatting.
"""
        try:
            raw_response = call_gemini(prompt, api_key)
            latex_code = clean_latex_response(raw_response)
            
            output_tex_path = args.output_dir / f"{args.output_name}_cover_letter.tex"
            with open(output_tex_path, "w", encoding="utf-8") as f:
                f.write(latex_code)
            
            print(f"Tailored LaTeX cover letter saved: {output_tex_path}")
            print("Compiling tailored cover letter to PDF...")
            pdf_path = compile_latex_to_pdf(output_tex_path)
            print(f"Tailored cover letter PDF compiled successfully: {pdf_path}")
        except Exception as e:
            print(f"Error generating tailored cover letter: {e}")
            if args.mode == "cover-letter":
                return 1

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
