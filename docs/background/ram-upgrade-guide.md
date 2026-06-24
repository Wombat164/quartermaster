# RAM Upgrade Guide — ASUS ROG Strix G15 G513QR (Ryzen 9 5900HX, RTX 3070)

Your machine: **2 SO-DIMM slots, DDR4-3200 (PC4-25600), 64 GB ceiling.** Both slots are currently filled with 2× 8 GB, so **any upgrade means replacing both sticks** — there is no free slot to add to.

> ✅ **64 GB verified compatible (2026-06-24).** Your laptop's firmware reports a "32 GB max," but that is ASUS's conservative 2021 spec label hardcoded into SMBIOS — a deprecated, OEM-supplied value, *not* a hardware limit. The Ryzen 9 5900HX officially supports 64 GB; ASUS shipped this exact chassis with 64 GB from the factory; and Crucial, Kingston, A-Tech & Adamanta all certify 64 GB kits for the G513QR. Confirmed by independent adversarial fact-check.
>
> ⚠️ **Critical: buy native 1.2 V JEDEC, NOT a 1.35 V "XMP" kit.** On this AMD platform a 1.35 V/XMP-only SO-DIMM downclocks to ~2666 MHz. The kits below are all native 1.2 V JEDEC and run at full 3200. Avoid Crucial **Ballistix** / anything labeled "XMP" or "1.35 V".
>
> 🔧 **BIOS:** yours is v331 (2023); latest is **v335 (2025-12-24)** via ASUS EZ Flash. Not required for 32 GB modules, but recommended hygiene before/after the swap.

## (A) Buying Guide

### Spec checklist — every box must match
| Spec | Required value |
|---|---|
| Memory type | **DDR4** (NOT DDR4L, NOT DDR5) |
| Form factor | **SO-DIMM, 260-pin** (laptop) |
| Speed | **3200 MT/s** (PC4-25600) |
| Voltage | **1.2 V** |
| CAS latency | **CL22** (Crucial) or **CL20** (Kingston Fury) — both fine |
| ECC / register | **Non-ECC, unbuffered** |

- **Buy a matched dual-channel kit** (one box, two sticks). The 5900HX runs dual-channel; two identical sticks guarantee it. Don't mix old 8 GB sticks with new.
- **Over-spec sticks just downclock.** A 3600 kit runs at 3200 here — no benefit, so buy 3200. CL20 vs CL22 is negligible.

### 64 GB (2× 32 GB) — the max
- **Primary: Crucial CT2K32G4SFD832A** — 2×32 GB, DDR4-3200, CL22, 1.2 V, 260-pin, non-ECC. Exactly what Crucial's tool certifies for the G513QR. **~€110–150**.
- **Alt: Kingston FURY Impact KF432S20IBK2/64** — 2×32 GB, CL20. **~€120–160**.

### 32 GB (2× 16 GB) — value sweet spot
- **Primary: Crucial CT2K16G4SFRA32A** — 2×16 GB, DDR4-3200, CL22, 1.2 V, 260-pin, non-ECC. **~€45–70**.
- **Alt: Kingston FURY Impact KF432S20IBK2/32** — 2×16 GB, CL20. **~€50–75**.

> For gaming + RTX 3070, **32 GB is the practical sweet spot**. Go 64 GB only for VMs, large datasets, heavy content creation, or many memory-hungry apps at once. Given your ~42 GB commit charge, **64 GB is justified** for your actual workload.

### Sources
- Crucial compatibility tool: https://www.crucial.com/compatible-upgrade-for/asus/rog-strix-g513
- Crucial 64 GB kit: https://www.crucial.com/memory/ddr4/ct2k32g4sfd832a
- Crucial 32 GB kit: https://www.crucial.com/memory/ddr4/ct2k16g4sfra32a
- Belgium listing (Crucial 64 GB): https://www.amazon.com.be/-/en/Crucial-CT2K32G4SFD832A-3200MHz-2933MHz-2666MHz/dp/B07ZLCVKPV

---

## (B) Installation Guide

### Tools & prep
- **#0 (PH0) Phillips screwdriver** (magnetized if possible).
- **Plastic pry tool / guitar pick / old card** — never metal to pry.
- Magnetic tray / labeled cups for screws.
- **Anti-static**: hard non-carpet surface, touch bare grounded metal (or wrist strap) before handling RAM, hold sticks by the **edges** — never contacts/chips.

### Step 1 — Pre-work
1. **Back up** anything critical.
2. **Fully shut down** (Start → Power → Shut down). For a truly cold state, hold **Shift** while clicking Shut down.
3. **Unplug AC** and any USB-C power.
4. ASUS recommends running the **battery to ≤25%** before opening.
5. **Hold the power button ~10–15 s** to discharge residual power.

### Step 2 — Remove the bottom panel
1. Lid closed, laptop **face-down on a soft cloth**.
2. **Remove the 11 Phillips screws**. Screw lengths can differ by position — keep them organized.
3. **One screw is captive** — it loosens but won't fully come out. Don't force it.
4. No glue; the panel is held by **clips**. Start at a corner, insert the pry tool at a shallow angle, and work around releasing clips slowly.
5. **CRITICAL:** the panel is tethered by **RGB LED ribbon cable(s)**. Lift only a few cm, then **disconnect the LED ribbon** before fully removing the panel.

### Step 3 — Disconnect the battery (recommended)
- Unplug the **battery connector** from the motherboard so the slots are unpowered. Reconnect last.

### Step 4 — Swap the RAM
1. Find the **two SO-DIMM slots** near center, beside the heatpipes, **under a silver heat-shield/sticker**.
2. **Peel the shield back** (don't fully remove) to expose modules.
3. Each old stick: **push the two side clips outward** → stick pops to ~30° → **pull straight out** by the edges.
4. New stick: align the **notch** with the slot key, insert at **~30°**, then **press down flat until both clips snap**. Repeat for the second. Confirm both fully seated and level.
5. Re-lay the heat-shield/sticker.

### Step 5 — Reassemble
1. **Reconnect the LED ribbon** (and battery connector last).
2. Align panel, **press edges until clips click**.
3. **Reinstall all 11 screws** (right screw, right hole, don't over-tighten).

### Step 6 — First boot
- Reconnect AC, power on. **First POST may take 20–40 s longer** with a black screen while memory retrains — normal. If no boot, **reseat the sticks** (#1 cause is a not-fully-clicked stick).

### Step 7 — Verify
1. **BIOS:** tap **F2**/Del at the ASUS logo → **Total Memory = 65536 MB / 64 GB**.
2. **Windows — Task Manager → Performance → Memory:** capacity **64.0 GB**, **Speed 3200 MHz**, **Slots used 2 of 2**.
3. **PowerShell** (read-only):
   ```powershell
   Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator, Capacity, Speed, Manufacturer, PartNumber
   ```
   Each `Capacity` = 34359738368 (32 GB), `Speed` = 3200.

### Warranty note
ASUS treats **memory/storage as user-upgradeable** on ROG Strix laptops (official upgrade guide + user-accessible memory). In the **EU/Belgium**, opening the laptop to upgrade RAM **cannot void your statutory legal guarantee**; "warranty void" stickers aren't enforceable against EU consumer rights for user-serviceable parts. But **damage you cause during the swap isn't covered** — photograph seals first and check your ASUS Belgium terms.

### Sources
- ASUS official RAM/SSD upgrade guide: https://rog.asus.com/articles/guides/how-to-upgrade-the-ram-and-ssd-of-your-rog-strix-laptop/
- LaptopMedia teardown: https://laptopmedia.com/highlights/inside-asus-rog-strix-g15-g513-disassembly-and-upgrade-options/
- ASUS G513 service guide (PDF): https://documents.cdn.ifixit.com/oKCDWCgQLxt13uAE.pdf
- iFixit device page: https://www.ifixit.com/Device/ASUS_ROG_Strix_G15_G513

---
**Bottom line:** For your workload (~42 GB commit on 16 GB), the **Crucial CT2K32G4SFD832A 2×32 GB (64 GB)** is the right target. Install is ~15 min: 11 screws, mind the LED ribbon, swap both sticks at 30°, then verify 64 GB @ 3200 MHz.

---

## (C) Live price comparison → Belgium (June 2026)
> ⚠️ DDR4 **surged hard in 2026** (this kit peaked ~$666 in Jan 2026). The €45–150 estimates earlier in this doc are PRE-surge — use the verified current prices below.

**64 GB — Crucial CT2K32G4SFD832A**
| Price | Where | Notes |
|---|---|---|
| ~€452–459 | Geizhals DE/EU floor | unnamed small DE shop + shipping |
| **€510.99** ✅ | bol.com (in stock, ships BE) | cheapest fully-verified buy |

**32 GB — Crucial CT2K16G4SFRA32A**
| Price | Where | Notes |
|---|---|---|
| ~€229 | Geizhals DE floor | + shipping |
| **€239** ✅ | Megekko.nl (in stock, next-day) | cheapest verified named buy |
| €256 | bol.com | easy BE delivery |

Kingston FURY is no cheaper (64 GB Kingston ~€927 — avoid). Ordering DE/FR saves only ~€10–25 vs NL — not worth the hassle.

## (D) Cheaper route — buy used / salvage
Used meaningfully undercuts surged-new. Verified-safe only if it's **1.2 V JEDEC DDR4-3200 SO-DIMM, 260-pin, non-ECC, non-XMP**.

| Path | 32 GB (2×16) | 64 GB (2×32) | Where |
|---|---|---|---|
| **Used kits** (best value) | **€90–130** | €160–300 | 2dehands.be / 2ememain.be (BE), Marktplaats.nl (ships BE ~€5), Kleinanzeigen.de (floor ~€65), Leboncoin.fr |
| **eBay "tested pulls"** (buyer protection) | €60–90 + ship | €150–180 + ship | befr.ebay.be, ebay.de — filter Used + "tested" + seller ≥98%, prefer EU sellers (no customs) |
| **Broken-laptop harvest** | rarely beats buying a kit | rarely worth it | only if donor is cheap AND has *confirmed socketed* 2×16/2×32 SO-DIMM, or you resell the other parts |

**Used safety checklist:** reject anything 1.35 V / XMP-only / DDR4L / LPDDR4 / ECC / desktop DIMM (288-pin); buy a **matched pair** (same brand + part# + rank, 1Rx8 vs 2Rx8); demand a **label or CPU-Z photo before paying**; prefer buyer-protected platforms (eBay Money-Back, 2dehands "veilig betalen"); run **MemTest86 3–4 passes** after install. Watch for relabeled fakes — stick to Samsung / SK Hynix / Micron-Crucial / Kingston.

**Verdict:** Used 32 GB ≈ €90–130 (vs €239 new) and used 64 GB ≈ €160–300 (vs €480 new) — both ~40–60% savings. Buy a used **matched kit** (not random singles) via 2dehands/Marktplaats or eBay tested-pulls; **skip the broken-laptop harvest** unless you stumble on a genuinely cheap dead unit with confirmed socketed RAM of the right capacity. To verify a donor laptop's RAM is socketed (not soldered), run its exact model through the Crucial compatibility tool — if it shows SO-DIMM upgrades, it's harvestable.
