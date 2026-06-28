# Quartermaster — Brand

**Name:** Quartermaster · **Tagline:** *Acquisitions, rationed.*
**What it is:** a compatibility-aware hardware deal-hunter + budget-disciplined, human-approved auction-snipe agent.

## Logo files
| File | Use |
|---|---|
| `quartermaster-key.svg` | **Primary mark.** A key whose bow is a reeded quarter with a star punched through; the bit's teeth ascend left→right (climbing value). One object = coin (quarter) + military (star) + control-of-stores (key). |
| `quartermaster-lockup.svg` | Horizontal lockup — mark + ledger-column rule + slab wordmark + tagline. |
| `quartermaster-mark-mono.svg` | Single-colour, transparent (stamps, watermarks; recolour via the group `fill`). |
| `quartermaster-favicon.svg` | Simplified to the star-punched quarter for small sizes (≤24 px). |
| `quartermaster-social.png` | 1280×640 GitHub social-preview card (lockup on the depot field). |

## Palette
| Token | Hex | Use |
|---|---|---|
| Depot (field) | `#3A4A29` → `#121A0B` | dark background / tile (olive-drab radial) |
| Brass light | `#F1CF73` | metal highlight |
| Brass mid | `#CF9E37` | metal body / accents |
| Brass dark | `#A8761C` | metal shade |
| Engrave | `#714E0D` | reeding / cut lines |
| Parchment | `#F2E9D2` | wordmark on dark |
| Brass tag | `#D9AE55` | tagline / hairlines |

The palette is deliberately **olive-drab + struck brass** — the quartermaster's real material world (depot, crates, brass fittings, ledgers) — not the default military gold-on-navy.

## Typography
- **Wordmark:** slab serif for a ledger/requisition feel — `Zilla Slab` 600, falling back to `Roboto Slab` / `Rockwell` / `Georgia`; tracked +2.
- **Tagline / utility:** `Inter` (→ `system-ui`), small caps, tracked +7.
- The lockup wordmark + tagline are **outlined to vector paths** (Zilla Slab 600 / Inter 500), so they render identically everywhere with no font dependency. Re-outline from the TTFs if the text changes.

## Usage
- Clear space around the mark ≈ the height of the star-bow.
- Don't recolour the brass-on-depot version; for one-colour contexts use `quartermaster-mark-mono.svg`.
- Below ~24 px, switch to `quartermaster-favicon.svg`.

## Domain
Candidate: **quartermaster.bid** (available 2026-06-24). Registration + DNS + hosting are fully API/Terraform-driven on **Scaleway** (`scaleway_domain_registration`).
