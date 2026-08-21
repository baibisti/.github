# Bisti GitHub organization profile — deployment handoff

Status: staged, verified, not published.

GitHub requires an organization repository named `.github`; `profile/README.md` then becomes the public organization profile. This folder already has required repository-root layout.

Deployment requires explicit repository authority:

1. Create or clone `github.com/baibisti/.github`.
2. Copy this folder contents to that repository root without changing `profile/assets/` paths.
3. Run `python3 verify_profile.py`.
4. Review, commit, and push through authorized GitHub credentials.

When checkout has expected `origin`, regeneration promotes local manifest from `ready-for-github-repository-staging` to `approved-github-profile-delivery`. Push/public visibility remain human-verified external gates.
