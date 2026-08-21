# Bisti GitHub organization profile — deployment handoff

Status: published and verified on `github.com/baibisti`.

GitHub requires an organization repository named `.github`; `profile/README.md` then becomes the public organization profile. This folder already has required repository-root layout.

Deployment record:

1. Public repository: `github.com/baibisti/.github`.
2. Default branch: `main`.
3. Profile source: `profile/README.md` with repository-local GIF/poster assets.
4. Verification: `python3 verify_profile.py`; public organization HTML checked after push.

Checkout uses expected `origin`. Generator records `published-public-github-organization-profile` only when remote `main` exists and GitHub reports `PUBLIC` visibility.
