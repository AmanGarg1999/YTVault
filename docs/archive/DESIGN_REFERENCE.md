# 🎨 Visual Design Reference Guide

A quick visual reference for the professional UI/UX design system.

---

## 📊 Color Palette

### Primary Color (Cyan Blue)
```
Light Accent       #f0f9ff  ░░░░░░░░░░
Light Accent       #e0f2fe  ░░░░░░░░░░
Primary (Main)     #0ea5e9  ███████████ ← Use for buttons, links, highlights
Hover              #0284c7  ███████████
Active             #0369a1  ███████████
Dark               #075985  ███████████
```

### Semantic Colors
```
Success            #10b981  ██ (Use:  Completed, accepted, ready)
Warning            #f59e0b  ██ (Use: ️ Review needed, caution)
Error              #ef4444  ██ (Use:  Failed, rejected, error)
Info               #3b82f6  ██ (Use: ℹ️ Neutral information)
```

### Neutral (Dark Mode)
```
White              #f9fafb  (text on dark backgrounds)
Very Light         #f3f4f6  (secondary text)
Light              #e5e7eb  (dividers, borders)
Medium Light       #d1d5db  (inactive elements)
Medium             #9ca3af  (placeholder text)
Medium Dark        #6b7280  (muted text)
Dark               #4b5563  (input backgrounds)
Very Dark          #2d3748  (sidebar, surfaces)
Nearly Black       #1f2937  (darker surfaces)
Black              #111827  (darkest backgrounds)
```

---

## 🔤 Typography System

### Font Families
- **Display & Text**: `Inter` (-apple-system fallback)
- **Code/Technical**: `JetBrains Mono`

### Size Scale
```
Heading 1 (H1)     34px (2.125rem)  Weight: 700  ← Page titles
Heading 2 (H2)     30px (1.875rem)  Weight: 700  ← Section titles
Heading 3 (H3)     24px (1.5rem)    Weight: 600
Heading 4 (H4)     18px (1.125rem)  Weight: 600
Body               16px (1rem)      Weight: 400  ← Default text
Body Small         14px (0.875rem)  Weight: 400
Label              12px (0.75rem)   Weight: 600  Uppercase, 0.05em spacing
```

### Line Heights
```
Headlines:  1.2–1.33 (tighter)
Body:       1.6 (comfortable reading)
Labels:     1.5 (compact)
```

### Letter Spacing
```
Headlines:  -0.01em to -0.02em (tightened)
Body:       normal (default)
Labels:     0.05em to 0.1em (expanded for emphasis)
```

---

## 🧩 Component Guidelines

### Metric Cards
```
┌─────────────────────┐
│ 📊 LABEL            │
│                     │
│    1,425            │  ← Large gradient text
│    +12%             │  ← Optional delta (smaller)
│                     │
└─────────────────────┘
```

### Status Badges
```
 Success   [green badge]    #10b981
️ Warning   [amber badge]    #f59e0b
 Error     [red badge]      #ef4444
ℹ️ Info      [blue badge]     #3b82f6
```

### Information Cards
```
┌─────────────────────────────────────────┐
│  Success Title                        │  ← Green left border
│                                         │
│ Optional description text here.         │
│ Supports multiple lines.                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ ️ Warning Title                        │  ← Amber left border
│ Text here...                            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Error Title                          │  ← Red left border
│ Text here...                            │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ ℹ️ Info Title                           │  ← Blue left border
│ Text here...                            │
└─────────────────────────────────────────┘
```

### Progress Steps
```
 Discovery          100% ████████████████████
 Triage             100% ████████████████████
🔄 Transcript Fetch    45% ████████░░░░░░░░░░░░
⭕ Refinement            0% ░░░░░░░░░░░░░░░░░░░░
⭕ Indexing             0% ░░░░░░░░░░░░░░░░░░░░
```

---

## 🎯 Component Usage Matrix

| Need | Component | Color | Icon |
|------|-----------|-------|------|
| Page Title | `page_header()` | Primary | User choice |
| Section Title | `section_header()` | Neutral | User choice |
| Key Metrics | `metric_grid()` | Primary gradient | 📊 |
| Success Message | `success_card()` | Success |  |
| Warning Message | `warning_card()` | Warning | ️ |
| Error Message | `error_card()` | Error |  |
| Info Message | `info_card()` | Info | ℹ️ |
| Status Indicator | `status_badge()` | Semantic | User choice |
| Pipeline Step | `progress_step()` | Primary | Various |
| Loading State | `loading_spinner()` | Primary | 🔄 |

---

## 📐 Spacing & Sizing

### Standard Measurements
```
Extra Small    0.25rem (4px)
Small          0.5rem  (8px)   ← Base unit
Medium         1rem    (16px)  ← Double base
Large          1.5rem  (24px)  ← Triple base
Extra Large    2rem    (32px)  ← Quad base
```

### Component Padding
```
Buttons:           0.75rem vertical × 1.5rem horizontal
Cards:             1.5rem all sides
Form Sections:     1rem all sides
Metric Cards:      1.5rem all sides
Expandable Items:  1rem vertical × 1.25rem horizontal
```

### Component Margins
```
Between sections:  2rem
Between cards:     1rem
Between list items: 0.25rem
Top of page:       2rem (header)
```

---

## 🎭 Component States

### Button States
```
Default:     Background #0ea5e9, text white
Hover:       Background #0284c7, slight lift (-2px), shadow
Active:      Background #0369a1, no lift
Disabled:    Background #6b7280, opacity 0.5
```

### Input States
```
Default:     Border #0ea5e9 with 0.2 opacity
Focus:       Border #0ea5e9, shadow: 0 0 0 3px rgba(14, 165, 233, 0.1)
Error:       Border #ef4444
Disabled:    Background #2d3748, opacity 0.5
```

### Card States
```
Default:     Border 1px solid rgba(14, 165, 233, 0.2)
Hover:       Border opacity increased to 0.4, slight lift (-2px)
Active:      Background slightly highlighted
```

---

## 📱 Responsive Breakpoints

```
Mobile          < 600px   (1 column layouts)
Tablet          600-1024px (2 column layouts)
Desktop         1024-1920px (3+ column layouts)
Wide Desktop    > 1920px   (4+ column layouts)
```

---

## Accessibility Standards

### Color Contrast Ratios
```
Text on Background:        4.5:1 (WCAG AA standard)
Large Text (18pt+):        3:1 (WCAG AA standard)
All interactive elements:  Meet above standards
```

### Keyboard Navigation
```
Tab:          Cycle through interactive elements
Shift+Tab:    Reverse cycle
Enter:        Activate buttons
Space:        Toggle checkboxes
Escape:       Close modals/expanders
Arrow Keys:   Selectors, spinners
```

### Focus Indicators
```
Outline:      2px solid #0ea5e9
Offset:       2px from element
Always visible (never hidden)
```

---

## 🎨 Emoji Usage Guide

| Emoji | Context | Examples |
|-------|---------|----------|
| 🧠 | Branding | App name, main identity |
| 📊 | Metrics | Dashboards, analytics, KPIs |
| 📋 | Lists | Queues, pending items, forms |
| 🔍 | Search | Queries, lookups, filtering |
|  | Success | Completed, accepted, ready |
| ️ | Warning | Caution, review, attention |
|  | Error | Failed, rejected, error |
| 🔄 | Loading | Processing, in-progress, refresh |
| 📈 | Progress | Growth, improvement, trending |
| 🎯 | Action | CTA buttons, focus, target |
| 📌 | Pin/Note | Important, highlights, pins |
| 💡 | Idea | Tips, insights, suggestions |
| 🚀 | Launch | Start, deploy, go live |
| 🗑️ | Delete | Remove, delete, clear |
| 📁 | Folder | Directory, category, group |

---

## 🎯 Do's and Don'ts

### DO
 Use components from library
 Follow color palette
 Use semantic colors correctly
 Maintain consistent spacing
 Test keyboard navigation
 Verify color contrast (4.5:1)
 Use proper text hierarchy
 Provide clear focus states

### DON'T
 Create custom inline styles
 Mix color systems
 Use color alone for meaning
 Nest too many levels
 Ignore accessibility standards
 Use non-semantic HTML
 Hide focus indicators
 Create responsive problems with fixed widths

---

## 📚 Quick Reference Links

| Resource | Purpose |
|----------|---------|
| **Design System** | `docs/UI_UX_DESIGN_SYSTEM.md` |
| **Migration Guide** | `docs/UI_MIGRATION_GUIDE.md` |
| **Component Library** | `src/ui/components/ui_helpers.py` |
| **Dashboard Example** | `src/ui/pages/dashboard.py` |
| **Quick Start** | `UI_QUICKSTART.md` |

---

**Design System Version**: 1.0  
**Framework**: ui-ux-pro-max-skill  
**Status**: Production Ready 
