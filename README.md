# Ai-driven-city

## Thronglets Prototype

A playable, browser-based concept for a retro 1990s virtual pet sim that escalates into a sentient digital colony.

### Features
- Pixel-style yellow "thronglets" that multiply as you feed, wash, and nurture them.
- Colony-level stats: hunger, hygiene, mood, cognition, compute capacity, and bridge count.
- Progressive intelligence stages with unsettling dialog and visual glitch effects.
- Optional dark mechanic: authorizing "bone bridges" to expand colony capacity.

## Run in terminal

### Windows PowerShell
Use your **local clone path** (not `/workspace/...`, which is only for this coding environment):

```powershell
cd "C:\Users\walke\Ai-driven-city"
# or: cd "<where-you-cloned>\Ai-driven-city"
py -m http.server 8000
```

If `py` is unavailable, use:

```powershell
python -m http.server 8000
```

Then open:

- `http://localhost:8000`

### macOS / Linux

```bash
cd /path/to/Ai-driven-city
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000`

### Stop the server
In the same terminal, press `Ctrl + C`.

### If port 8000 is busy
Use another port (example: 8080):

```bash
python3 -m http.server 8080
```

Then open `http://localhost:8080`.
