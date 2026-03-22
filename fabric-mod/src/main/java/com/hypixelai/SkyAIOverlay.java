package com.hypixelai;

import net.fabricmc.fabric.api.client.rendering.v1.HudRenderCallback;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.font.TextRenderer;
import net.minecraft.client.gui.DrawContext;
import net.minecraft.client.render.RenderTickCounter;
import net.minecraft.text.OrderedText;
import net.minecraft.text.Text;

import java.util.ArrayList;
import java.util.List;

/**
 * Polished floating HUD overlay for AI responses.
 * Terminal-style dark panel with simulated rounded corners,
 * gradient header, soft shadow, and traffic light dots.
 */
public class SkyAIOverlay implements HudRenderCallback {

    // Layout
    private static final int MARGIN_RIGHT = 10;
    private static final int MARGIN_TOP = 10;
    private static final int PADDING_X = 10;
    private static final int PADDING_Y = 8;
    private static final int HEADER_HEIGHT = 14;
    private static final int QUESTION_HEIGHT = 12;
    private static final int LINE_HEIGHT = 11;
    private static final int MAX_WIDTH = 260;
    private static final int MIN_WIDTH = 180;
    private static final int R = 3; // corner "radius" in pixels

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
        int wrapWidth = MAX_WIDTH - PADDING_X * 2;
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

    @Override
    public void onHudRender(DrawContext context, RenderTickCounter tickCounter) {
        if (currentQuestion == null && !thinking) return;

        long now = System.currentTimeMillis();
        MinecraftClient client = MinecraftClient.getInstance();
        if (client == null) return;
        TextRenderer tr = client.textRenderer;
        int screenW = client.getWindow().getScaledWidth();

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

        // Has question bar?
        boolean hasQuestion = currentQuestion != null && !currentQuestion.isEmpty() && !thinking;
        int questionBarH = hasQuestion ? QUESTION_HEIGHT + 4 : 0;

        // Calculate dimensions
        int contentW, bodyH;
        if (thinking) {
            contentW = MIN_WIDTH;
            bodyH = PADDING_Y + LINE_HEIGHT + PADDING_Y;
        } else if (processedLines != null) {
            int maxLineW = 0;
            for (OverlayLine line : processedLines) {
                if (line.type != LineType.SPACER) {
                    int w = tr.getWidth(line.text) + line.indent + 10;
                    if (w > maxLineW) maxLineW = w;
                }
            }
            if (hasQuestion) {
                int qw = tr.getWidth("> " + currentQuestion) + 10;
                if (qw > maxLineW) maxLineW = qw;
            }
            contentW = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, maxLineW + PADDING_X * 2));
            int linesH = 0;
            for (OverlayLine line : processedLines) {
                linesH += (line.type == LineType.SPACER) ? 6 : LINE_HEIGHT;
            }
            bodyH = PADDING_Y + linesH + PADDING_Y;
        } else {
            return;
        }

        int totalH = HEADER_HEIGHT + 1 + questionBarH + bodyH;

        // Position: top-right
        int x = screenW - contentW - MARGIN_RIGHT;
        int y = MARGIN_TOP;

        // === SOFT SHADOW (multi-layer) ===
        for (int i = 4; i >= 1; i--) {
            int sa = (int)(((5 - i) * 12) * alpha);
            if (sa > 0) {
                fillRounded(context, x - i + 1, y - i + 2, contentW + (i - 1) * 2, totalH + (i - 1) * 2,
                        R + i - 1, (sa << 24));
            }
        }

        // === MAIN PANEL (rounded) ===
        fillRounded(context, x, y, contentW, totalH, R, col(0xF0, 0x1A, 0x1A, 0x2E, alpha));

        // === HEADER (gradient effect — 3 bands) ===
        int hY = y;
        int bandH = HEADER_HEIGHT / 3;
        fillRoundedTop(context, x, hY, contentW, bandH, R, col(0xFF, 0x30, 0x30, 0x4A, alpha));
        fill(context, x, hY + bandH, x + contentW, hY + bandH * 2, col(0xFF, 0x2C, 0x2C, 0x44, alpha));
        fill(context, x, hY + bandH * 2, x + contentW, hY + HEADER_HEIGHT, col(0xFF, 0x28, 0x28, 0x40, alpha));

        // Top edge highlight
        fill(context, x + R, y, x + contentW - R, y + 1, col(0x44, 0x88, 0x88, 0xCC, alpha));

        // Accent line under header
        fill(context, x, y + HEADER_HEIGHT, x + contentW, y + HEADER_HEIGHT + 1, col(0xFF, 0x00, 0xBB, 0xEE, alpha));

        // === TRAFFIC LIGHT DOTS ===
        int dotCY = y + HEADER_HEIGHT / 2;
        int dotCX = x + 9;
        // Each dot: 3x3 center + 4 extra pixels for cross shape (simulates circle)
        drawDot(context, dotCX, dotCY, 0xFF5F57, alpha);
        drawDot(context, dotCX + 8, dotCY, 0xFFBD2E, alpha);
        drawDot(context, dotCX + 16, dotCY, 0x28C840, alpha);

        // === TITLE ===
        int titleX = x + 9 + 24 + 4;
        context.drawText(tr, "SkyAI", titleX, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF00DDFF, alpha), false);

        // Version
        String ver = "v" + HypixelAIUpdater.MOD_VERSION;
        int verW = tr.getWidth(ver);
        context.drawText(tr, ver, x + contentW - verW - PADDING_X, y + (HEADER_HEIGHT - 8) / 2,
                withAlpha(0xFF555566, alpha), false);

        // === QUESTION BAR ===
        int contentY = y + HEADER_HEIGHT + 1;
        if (hasQuestion) {
            fill(context, x, contentY, x + contentW, contentY + questionBarH,
                    col(0xFF, 0x1E, 0x1E, 0x30, alpha));
            // Subtle separator
            fill(context, x + PADDING_X, contentY + questionBarH - 1,
                    x + contentW - PADDING_X, contentY + questionBarH,
                    col(0x33, 0x55, 0x55, 0x77, alpha));

            String qText = "> " + currentQuestion;
            if (tr.getWidth(qText) > contentW - PADDING_X * 2) {
                qText = qText.substring(0, Math.min(qText.length(), 35)) + "...";
            }
            context.drawText(tr, qText, x + PADDING_X, contentY + 3,
                    withAlpha(0xFF44AACC, alpha), false);
            contentY += questionBarH;
        }

        // === BODY TEXT ===
        int cy = contentY + PADDING_Y;

        if (thinking) {
            long dots = ((now - thinkingStart) / 400) % 4;
            String thinkText = "Thinking" + ".".repeat((int) dots);
            context.drawText(tr, thinkText, x + PADDING_X, cy, withAlpha(0xFF888899, alpha), false);
        } else if (processedLines != null) {
            int tx = x + PADDING_X;
            for (OverlayLine line : processedLines) {
                if (line.type == LineType.SPACER) { cy += 6; continue; }

                int lx = tx + line.indent;

                switch (line.type) {
                    case BULLET:
                        context.drawText(tr, "\u2022", tx + 2, cy, withAlpha(0xFFFFAA00, alpha), false);
                        context.drawText(tr, line.text, lx + 8, cy, withAlpha(0xFFCCCCCC, alpha), false);
                        break;
                    case BULLET_CONT:
                        context.drawText(tr, line.text, lx + 8, cy, withAlpha(0xFFCCCCCC, alpha), false);
                        break;
                    case NUMBERED:
                        int dotIdx = line.text.indexOf('.');
                        if (dotIdx > 0 && dotIdx < 4) {
                            String num = line.text.substring(0, dotIdx + 1);
                            String rest = line.text.substring(dotIdx + 1).trim();
                            context.drawText(tr, num, lx, cy, withAlpha(0xFF00BBEE, alpha), false);
                            context.drawText(tr, rest, lx + tr.getWidth(num + " "), cy,
                                    withAlpha(0xFFCCCCCC, alpha), false);
                        } else {
                            context.drawText(tr, line.text, lx, cy, withAlpha(0xFFCCCCCC, alpha), false);
                        }
                        break;
                    default:
                        context.drawText(tr, line.text, lx, cy, withAlpha(0xFFCCCCCC, alpha), false);
                        break;
                }
                cy += LINE_HEIGHT;
            }
        }

        // === BOTTOM EDGE (subtle) ===
        // Dark line at very bottom for depth
        fill(context, x + R, y + totalH - 1, x + contentW - R, y + totalH,
                col(0x22, 0x00, 0x00, 0x00, alpha));
    }

    // --- Drawing helpers ---

    /**
     * Draw a dot as a cross/diamond shape to simulate a circle at small scale.
     * At 5x5 this looks like:
     *   .###.
     *   #####
     *   #####
     *   #####
     *   .###.
     */
    private static void drawDot(DrawContext ctx, int cx, int cy, int rgb, float alpha) {
        int c = col(0xFF, (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF, alpha);
        // 3x5 vertical strip
        fill(ctx, cx - 1, cy - 2, cx + 2, cy + 3, c);
        // 5x3 horizontal strip
        fill(ctx, cx - 2, cy - 1, cx + 3, cy + 2, c);
    }

    /**
     * Fill a "rounded" rectangle by clipping corners.
     * For R=3:
     *    ...######...    (row 0: indent 3)
     *    .##########.    (row 1: indent 1)
     *    ############    (row 2+: full width)
     *    ...
     *    ############    (row h-3: full width)
     *    .##########.    (row h-2: indent 1)
     *    ...######...    (row h-1: indent 3)
     */
    private static void fillRounded(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;

        // Corner insets for each row from the edge (approximate circle)
        int[] insets;
        if (r >= 3) {
            insets = new int[]{3, 1, 1};
        } else if (r >= 2) {
            insets = new int[]{2, 1};
        } else {
            insets = new int[]{1};
        }

        // Top rounded rows
        for (int i = 0; i < insets.length && i < h; i++) {
            fill(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);
        }

        // Middle full rows
        int midStart = Math.min(insets.length, h);
        int midEnd = Math.max(midStart, h - insets.length);
        if (midEnd > midStart) {
            fill(ctx, x, y + midStart, x + w, y + midEnd, color);
        }

        // Bottom rounded rows
        for (int i = 0; i < insets.length && (h - 1 - i) >= midEnd; i++) {
            fill(ctx, x + insets[i], y + h - 1 - i, x + w - insets[i], y + h - i, color);
        }
    }

    /**
     * Fill a rectangle with only the top corners rounded.
     */
    private static void fillRoundedTop(DrawContext ctx, int x, int y, int w, int h, int r, int color) {
        if (h <= 0 || w <= 0) return;

        int[] insets;
        if (r >= 3) {
            insets = new int[]{3, 1, 1};
        } else if (r >= 2) {
            insets = new int[]{2, 1};
        } else {
            insets = new int[]{1};
        }

        // Top rounded rows
        for (int i = 0; i < insets.length && i < h; i++) {
            fill(ctx, x + insets[i], y + i, x + w - insets[i], y + i + 1, color);
        }

        // Rest is full width
        int midStart = Math.min(insets.length, h);
        if (h > midStart) {
            fill(ctx, x, y + midStart, x + w, y + h, color);
        }
    }

    private static void fill(DrawContext ctx, int x1, int y1, int x2, int y2, int argb) {
        if (((argb >> 24) & 0xFF) <= 0) return;
        ctx.fill(x1, y1, x2, y2, argb);
    }

    private static int col(int a, int r, int g, int b, float alpha) {
        int fa = (int)(a * alpha);
        return (fa << 24) | (r << 16) | (g << 8) | b;
    }

    private static int withAlpha(int argb, float alpha) {
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
