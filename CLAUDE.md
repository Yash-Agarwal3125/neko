# CLAUDE.md

Neko — a Go desktop app where a cat chases the mouse cursor. Re-implementation of the classic 1980s Neko using [Ebitengine](https://ebitengine.org). Single-package (`package main`) codebase: `main.go`, `main_test.go`, `gensheet_test.go`.

## Tech stack

- **Go 1.26**, single module (`neko`)
- **Ebitengine v2** — game loop via `Update`/`Draw`/`Layout` on the `neko` struct
- **Filo** (`github.com/crgimenes/filo`) for Lisp-like config files
- Sprites: 8×4 grid of 32×32 tiles in oneko.js layout (`assets/neko.png`)
- Audio: embedded WAV files decoded via Ebitengine's audio package

## Commands

```bash
# Run (CGO_ENABLED=1 needed on Linux/macOS, not Windows)
CGO_ENABLED=1 go run main.go

# Build for Windows (no CGO needed)
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o neko.exe

# Cross-platform builds
make all    # Windows amd64 + macOS arm64 → dist/
make clean

# Tests
go test ./...

# Regenerate sprite sheet from individual PNGs in sprites/
GENSHEET=1 go test -run TestGenerateSpriteSheet
```

Linux builds require system libs: `libasound2-dev libgl1-mesa-dev libxcursor-dev libxi-dev libxinerama-dev libxrandr-dev libxxf86vm-dev`.

## Architecture

- **State machine**: `m.state` tracks idle phases (awake → scratch → wash → yawn → sleep). `stateMoving` (0) means chasing cursor.
- **8-direction movement** with angular hysteresis (`directionHysteresis = 3.0°`) to prevent jitter at sector boundaries.
- **Config precedence**: defaults → Filo config file (`neko_init.filo` or `~/.config/neko/init.filo`) → CLI flags (`-speed`, `-scale`, `-quiet`, `-mousepassthrough`, `-spritesheet`).
- **Sprite sheet**: `spriteSheetLayout` map is the single source of truth for tile positions. `gensheet_test.go` composes individual `sprites/*.png` into `assets/neko.png`.
- **Embed**: only `assets/neko.png` and `assets/*.wav` are embedded in the binary. Individual sprites in `sprites/` are build-time inputs only.
- **Window**: always 32×32 internal, scaled via `Scale` config. Transparent, undecorated, floating, skips taskbar. Left-click toggles pause.
- **Multi-monitor**: `syncMonitor()` rebases cat position when the window crosses monitors.

## CI

GitHub Actions on `master`: runs `go test ./...` on Ubuntu (with system deps), cross-builds for windows/{386,amd64,arm64} and darwin/{amd64,arm64}.
