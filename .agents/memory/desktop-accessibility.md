---
name: Desktop accessibility verification
description: Why zoom and keyboard checks must measure layout and viewport visibility.
---

When testing browser zoom, exercise the reduced CSS viewport as well as increased pixel density. Pixel density alone and pinch magnification do not test responsive reflow. Label viewport-based zoom checks as emulation, not native browser-UI zoom.

**Why:** A zoomed desktop can switch to compact navigation. A keyboard-focused link can remain below a fixed overlay's visible bounds even though focus and its CSS outline are both correct.

**How to apply:** Assert that focused controls are within the visible viewport and their scroll containers, rather than relying only on focus state or screenshots. Keep the browser-zoom emulation limitation explicit when reporting verification.
