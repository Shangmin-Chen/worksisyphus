from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GitHubReadmeSource:
    slug: str
    owner: str
    repo: str
    branch: str
    path: str

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}.git"

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"

    def raw_url(self, commit_sha: str) -> str:
        return (
            f"https://raw.githubusercontent.com/"
            f"{self.owner}/{self.repo}/{commit_sha}/{self.path}"
        )


JOBRIGHT_2026_SE_NEW_GRAD = GitHubReadmeSource(
    slug="jobright_ai_2026_software_engineer_new_grad",
    owner="jobright-ai",
    repo="2026-Software-Engineer-New-Grad",
    branch="master",
    path="README.md",
)

SOURCES = {
    JOBRIGHT_2026_SE_NEW_GRAD.slug: JOBRIGHT_2026_SE_NEW_GRAD,
}
