# Auto Proposal Wire Generator (Figma Plugin)

Figma plugin that consumes the "Wire JSON" emitted by the auto-proposal pipeline and instantiates the internal wireframe UI kit (e.g. `Section/Hero/Center`) across Desktop/Tablet/Mobile frames with Auto Layout, layout grids, and placeholder fallbacks.

## Features

- Fetch Wire JSON via signed URL (e.g. Cloud Storage) **or** load a local JSON file
- Create page-level frames per page spec with configurable device presets (Desktop/Tablet/Mobile)
- Map `kind/variant` to library components (`Section/<Kind>/<Variant>`). Missing components fall back to dashed placeholder frames with warnings
- Inject placeholder copy into text layers when layer names match placeholder keys (case-insensitive)
- Surface warnings/errors in the plugin UI and Figma notifications, persisting the last-used URL in `clientStorage`
- Attach relaunch data so frames can be regenerated from the plugin quick actions menu

## Development Workflow

```bash
cd figma-plugin
npm install
npm run build      # outputs dist/main.js + manifest.json
```

Figma expects the published bundle to include `manifest.json` and `main.js`. After running `npm run build`, import the `figma-plugin/dist` directory in Figma via **Resources → Plugins → Development → Import plugin from manifest…**.

Use `npm run build:watch` during development to rebuild automatically on file changes.

## UI Kit expectations

- Components must be named `Section/<Kind>/<Variant>` (e.g. `Section/Hero/Center`) and be available in the current file or imported library.
- Text layers inside the component instance should be named with alphanumeric keys matching `placeholders` in the JSON (e.g. `headline`, `cta`). Keys are compared case-insensitively and ignore non-alphanumeric characters.
- Frames are configured with layout grids and spacing tokens defined in the plugin; tweak `FRAME_PRESETS` in `src/main.ts` to adjust sizing/padding rules.

## JSON schema snapshot

```json
{
  "project": { "id": "OPP-2025-001", "title": "dot.homes 新LP" },
  "frames": ["Desktop", "Tablet", "Mobile"],
  "pages": [
    {
      "page_id": "top",
      "sections": [
        { "kind": "Hero", "variant": "Center", "placeholders": { "headline": "..." } }
      ],
      "notes": ["コピー未確定→要原稿"]
    }
  ]
}
```

## Missing component fallback

If the library lacks the requested `kind/variant`, the plugin drops a dashed placeholder frame and records a warning in the UI. These warnings should be triaged after generation to extend the UI kit or adjust the dictionary mapping.
