# Publishing the container image

The **Publish container image** workflow builds the root `Dockerfile` with the
repository root as its context and publishes to
`ghcr.io/rafaelpierre/reasoning-from-scratch` (or `ghcr.io/<owner>/<repo>` in a fork).
It builds `linux/amd64`, as required by the Dockerfile's CUDA stage.

The workflow runs on pushes to `main` that change the Dockerfile, its ignore
files, `pyproject.toml`, or the workflow itself; on `v*` tag pushes; and manually
from the repository's **Actions** tab. Tag pushes run regardless of path filters.
It authenticates using the automatic `GITHUB_TOKEN` with `packages: write`;
no personal access token or additional repository secret is required.

Images receive a `sha-<full-commit-sha>` tag. Builds on the default branch also
update `latest`; version tag pushes publish the exact Git tag, such as `v1.0.0`.
Version builds do not move `latest`. Build layers are cached in GitHub Actions.

## Make the package public once

GitHub creates new container packages as **private**, even for public
repositories. After the first successful workflow run:

1. Open the repository's **Packages** section and select the
   `reasoning-from-scratch` container package.
2. Open **Package settings**.
3. Under **Danger Zone**, choose **Change visibility**, select **Public**, and
   confirm the package name.

This is a one-time package setting, separate from repository visibility. Future
pushes to the same package preserve it. See
[GitHub's container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).
If this package already exists and publishing is denied, grant this repository
write access under the package's **Manage Actions access** settings.

After making the package public, anyone can pull it without authentication:

```sh
docker pull ghcr.io/rafaelpierre/reasoning-from-scratch:latest
```

Commit the root `Dockerfile`, `Dockerfile.dockerignore`, and `pyproject.toml`
alongside the workflow so the runner has the build inputs. The first push to
`main` will start the build, or use **Actions → Publish container image → Run
workflow** after the workflow is on the default branch.
