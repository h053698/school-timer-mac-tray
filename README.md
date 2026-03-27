## Build macOS app (.app)

### Prereqs

- `uv` installed
- Xcode Command Line Tools installed
- If you see a license error, run:

```bash
sudo xcodebuild -license
```

### Build

```bash
chmod +x scripts/build-mac.sh
./scripts/build-mac.sh
```

Result:

- `dist/SchoolTimer.app`

