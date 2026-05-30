# PO Generator — SPEC.md

## 1. Concept & Vision

Aplikasi web untuk generate Surat Pemesanan Barang (PO) dalam format PDF sesuai kop Surat PT SAA. User mengisi form data PO, lihat preview langsung, lalu download PDF. Desain profesional dengan nuansa korporat — clean, trustworthy, efisien. Tampilan ala "internal tool" yang dipakai daily tanpa feels "side project".

## 2. Design Language

**Aesthetic:** Corporate professional — flat design, confident typography, structured whitespace. Mirrors enterprise document tooling (SAP, Oracle EBS aesthetic but modernized).

**Color Palette:**
- Primary: `#1a3a5c` (deep navy)
- Secondary: `#2d5a87` (medium blue)
- Accent: `#e8911a` (warm orange — action buttons, highlights)
- Background: `#f4f6f9` (light grey)
- Surface: `#ffffff` (white cards)
- Text primary: `#1a1a2e`
- Text secondary: `#64748b`
- Border: `#e2e8f0`
- Error: `#dc2626`
- Success: `#16a34a`

**Typography:**
- Headings: `'Inter', sans-serif` — weight 600/700
- Body: `'Inter', sans-serif` — weight 400/500
- Monospace (PO number): `'JetBrains Mono', monospace`

**Spatial System:**
- Base unit: 8px
- Card padding: 24px
- Section gap: 32px
- Form field gap: 16px

**Motion:**
- Form interactions: subtle hover/focus transitions (150ms ease)
- Button press: scale(0.98) on active
- Preview panel: smooth fade-in on load (300ms)
- No gratuitous animation — this is a work tool

**Visual Assets:**
- Icons: Lucide (via CDN) — consistent stroke icons
- No decorative images — content-focused

## 3. Layout & Structure

**Single Page Layout:**

```
┌─────────────────────────────────────────────────────────┐
│ HEADER: Logo SAA + "PO Generator" + Timestamp           │
├────────────────────────┬────────────────────────────────┤
│ FORM PANEL (left 45%)  │  PREVIEW PANEL (right 55%)     │
│                        │                                 │
│  Section: Distributor  │   Live HTML preview of the     │
│  - Kode/Nama Dist      │   actual PO document as it     │
│  - Wilayah             │   will appear in PDF           │
│  - Alamat Tujuan       │                                │
│                        │   [Preview scales to fit]      │
│  Section: Barang       │                                │
│  - Merk                │   Scroll dalam iframe,          │
│  - Jenis Semen         │   real-time update              │
│  - Kemasan & Jumlah    │                                │
│                        │   [Download PDF button]        │
│  Section: Pengiriman   │                                │
│  - Metode              │                                │
│  - Pelang harbor Tujuan│                                │
│  - Permintaan Tgl Tiba │                                │
│                        │                                │
│  Section: Kapal        │                                │
│  - Nama Kapal          │                                │
│  - Perusahaan          │                                │
│  - Tgl Muat            │                                │
│  - Pelang harbor Muat   │                                │
│                        │                                │
│  Section: Tambahan     │                                │
│  - Info Tambahan       │                                │
│                        │                                │
│  [Generate PDF]        │                                │
└────────────────────────┴────────────────────────────────┘
```

**Responsive:** On mobile (< 768px), stack vertically (form on top, preview below). Form sections collapse into accordion-style groups.

**Pacing:** Dense but breathable. Form sections separated by subtle dividers. Preview panel is visually "elevated" (white card on grey bg) to feel like the main output.

## 4. Features & Interactions

### Form Fields (all required unless noted)

**Distributor:**
- Kode Distributor (text, 4-digit)
- Nama Distributor (text)
- Wilayah (text)
- Metode Pembayaran (select: KREDIT TUNAI / TRANSFER)
- Customer Code (text, optional)

**Barang:**
- Merk (select: Tiga Roda / Rajawali / Holcim / Semen Tonasa)
- Jenis Semen (multi-select checkboxes: PCC / PPC / WC OPC / Type II / Type V / TR 30)
- Kemasan & Jumlah (3 rows: 50kg, 40kg, 1 ton — each has qty in ton and zak)
- Info Tambahan (textarea, optional)

**Pengiriman:**
- Metode (select: LOCO / FAS / CIF / FRANCO / FOB)
- Alamat Tujuan (textarea)
- Pelang harbor Tujuan (text)
- Pelang harbor Muat (text)

**Kapal:**
- Nama Kapal (text)
- Nama Perusahaan Pelayaran (text)
- Tanggal Muat (date)
- Tanggal Tiba (date, optional)

**PO Details:**
- Nomor PO (auto-generated: format `XXXX / SAA-OP / MM / YYYY` — user can override)
- Tanggal PO (date, defaults to today)
- Disetujui Oleh (text, defaults to "Manager")
- GM Opr (text, defaults to "Henry Gunawan")

### Interactions

- **Live Preview:** Every field change updates the preview within 200ms (debounced)
- **Field validation:** Red border + inline error message on blur if required field empty
- **Generate PDF:** Click button → html2pdf.js generates PDF → auto-download
- **Reset Form:** Clear all fields to default values
- **Copy PO Number:** Click on PO number in preview to copy to clipboard

### Error Handling

- Empty required fields: border turns red, tooltip appears
- PDF generation failure: show toast notification with error message
- Invalid date combinations (tgl tiba before tgl muat): warning but allow

## 5. Component Inventory

### Header
- Logo SAA (text-based: "PT SAA" in styled font)
- Title: "PO Generator"
- Timestamp: "Generated: DD/MM/YYYY HH:mm"
- States: static

### Form Section Card
- Section title (e.g., "Data Distributor")
- 2-4 form fields inside
- Collapsible on mobile (accordion)
- States: default, collapsed (mobile)

### Text Input
- Label above
- Input field with placeholder
- Helper text below (optional)
- States: default, focus (blue border), error (red border + message), disabled

### Select Dropdown
- Same as text input but with chevron icon
- States: default, open, focus, error, disabled

### Multi-Select Checkbox Group (Jenis Semen)
- Label "Jenis Semen"
- Inline checkboxes: PCC | PPC | WC OPC | Type II | Type V | TR 30
- States: checked/unchecked per option

### Kemasan Row (3x)
- Label: "50 Kg" / "40 Kg" / "1 Ton"
- Two inputs: "Ton" and "Zak"
- Inline layout: [Label] [Ton input] [Zak input]

### Textarea
- For Alamat Tujuan, Info Tambahan
- Auto-grow height up to max
- States: default, focus, error

### Primary Button
- "Generate PDF" — orange background (#e8911a), white text
- States: default, hover (darken 10%), active (scale 0.98), loading (spinner + "Generating..."), disabled

### Secondary Button
- "Reset Form" — outlined, grey
- States: default, hover, active

### Preview Panel
- White card with shadow
- Contains rendered HTML PO document at 70% scale
- Scrollable if content overflows
- "Download PDF" button pinned at bottom of panel

### Toast Notification
- Appears top-right
- Types: success (green), error (red), warning (yellow)
- Auto-dismiss after 4s
- States: visible, dismissing (fade out)

## 6. Technical Approach

**Stack:** Vanilla HTML + CSS + JS (no framework). Single `index.html` file for simplicity and Vercel deployment.

**PDF Generation:** `html2pdf.js` via CDN — converts the preview HTML to PDF. The preview HTML uses A4 page sizing with exact pixel-to-mm mapping to match the physical PO layout.

**Key Libraries (CDN):**
- html2pdf.js v0.10.1
- Google Fonts: Inter, JetBrains Mono

**PO Template:** 
The preview renders using a `<div>` with CSS that maps to physical page dimensions:
- A4: 210mm × 297mm
- Page padding: 20mm all sides
- Font stack matches the PDF template
- The template is embedded directly in `index.html` as a hidden `<div>` that gets cloned into the preview

**Vercel Deployment:**
- Static site — no server needed
- `vercel.json` with clean URLs
- Single `index.html` entry point

**PDF Output Spec:**
- Page size: A4 portrait
- Font: Helvetica (pdfkit default, or system sans-serif via html2pdf)
- Content fits single page (PO is one-page document)
- Filename: `PO_[NOMOR]_[TANGGAL].pdf` — e.g., `PO_0922_SAA-OP_XI_2025.pdf`