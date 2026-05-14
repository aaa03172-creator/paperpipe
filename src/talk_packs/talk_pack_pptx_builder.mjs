import fs from "node:fs/promises";
import path from "node:path";

const { Presentation, PresentationFile, drawSlideToCtx } = await import("@oai/artifact-tool");
const { Canvas } = await import("skia-canvas");

const WIDTH = 1280;
const HEIGHT = 720;
const THEMES = {
  paperpipe_baseline: {
    paper: "#F6F2E9",
    ink: "#182126",
    graphite: "#42535F",
    muted: "#6B7A84",
    panel: "#FFFFFF",
    panelAlt: "#F0E8DA",
    accent: "#BC6C25",
    accentDark: "#8F4D12",
    titleFace: "Poppins",
    bodyFace: "Lato",
    monoFace: "Aptos",
    panelLine: "#D9CFBE",
    altPanelLine: "#D7C8AF",
    rule: "#D8CCB8",
  },
  paperpipe_editorial: {
    paper: "#F4F1EA",
    ink: "#121B24",
    graphite: "#334854",
    muted: "#677A87",
    panel: "#FBFAF7",
    panelAlt: "#E7EEF3",
    accent: "#8F3A34",
    accentDark: "#672620",
    titleFace: "Caladea",
    bodyFace: "Lato",
    monoFace: "Aptos",
    panelLine: "#CFD9E1",
    altPanelLine: "#C3D1DB",
    rule: "#D4C7BC",
  },
};
const TEMPLATE_VARIANTS = {
  default: {
    showSectionEyebrow: true,
    footerMode: "raw_owner",
  },
  audience_clean: {
    showSectionEyebrow: false,
    footerMode: "audience_facing",
  },
};

const [inputPath, outputPath, previewDir] = process.argv.slice(2);
if (!inputPath || !outputPath) {
  throw new Error("Usage: node talk_pack_pptx_builder.mjs <input.json> <output.pptx> [preview_dir]");
}

function normalizeLines(items, { prefix = "" } = {}) {
  return (items || []).map((item) => `${prefix}${String(item ?? "").trim()}`).filter(Boolean).join("\n");
}

function normalizeEvidenceRefs(items, { prefix = "" } = {}) {
  return (items || [])
    .map((item) => {
      if (!item) return "";
      if (typeof item === "string") return `${prefix}${item.trim()}`;
      return `${prefix}${JSON.stringify(item)}`;
    })
    .filter(Boolean)
    .join("\n");
}

function addText(
  slide,
  text,
  x,
  y,
  width,
  height,
  {
    size = 18,
    color = THEMES.paperpipe_baseline.ink,
    bold = false,
    face = THEMES.paperpipe_baseline.bodyFace,
    align = "left",
    fill = THEMES.paperpipe_baseline.panel,
    lineColor = "#00000000",
    lineWidth = 0,
  } = {},
) {
  const box = slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width, height },
    fill,
    line: { color: lineColor, width: lineWidth },
  });
  box.text = text;
  box.text.fontSize = size;
  box.text.color = color;
  box.text.bold = bold;
  box.text.typeface = face;
  box.text.alignment = align;
  box.text.verticalAlignment = "top";
  box.text.insets = { left: 0, right: 0, top: 0, bottom: 0 };
  return box;
}

function addRule(slide, x, y, width, height, color) {
  slide.shapes.add({
    geometry: "rect",
    position: { left: x, top: y, width, height },
    fill: color,
    line: { color: color, width: 0 },
  });
}

function addPanel(slide, x, y, width, height, fill = PANEL, lineColor = "#D6CCBB") {
  slide.shapes.add({
    geometry: "roundRect",
    position: { left: x, top: y, width, height },
    fill,
    line: { color: lineColor, width: 1 },
  });
}

function humanizeSpeakerPriority(priority) {
  if (!priority) return null;
  if (priority === "must_say") return "Must say";
  if (priority === "nice_to_say") return "Nice to say";
  if (priority === "skip_if_short_on_time") return "Skip if short on time";
  return String(priority);
}

function humanizeTimeBudget(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  if (seconds < 60) return `${seconds} sec`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  if (remainder === 0) return `${minutes} min`;
  return `${minutes}m ${remainder}s`;
}

function humanizeTokenizedText(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const text = raw.replace(/[_-]+/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function footerTextForDeck(deck) {
  if (deck.templateVariant.footerMode === "audience_facing") {
    return `${humanizeTokenizedText(deck.talk_mode)} • ${humanizeTokenizedText(deck.audience_profile)} • ${deck.duration_minutes} min`;
  }
  return `${deck.paper_slug} • ${deck.audience_profile} • ${deck.duration_minutes} min`;
}

function addManifestBadges(slide, slideData, hasKeyNumbers) {
  const badges = [];
  if (slideData.slide_kind === "backup") {
    badges.push({ label: "Backup", fill: "#E6D3B4", color: slideData.theme.accentDark, width: 112 });
  }
  if (badges.length === 0) {
    return;
  }

  let left = hasKeyNumbers ? 64 : 860;
  if (!hasKeyNumbers) {
    left = 64 + 860 - badges.reduce((sum, badge, idx) => sum + badge.width + (idx > 0 ? 10 : 0), 0);
  }
  for (const badge of badges) {
    addPanel(slide, left, 188, badge.width, 32, badge.fill, "#00000000");
    addText(slide, badge.label, left + 14, 196, badge.width - 28, 16, {
      size: 12,
      color: badge.color,
      bold: true,
      face: slideData.theme.monoFace,
      align: "center",
      fill: "#00000000",
    });
    left += badge.width + 10;
  }
}

function addVisualPanel(slide, slideData) {
  const visuals = Array.isArray(slideData.visual_assets)
    ? slideData.visual_assets.filter((item) => item && item.data_url)
    : [];
  const visualLabels = Array.isArray(slideData.visual_labels)
    ? slideData.visual_labels.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  const hasKeyNumbers = Array.isArray(slideData.key_numbers)
    ? slideData.key_numbers.filter(Boolean).length > 0
    : false;
  if (visuals.length === 0) {
    return false;
  }
  const panel = { left: 660, top: 92, width: 556, height: 544 };
  addPanel(
    slide,
    panel.left,
    panel.top,
    panel.width,
    panel.height,
    slideData.theme.panelAlt,
    slideData.theme.altPanelLine,
  );
  addText(slide, "Visual context", panel.left + 24, panel.top + 24, 220, 24, {
    size: 14,
    color: slideData.theme.accentDark,
    bold: true,
    face: slideData.theme.monoFace,
    fill: "#00000000",
  });
  if (visuals.length === 1) {
    const visual = visuals[0];
    const visualLabel = visualLabels[0] || visual.label || "Bounded visual reference";
    const image = slide.images.add({
      dataUrl: visual.data_url,
      fit: "contain",
      alt: visual.alt || visual.label || "Visual context",
    });
    image.position = {
      left: panel.left + 24,
      top: panel.top + 58,
      width: panel.width - 48,
      height: panel.height - 94,
    };
    addText(slide, visualLabel, panel.left + 24, panel.top + panel.height - 36, panel.width - 48, 20, {
      size: 10,
      color: slideData.theme.muted,
      face: slideData.theme.bodyFace,
      fill: "#00000000",
      align: "center",
    });
    return true;
  }

  const layout = ["primary_supporting", "main_plus_inset"].includes(slideData.visual_layout)
    ? slideData.visual_layout
    : "pair_equal";
  const slots =
    layout === "primary_supporting"
      ? [
          {
            left: panel.left + 24,
            top: panel.top + 72,
            width: 344,
            height: 364,
            roleLabel: "Primary visual",
            roleLabelTop: panel.top + 52,
            labelTop: panel.top + 448,
          },
          {
            left: panel.left + 392,
            top: panel.top + 124,
            width: 140,
            height: 264,
            roleLabel: "Supporting visual",
            roleLabelTop: panel.top + 104,
            labelTop: panel.top + 398,
          },
        ]
      : layout === "main_plus_inset"
      ? [
          {
            left: panel.left + 24,
            top: panel.top + 72,
            width: 360,
            height: 396,
            roleLabel: "Main visual",
            roleLabelTop: panel.top + 52,
            labelTop: panel.top + 480,
          },
          {
            left: panel.left + 392,
            top: panel.top + 104,
            width: 140,
            height: 262,
            roleLabel: "Inset",
            roleLabelTop: panel.top + 84,
            labelTop: panel.top + 378,
          },
        ]
      : [
          {
            left: panel.left + 24,
            top: panel.top + 72,
            width: 244,
            height: 340,
            roleLabel: null,
            labelTop: panel.top + 424,
          },
          {
            left: panel.left + 288,
            top: panel.top + 72,
            width: 244,
            height: 340,
            roleLabel: null,
            labelTop: panel.top + 424,
          },
        ];
  for (const [index, visual] of visuals.slice(0, 2).entries()) {
    const slot = slots[index];
    const visualLabel = visualLabels[index] || visual.label || "Bounded visual reference";
    const image = slide.images.add({
      dataUrl: visual.data_url,
      fit: "contain",
      alt: visual.alt || visual.label || "Visual context",
    });
    image.position = {
      left: slot.left,
      top: slot.top,
      width: slot.width,
      height: slot.height,
    };
    if (slot.roleLabel) {
      addText(slide, slot.roleLabel, slot.left, slot.roleLabelTop, slot.width, 14, {
        size: 10,
        color: slideData.theme.accentDark,
        bold: true,
        face: slideData.theme.monoFace,
        fill: "#00000000",
        align: "center",
      });
    }
    addText(slide, visualLabel, slot.left, slot.labelTop, slot.width, 28, {
      size: layout === "pair_equal" ? 9 : 8,
      color: slideData.theme.muted,
      face: slideData.theme.bodyFace,
      fill: "#00000000",
      align: "center",
    });
  }
  return true;
}

function addKeyNumbersPanel(slide, deck, slideData, hasVisualPanel) {
  const keyNumbers = Array.isArray(slideData.key_numbers)
    ? slideData.key_numbers.filter(Boolean)
    : [];
  if (keyNumbers.length === 0) {
    return false;
  }
  const panel = hasVisualPanel
    ? { left: 64, top: 414, width: 560, height: 116 }
    : { left: 64, top: 492, width: 1152, height: 92 };
  addPanel(slide, panel.left, panel.top, panel.width, panel.height, deck.theme.panelAlt, deck.theme.altPanelLine);
  addText(slide, "Evidence anchor", panel.left + 24, panel.top + 18, 220, 24, {
    size: 14,
    color: deck.theme.accentDark,
    bold: true,
    face: deck.theme.monoFace,
    fill: "#00000000",
  });
  addText(
    slide,
    normalizeLines(keyNumbers.slice(0, hasVisualPanel ? 2 : 3), { prefix: "• " }),
    panel.left + 24,
    panel.top + (hasVisualPanel ? 46 : 40),
    hasVisualPanel ? 512 : 1104,
    hasVisualPanel ? 48 : 36,
    {
      size: hasVisualPanel ? 14 : 14,
      color: deck.theme.graphite,
      face: deck.theme.bodyFace,
      fill: "#00000000",
    },
  );
  return true;
}

function addSlide(presentation, deck, slideData, index) {
  const slide = presentation.slides.add();
  slide.background.fill = deck.theme.paper;
  addRule(slide, 0, 0, WIDTH, 14, deck.theme.accent);
  addRule(slide, 64, 72, 1152, 2, deck.theme.rule);

  if (deck.templateVariant.showSectionEyebrow) {
    addText(slide, String(slideData.section || deck.talk_mode || "talk").toUpperCase(), 64, 32, 360, 24, {
      size: 13,
      color: deck.theme.accentDark,
      bold: true,
      face: deck.theme.monoFace,
      fill: "#00000000",
    });
  }
  addText(slide, `${String(index + 1).padStart(2, "0")} / ${String(deck.slides.length).padStart(2, "0")}`, 1080, 32, 136, 24, {
    size: 13,
    color: deck.theme.accentDark,
    bold: true,
    face: deck.theme.monoFace,
    align: "right",
    fill: "#00000000",
  });

  const hasVisualPanel = addVisualPanel(slide, slideData);
  const hasKeyNumbers = addKeyNumbersPanel(slide, deck, slideData, hasVisualPanel);
  const hasRightColumn = hasKeyNumbers || hasVisualPanel;
  addManifestBadges(slide, slideData, hasRightColumn);
  const titleWidth = hasVisualPanel ? 560 : 1152;
  const titleSize = hasVisualPanel ? 30 : 34;
  const messagePanelWidth = hasVisualPanel ? 560 : 1152;
  const messageTextWidth = hasVisualPanel ? 512 : 1104;
  const messagePanelHeight = hasVisualPanel ? 156 : 228;
  const messageTextHeight = hasVisualPanel ? 110 : 176;
  const messageTextSize = hasVisualPanel ? 22 : 26;

  addText(slide, slideData.title, 64, 108, titleWidth, 104, {
    size: titleSize,
    color: deck.theme.ink,
    bold: true,
    face: deck.theme.titleFace,
    fill: "#00000000",
  });

  addPanel(slide, 64, 232, messagePanelWidth, messagePanelHeight, deck.theme.panel, deck.theme.panelLine);
  addText(slide, slideData.primary_message, 88, 258, messageTextWidth, messageTextHeight, {
    size: messageTextSize,
    color: deck.theme.ink,
    face: deck.theme.bodyFace,
    fill: "#00000000",
  });

  addText(
    slide,
    footerTextForDeck(deck),
    64,
    670,
    1152,
    22,
    {
      size: 11,
      color: deck.theme.muted,
      face: deck.theme.bodyFace,
      fill: "#00000000",
      align: "right",
    },
  );

  const speakerNotes = [
    "[Style Profile]",
    deck.style_profile || "paperpipe_baseline",
    "",
    "[Template Attachment Refs]",
    normalizeLines(deck.template_attachment_refs, { prefix: "- " }) || "- No explicit template attachment refs recorded.",
    "",
    "[Template Variant]",
    deck.template_variant || "default",
    "",
    slideData.primary_message,
    "",
    "[Slide Kind]",
    slideData.slide_kind || "main",
    "",
    "[Speaker Priority]",
    humanizeSpeakerPriority(slideData.speaker_priority) || "not specified",
    "",
    "[Time Budget]",
    humanizeTimeBudget(slideData.time_budget_seconds) || "not specified",
    "",
    "[Claim Refs]",
    normalizeLines(slideData.claim_refs, { prefix: "- " }) || "- No explicit claim refs recorded.",
    "",
    "[Key Number Refs]",
    normalizeLines(slideData.key_number_refs, { prefix: "- " }) || "- No explicit key-number refs recorded.",
    "",
    "[Evidence Refs]",
    normalizeEvidenceRefs(slideData.evidence_refs, { prefix: "- " }) || "- No explicit evidence refs recorded.",
    "",
    "[Source Artifact Refs]",
    normalizeLines(slideData.source_artifact_refs, { prefix: "- " }) || "- No explicit source artifact refs recorded.",
    "",
    "[Visual Refs]",
    normalizeLines(slideData.visual_refs, { prefix: "- " }) || "- No explicit visual refs recorded.",
    "",
    "[Visual Layout]",
    slideData.visual_layout || "auto",
    "",
    "[Visual Labels]",
    normalizeLines(slideData.visual_labels, { prefix: "- " }) || "- No explicit visual labels recorded.",
    "",
    "[Key Numbers]",
    normalizeLines((slideData.key_numbers || []).slice(0, 3), { prefix: "- " }) || "- No explicit key numbers recorded.",
    "",
    "[Notes Focus]",
    normalizeLines(slideData.notes_focus, { prefix: "- " }) || "- Keep the slide message evidence-linked and concise.",
    "",
    "[Warnings]",
    normalizeLines(slideData.warnings, { prefix: "- " }) || "- No explicit warnings recorded for this slide.",
  ].join("\n");
  slide.speakerNotes.setText(speakerNotes);
  return slide;
}

async function exportSlidePreviews(presentation, slides, outputDir) {
  if (!outputDir) {
    return;
  }
  await fs.mkdir(outputDir, { recursive: true });
  for (const [index, slide] of slides.entries()) {
    const canvas = new Canvas(WIDTH, HEIGHT);
    const ctx = canvas.getContext("2d");
    await drawSlideToCtx(slide, presentation, ctx);
    const filename = `slide-${String(index + 1).padStart(2, "0")}.png`;
    await canvas.toFile(path.join(outputDir, filename));
  }
}

const raw = await fs.readFile(inputPath, "utf8");
const deck = JSON.parse(raw);
if (!Array.isArray(deck.slides) || deck.slides.length === 0) {
  throw new Error("Talk Pack PPTX builder requires at least one slide.");
}
deck.style_profile = String(deck.style_profile || "paperpipe_baseline").trim() || "paperpipe_baseline";
deck.template_attachment_refs = Array.isArray(deck.template_attachment_refs)
  ? deck.template_attachment_refs.filter(Boolean)
  : [];
deck.template_variant = String(deck.template_variant || "default").trim() || "default";
deck.theme = THEMES[deck.style_profile] || THEMES.paperpipe_baseline;
deck.templateVariant = TEMPLATE_VARIANTS[deck.template_variant] || TEMPLATE_VARIANTS.default;
for (const slideData of deck.slides) {
  slideData.theme = deck.theme;
}

const presentation = Presentation.create({
  slideSize: { width: WIDTH, height: HEIGHT },
});

const renderedSlides = [];
for (const [index, slideData] of deck.slides.entries()) {
  renderedSlides.push(addSlide(presentation, deck, slideData, index));
}

const blob = await PresentationFile.exportPptx(presentation);
await blob.save(outputPath);
await exportSlidePreviews(presentation, renderedSlides, previewDir);
console.log(outputPath);
