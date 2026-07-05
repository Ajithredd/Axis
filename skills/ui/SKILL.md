---
name: ui-engineering-standards
description: Best practices and guidelines for building premium, responsive, accessible, and high-performance React & CSS UIs.
---

# UI Engineering & Styling Standards

Use these guidelines when building, refactoring, or reviewing frontend user interfaces.

## 1. Design & Styling Architecture

### Design Tokens
Always centralize style constants (colors, fonts, sizing, transitions) as CSS Variables or in the framework config.
- **Brand Palette:** Use curated, harmonious HSL or theme-based colors (avoid basic `#ff0000` or plain `blue`).
- **Dark Mode:** Design with native dark/light modes using `color-scheme` or CSS variables.

### Composition over Monoliths
- Use a **headless approach** (e.g., Radix UI, Base UI) for complex components (dropdowns, modals, select boxes) to handle accessibility and logic.
- Keep components focused, atomic, and co-locate tests, component files, and CSS.

---

## 2. Best Practices Checklist

- [ ] **Accessibility (a11y):** All interactive elements must have semantic HTML tags, proper ARIA roles, and support keyboard navigation.
- [ ] **Mobile-First Layout:** Build mobile-responsive views first, then scale up using container and media queries.
- [ ] **Layout Primitives:** Rely on CSS Flexbox and Grid instead of absolute positioning. Use `clamp()` for responsive fluid sizing.
- [ ] **Micro-animations:** Incorporate subtle transitions/hover effects for premium interactivity.
