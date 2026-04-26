# Contributing To GhostHub

Thanks for helping make GhostHub better. This project is a real Raspberry Pi product-sized app, so the best contributions are focused, tested, and respectful of the existing architecture.

## Start Here

1. Read [README.md](README.md) for the product overview.
2. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) before changing backend flow.
3. Use Python 3.9 for development.
4. Keep changes scoped to one feature, bug, or documentation improvement.

## Local Setup

For normal development, create the virtual environment yourself:

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd static/js
npm install
cd ../..
python ghosthub.py
```

Open `http://localhost:5000`.

For Pi deployment from a local checkout, `scripts/deploy_to_pi.sh` can create `venv/` and install dependencies automatically as long as Python 3.9 and Node.js/npm are installed on your computer.

## Validation

Run focused tests while iterating:

```bash
./venv/bin/python -m pytest tests/test_admin_routes.py -v
cd static/js && npm test
```

Run the full development suite before opening a release-facing change:

```bash
./venv/bin/python scripts/run_all_tests.py
```

Hardware-oriented validation lives in `stress_tests/` and should be run on an actual Pi when changes affect storage, upload limits, networking, HDMI, service setup, or long-running runtime behavior.

## Backend Rules

- Use the `specter-runtime` package with `from specter import ...` imports.
- Keep HTTP routes and socket/event ingress inside SPECTER controllers.
- Keep business logic in services.
- Do not add bare Flask blueprints or direct Socket.IO handlers outside the established runtime boundaries.
- Use parameterized queries and existing auth helpers.
- Mirror admin checks consistently between HTTP and socket paths.

## Frontend Rules

- Frontend code is ES modules.
- Use the vendored RAGOT runtime at `static/js/libs/ragot.esm.min.js`.
- Keep lifecycle-owned listeners, timers, and socket handlers inside the existing module/component patterns.
- Use `document.getElementById()` for IDs containing `::`.
- Avoid inline global handlers in generated HTML.

## Documentation Rules

Public docs should help a new user succeed quickly:

- Put the fastest path first.
- Prefer copy-pasteable commands.
- Keep internal planning notes out of the public tree.
- Use neutral OSS language, not private launch or customer handoff language.
- Keep Python references aligned with Python 3.9.

## Pull Requests

Good PRs include:

- A clear description of what changed and why.
- The validation you ran.
- Screenshots or short clips for visible UI changes.
- Notes about Raspberry Pi hardware testing when relevant.

## License

By contributing, you agree that your contribution is provided under the repository license, AGPL-3.0.
