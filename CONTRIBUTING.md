# Contributing to BazzCap

Thank you for your interest in contributing to BazzCap. This document explains how to set up a development environment, submit changes, and what to expect during the review process.

---

## Getting Started

### Prerequisites
- Python 3.10 or newer
- Git
- A Linux system with GNOME or KDE Plasma (Wayland recommended)
- The system packages listed in the README (xdotool, ffmpeg, wl-clipboard, grim or spectacle)

### Development Setup

1. Fork the repository on GitHub and clone your fork:
   ```
   git clone https://github.com/YOUR_USERNAME/BazzCap.git
   cd BazzCap
   ```

2. Create a virtual environment and install dependencies:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run BazzCap from the source directory:
   ```
   python bazzcap.py
   ```

---

## Making Changes

### Branch Naming
Create a new branch for your work. Use a descriptive name:
- `fix/hotkey-registration` -- for bug fixes
- `feature/crop-tool` -- for new features
- `docs/install-guide` -- for documentation changes

```
git checkout -b feature/your-feature-name
```

### Code Style
- Follow PEP 8 conventions.
- Use double quotes for strings.
- Use type hints where practical.
- Keep functions focused and reasonably sized.
- Add docstrings to classes and public methods.
- Use meaningful variable names.

### Commit Messages
Write clear, concise commit messages:
- Use the imperative mood: "Add crop tool" not "Added crop tool"
- Keep the first line under 72 characters
- Reference issue numbers if applicable: "Fix hotkey crash on KDE (#12)"

---

## Submitting a Pull Request

1. Push your branch to your fork:
   ```
   git push origin feature/your-feature-name
   ```

2. Open a pull request on GitHub against the `main` branch.

3. In the pull request description:
   - Describe what the change does and why.
   - List any new dependencies or system requirements.
   - Note which desktop environments and display servers you tested on (GNOME/KDE, Wayland/X11).

4. Keep pull requests focused on a single change. If you have multiple unrelated changes, submit separate pull requests.

---

## What to Contribute

### Bug Reports
Open an issue on GitHub with:
- Steps to reproduce the problem.
- Expected behavior vs actual behavior.
- Your system info: distribution, desktop environment, display server, Python version.
- Any error output from the terminal.

### Feature Requests
Open an issue describing:
- What the feature would do.
- Why it would be useful.
- Any ideas on how it could be implemented.

### Code Contributions
Areas where contributions are welcome:
- Bug fixes
- New annotation tools
- Additional screenshot or recording backends
- Support for more desktop environments
- Performance improvements
- Documentation improvements
- Translations

---

## Testing

Before submitting a pull request, test your changes:
- Run BazzCap and verify the feature or fix works as expected.
- Test on both GNOME and KDE if possible.
- Test on Wayland (the primary target) and X11 if your change affects display or capture.
- Make sure existing features still work (hotkeys, capture, annotations, clipboard, tray).

---

## Project Layout

See the README for a description of the project structure. Key files for common contributions:

- **overlay.py** -- Annotation tools and region selection overlay.
- **capture.py** -- Add or modify screenshot backends.
- **recorder.py** -- Add or modify recording backends.
- **editor.py** -- Post-capture image editor.
- **hotkeys.py** -- Global hotkey registration for different desktop environments.
- **app.py** -- Main window, tray, and application lifecycle.

---

## License

By contributing to BazzCap, you agree that your contributions will be licensed under the MIT License.
