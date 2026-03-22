package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.text.OrderedText;
import net.minecraft.text.Text;
import org.lwjgl.nanovg.NVGColor;
import org.lwjgl.nanovg.NVGPaint;
import org.lwjgl.nanovg.NanoVG;
import org.lwjgl.nanovg.NanoVGGL3;
import org.lwjgl.opengl.GL11;
import org.lwjgl.opengl.GL14;

import java.util.ArrayList;
import java.util.List;

import static org.lwjgl.nanovg.NanoVG.*;

/**
 * Smooth vector HUD overlay using NanoVG for backgrounds/shapes
 * and Minecraft's TextRenderer for text.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // NanoVG context
    private static long vg = 0;
    private static boolean nvgInitFailed = false;

    // Layout constants (in GUI-scaled pixels)
    private static final int MARGIN_RIGHT = 8;
    private static final int MARGIN_TOP = 8;
    private static final int PADDING = 10;
    private static final int HEADER_HEIGHT = 18;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 260;
    private static final int MIN_WIDTH = 160;
    private static final int CORNER_RADIUS = 5;
    private static final float DOT_RADIUS = 3.5f;

    // State (set from any thread)
    private static volatile String currentQuestion = null;
    private static volatile String[] rawLines = null;
    private static volatile boolean thinking = false;
    private static volatile long showTime = 0;
    private static volatile long hideTime = 0;
    private static volatile long thinkingStart = 0;

    // Processed lines (render thread only)
    private static List<OverlayLine> processedLines = null;
    private static String[] processedFrom = null;

    private static final long FADE_IN_MS = 200;
    private static final long DISPLAY_MS = 15000;
    private static final long FADE_OUT_MS = 500;

    public static void show(String question, String[] responseLines) {
        currentQuestion = question;
        rawLines = responseLines;
        processedLines = null;
        processedFrom = null;
        showTime = System.currentTimeMillis();
        hideTime = 0;
        thinking = false;
    }

    public static void showThinking(String question) {
        currentQuestion = question;
        rawLines = null;
        processedLines = null;
        processedFrom = null;
        thinking = true;
        thinkingStart = System.currentTimeMillis();
        showTime = System.currentTimeMillis();
        hideTime = 0;
    }

    public static void hide() {
        if (hideTime == 0 && (rawLines != null || thinking)) {
            hideTime = System.currentTimeMillis();
        }
    }

    public static void clear() {
        currentQuestion = null;
        rawLines = null;
        processedLines = null;
        processedFrom = null;
        thinking = false;
        showTime = 0;
        hideTime = 0;
    }

    public static void register() {
        HudRenderCallback.EVENT.register(new SkyAIOverlay());
    }

    private static void processLines(TextRenderer tr, String[] lines) {
        int wrapWidth = MAX_WIDTH - PADDING * 2;
        List<OverlayLine> result = new ArrayList<>();

        for (String line : lines) {
            if (line.isEmpty()) {
                result.add(new OverlayLine("", LineType.SPACER, 0));
                continue;
            }

            LineType type = LineType.NORMAL;
            String content = line;
            int indent = 0;

            if (line.startsWith("- ") || line.startsWith("* ")) {
                type = LineType.BULLET;
                content = line.substring(2);
                indent = 8;
            } else if (line.matches("^\\d+\\.\\s.*")) {
                type = LineType.NUMBERED;
                indent = 4;
            }

            List<OrderedText> wrapped = tr.wrapLines(Text.literal(content), wrapWidth - indent);
            for (int i = 0; i < wrapped.size(); i++) {
                LineType t = (i == 0) ? type : (type == LineType.BULLET ? LineType.BULLET_CONT : LineType.NORMAL);
                StringBuilder sb = new StringBuilder();
                wrapped.get(i).accept((index, style, codePoint) -> {
                    sb.appendCodePoint(codePoint);
                    return true;
                });
                result.add(new OverlayLine(sb.toString(), t, indent));
            }
        }

        processedLines = result;
    }

    private static void initNanoVG() {
        if (vg != 0 || nvgInitFailed) return;
        try {
            vg = NanoVGGL3.nvgCreate(NanoVGGL3.NVG_ANTIALIAS | NanoVGGL3.NVG_STENCIL_STROKES);
            if (vg == 0) {
                HypixelAIMod.LOGGER.error("[HypixelAI] Failed to create NanoVG context");
                nvgInitFailed = true;
            } else {
                HypixelAIMod.LOGGER.info("[HypixelAI] NanoVG initialized");
            }
        } catch (Exception e) {
            HypixelAIMod.LOGGER.error("[HypixelAI] NanoVG init error", e);
            nvgInitFailed = true;
        }
    }

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (currentQuestion == null && !thinking) return;

        long now = System.currentTimeMillis();
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;
        TextRenderer tr = client.textRenderer;
        int screenW = client.getWindow().getScaledWidth();
        int screenH = client.getWindow().getScaledHeight();

        // Lazy-process raw lines on render thread
        String[] raw = rawLines;
        if (raw != null && (processedLines == null || processedFrom != raw)) {
            processLines(tr, raw);
            processedFrom = raw;
        }

        // Auto-hide
        if (hideTime == 0 && processedLines != null) {
            if (now - showTime > DISPLAY_MS) hideTime = now;
        }

        // Alpha
        float alpha;
        if (hideTime > 0) {
            float fadeOut = 1f - (float)(now - hideTime) / FADE_OUT_MS;
            if (fadeOut <= 0) { clear(); return; }
            alpha = fadeOut;
        } else {
            alpha = Math.min(1f, (float)(now - showTime) / FADE_IN_MS);
        }

        // Calculate dimensions
        int contentW, contentH;
        if (thinking) {
            contentW = MIN_WIDTH;
            contentH = HEADER_HEIGHT + 1 + PADDING + LINE_HEIGHT + PADDING;
        } else if (processedLines != null) {
            int maxLineW = 0;
            for (OverlayLine line : processedLines) {
                if (line.type != LineType.SPACER) {
                    int w = tr.getWidth(line.text) + line.indent + 8;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            contentW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, maxLineW + PADDING * 2 + 8));
            int linesH = 0;
            for (OverlayLine line : processedLines) {
                linesH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            contentH = HEADER_HEIGHT + 1 + PADDING + linesH + PADDING;
        } else {
            return;
        }

        // Position: top-right
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // --- NanoVG: draw smooth background shapes ---
        initNanoVG();
        if (vg != 0) {
            drawNvgBackground(client, x, y, contentW, contentH, alpha);
        } else {
            // Fallback: simple fill rectangles
            drawFillFallback(context, x, y, contentW, contentH, alpha);
        }

        // --- Minecraft TextRenderer: draw text on top ---
        drawText(context, tr, x, y, contentW, alpha, now);
    }

    private void drawNvgBackground(MinecraftClient client, int x, int y, int w, int h, float alpha) {
        // Get actual framebuffer dimensions for NanoVG
        int fbW = client.getWindow().getFramebufferWidth();
        int fbH = client.getWindow().getFramebufferHeight();
        float scaleFactor = (float) client.getWindow().getScaleFactor();

        // Save GL state that NanoVG will modify
        boolean depthTest = GL11.glIsEnabled(GL11.GL_DEPTH_TEST);
        boolean blend = GL11.glIsEnabled(GL11.GL_BLEND);
        boolean cullFace = GL11.glIsEnabled(GL11.GL_CULL_FACE);
        int[] prevBlendSrc = new int[1];
        int[] prevBlendDst = new int[1];
        GL11.glGetIntegerv(GL11.GL_BLEND_SRC, prevBlendSrc);
        GL11.glGetIntegerv(GL11.GL_BLEND_DST, prevBlendDst);

        nvgBeginFrame(vg, fbW / scaleFactor, fbH / scaleFactor, scaleFactor);

        // Shadow (subtle drop shadow)
        try (NVGPaint shadowPaint = NVGPaint.calloc()) {
            try (NVGColor shadowInner = nvgColor(0, 0, 0, 0.4f * alpha);
                 NVGColor shadowOuter = nvgColor(0, 0, 0, 0f)) {
                nvgBoxGradient(vg, x, y + 2, w, h, CORNER_RADIUS, 8, shadowInner, shadowOuter, shadowPaint);
                nvgBeginPath(vg);
                nvgRect(vg, x - 10, y - 10, w + 20, h + 20);
                nvgFillPaint(vg, shadowPaint);
                nvgFill(vg);
            }
        }

        // Main background — dark with rounded corners
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x, y, w, h, CORNER_RADIUS);
        try (NVGColor bg = nvgColor(0x14, 0x14, 0x20, (int)(0xF0 * alpha))) {
            nvgFillColor(vg, bg);
        }
        nvgFill(vg);

        // Header background — slightly lighter, rounded top only
        nvgBeginPath(vg);
        nvgRoundedRectVarying(vg, x, y, w, HEADER_HEIGHT, CORNER_RADIUS, CORNER_RADIUS, 0, 0);
        try (NVGColor headerBg = nvgColor(0x28, 0x28, 0x40, (int)(0xFF * alpha))) {
            nvgFillColor(vg, headerBg);
        }
        nvgFill(vg);

        // Accent line under header
        nvgBeginPath(vg);
        nvgRect(vg, x, y + HEADER_HEIGHT, w, 1);
        try (NVGColor accent = nvgColor(0x00, 0xBB, 0xEE, (int)(0xFF * alpha))) {
            nvgFillColor(vg, accent);
        }
        nvgFill(vg);

        // Border
        nvgBeginPath(vg);
        nvgRoundedRect(vg, x + 0.5f, y + 0.5f, w - 1, h - 1, CORNER_RADIUS);
        try (NVGColor border = nvgColor(0x44, 0x44, 0x66, (int)(0x88 * alpha))) {
            nvgStrokeColor(vg, border);
        }
        nvgStrokeWidth(vg, 1.0f);
        nvgStroke(vg);

        // Traffic light dots
        float dotY = y + HEADER_HEIGHT / 2f;
        float dotX = x + 10;
        float dotGap = DOT_RADIUS * 2 + 4;

        drawDot(dotX, dotY, 0xFF, 0x5F, 0x57, alpha);                   // red
        drawDot(dotX + dotGap, dotY, 0xFF, 0xBD, 0x2E, alpha);          // yellow
        drawDot(dotX + dotGap * 2, dotY, 0x28, 0xC8, 0x40, alpha);      // green

        nvgEndFrame(vg);

        // Restore GL state
        if (depthTest) GL11.glEnable(GL11.GL_DEPTH_TEST); else GL11.glDisable(GL11.GL_DEPTH_TEST);
        if (blend) GL11.glEnable(GL11.GL_BLEND); else GL11.glDisable(GL11.GL_BLEND);
        if (cullFace) GL11.glEnable(GL11.GL_CULL_FACE); else GL11.glDisable(GL11.GL_CULL_FACE);
        GL11.glBlendFunc(prevBlendSrc[0], prevBlendDst[0]);
    }

    private void drawDot(float cx, float cy, int r, int g, int b, float alpha) {
        nvgBeginPath(vg);
        nvgCircle(vg, cx, cy, DOT_RADIUS);
        try (NVGColor col = nvgColor(r, g, b, (int)(0xFF * alpha))) {
            nvgFillColor(vg, col);
        }
        nvgFill(vg);
    }

    /**
     * Fallback rendering if NanoVG fails to initialize.
     */
    private void drawFillFallback(DrawContext context, int x, int y, int w, int h, float alpha) {
        int bgColor = alphaColor(0xF01E1E2E, alpha);
        int headerColor = alphaColor(0xFF282840, alpha);
        int accentColor = alphaColor(0xFF00BBEE, alpha);

        context.fill(x, y, x + w, y + h, bgColor);
        context.fill(x, y, x + w, y + HEADER_HEIGHT, headerColor);
        context.fill(x, y + HEADER_HEIGHT, x + w, y + HEADER_HEIGHT + 1, accentColor);
    }

    /**
     * Draw all text using Minecraft's TextRenderer (always crisp bitmap text).
     */
    private void drawText(DrawContext context, TextRenderer tr, int x, int y, int contentW, float alpha, long now) {
        // Title
        int titleX = x + 10 + (int)(DOT_RADIUS * 2 + 4) * 3 + 4;
        context.drawText(tr, "SkyAI", titleX, y + (HEADER_HEIGHT - 8) / 2,
                applyAlpha(0xFF00DDFF, alpha), false);

        // Version
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING, y + (HEADER_HEIGHT - 8) / 2,
                applyAlpha(0xFF777788, alpha), false);

        // Content
        int cy = y + HEADER_HEIGHT + 1 + PADDING;

        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int) dots);
            context.drawText(tr, thinkText, x + PADDING, cy, applyAlpha(0xFF777788, alpha), false);
        } else if (processedLines != null) {
            int tx = x + PADDING;
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }

                int lx = tx + line.indent;

                switch (line.type) {
                    case BULLET:
                        context.drawText(tr, "\u2022", tx, cy, applyAlpha(0xFFFFAA00, alpha), false);
                        context.drawText(tr, line.text, lx + 8, cy, applyAlpha(0xFFCCCCCC, alpha), false);
                        break;
                    case BULLET_CONT:
                        context.drawText(tr, line.text, lx + 8, cy, applyAlpha(0xFFCCCCCC, alpha), false);
                        break;
                    case NUMBERED:
                        int dotIdx = line.text.indexOf('.');
                        if (dotIdx > 0 && dotIdx < 4) {
                            String num = line.text.substring(0, dotIdx + 1);
                            String rest = line.text.substring(dotIdx + 1).trim();
                            context.drawText(tr, num, lx, cy, applyAlpha(0xFF00BBEE, alpha), false);
                            context.drawText(tr, rest, lx + tr.getWidth(num + " "), cy,
                                    applyAlpha(0xFFCCCCCC, alpha), false);
                        } else {
                            context.drawText(tr, line.text, lx, cy, applyAlpha(0xFFCCCCCC, alpha), false);
                        }
                        break;
                    default:
                        context.drawText(tr, line.text, lx, cy, applyAlpha(0xFFCCCCCC, alpha), false);
                        break;
                }
                cy += LINE_HEIGHT;
            }
        }
    }

    // --- Utility ---

    private static NVGColor nvgColor(int r, int g, int b, float a) {
        NVGColor color = NVGColor.calloc();
        color.r(r / 255f);
        color.g(g / 255f);
        color.b(b / 255f);
        color.a(a);
        return color;
    }

    private static NVGColor nvgColor(int r, int g, int b, int a) {
        return nvgColor(r, g, b, a / 255f);
    }

    private static int applyAlpha(int argb, float alpha) {
        int a = (argb >> 24) & 0xFF;
        a = (int)(a * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    private static int alphaColor(int argb, float alpha) {
        int a = (int)(((argb >> 24) & 0xFF) * alpha);
        return (a << 24) | (argb & 0x00FFFFFF);
    }

    private enum LineType { NORMAL, BULLET, BULLET_CONT, NUMBERED, SPACER }

    private static class OverlayLine {
        final String text;
        final LineType type;
        final int indent;
        OverlayLine(String text, LineType type, int indent) {
            this.text = text;
            this.type = type;
            this.indent = indent;
        }
    }
}
